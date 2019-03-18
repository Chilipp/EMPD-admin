# command line parser for the EMPD-admin
import argparse
import os
import os.path as osp
import shlex
import tempfile
import textwrap
from git import Repo
import empd_admin.repo_test as test

parser_info = dict(exited=False, errored=False, exit_message='',
                   exit_status=0)

_parser_info_save = parser_info.copy()


class WebParser(argparse.ArgumentParser):
    """An ArgumentParser that does not sys.exit"""

    def exit(self, status=0, message=None):
        parser_info.update(exited=True, exit_status=status,
                           message=message)
        raise RuntimeError(message or '')

    def error(self, message):
        parser_info['errored'] = True
        args = {'prog': self.prog, 'message': message}
        self.exit(2, '%(prog)s: error: %(message)s' % args)

    def parse_known_args(self, *args, **kwargs):
        parser_info.update(_parser_info_save)
        return super().parse_known_args(*args, **kwargs)


def get_parser():
    parser = argparse.ArgumentParser('empd-admin', add_help=False)

    parser.add_argument(
        '-d', '--directory', default='.',
        help=('Path to the local EMPD2/EMPD-data repository. '
              'Default: %(default)s'))

    setup_subparsers(parser)
    return parser


def setup_subparsers(parser):

    subparsers = parser.add_subparsers(title='Commands', dest='parser')

    test_parser = subparsers.add_parser(
        'test', help='test the database', add_help=False)
    fix_parser = subparsers.add_parser(
        'fix', help='fix the database', add_help=False)

    for subparser in [test_parser, fix_parser]:
        subparser.add_argument(
            '--collect-only', help="only collect tests, don't execute them.",
            action='store_true')
        subparser.add_argument(
            '-x', '--exitfirst',
            help="exit instantly on first error or failed test.",
            action='store_true')
        subparser.add_argument(
            '-m', help=("only run tests matching given mark expression. "
                        "example: -m 'mark1 and not mark2'.'"),
            metavar='MARKEXPR')
        subparser.add_argument(
            '-k', metavar='EXPRESSION',
            help=('only run tests which match the given substring'
                  'expression. An expression is a python evaluatable'
                  'expression where all names are substring-matched'
                  'against test names and their parent classes. Example:'
                  "-k 'test_method or test_other' matches all test"
                  'functions and classes whose name contains'
                  "'test_method' or 'test_other', while -k 'not"
                  "test_method' matches those that don't contain"
                  "'test_method' in their names. Additionally keywords"
                  'are matched to classes and functions containing extra'
                  "names in their 'extra_keyword_matches' set, as well as"
                  'functions which have names assigned directly to them.'))

    fix_parser.add_argument(
        '--no-commit', help="Do not commit the changes", action='store_true')

    # help parser
    choices = subparsers.choices

    help_parser = subparsers.add_parser(
        'help', help='Print the help on a command', add_help=False)

    help_parser.add_argument(
        'command', choices=choices, nargs='?',
        help="Command for which to request the help")

    help_parser.set_defaults(
        print_help=lambda n: choices.get(n, parser).print_help(),
        format_help=lambda n: choices.get(n, parser).format_help())

    return subparsers


def setup_pytest_args(namespace):
    pytest_args = []
    if namespace.m:
        pytest_args.extend(['-m', namespace.m])
        if namespace.parser == 'fix':
            pytest_args[-1] += ' and dbfix'
            pytest_args.append('--fix-db')
    elif namespace.parser == 'fix':
        pytest_args.extend(['-m', 'dbfix', '--fix-db'])
        if not namespace.no_commit:
            pytest_args.append('--commit')
    if namespace.k:
        pytest_args.extend(['-k', namespace.k])
    if namespace.collect_only:
        pytest_args.append('--collect-only')
    if namespace.exitfirst:
        pytest_args.append('-x')

    files = ['fixes.py'] if namespace.parser == 'fix' else ['']

    return pytest_args, files


def process_comment(comment, pr_owner, pr_repo, pr_branch):
    reports = []
    for line in comment.splitlines():
        report = process_comment_line(line, pr_owner, pr_repo, pr_branch)
        if report:
            reports.append(report)
    if reports:
        message = textwrap.dedent("""
        Hi! I'm your friendly automated EMPD-admin bot!

        I processed your command%s and hope that I can help you!
        """ % ('s' if len(reports) > 1 else ''))
        return message + '\n\n' + '\n\n---\n\n'.join(reports)


def process_comment_line(line, pr_owner, pr_repo, pr_branch):
    if not line or not line.startswith('@EMPD-admin'):
        return
    args = shlex.split(line)
    parser = WebParser('@EMPD-admin', add_help=False)
    setup_subparsers(parser)

    ret = '> ' + line[len('@EMPD-admin'):] + '\n\n'

    try:
        ns = parser.parse_args(args[1:])
    except RuntimeError as e:
        if parser_info['message']:
            ret += parser_info['message']
        else:
            ret += repr(e)
    else:
        if ns.parser == 'help':
            ret += '```\n' + ns.format_help(ns.command) + '\n```'
        elif ns.parser is None:
            ret += '```\n' + parser.format_help() + '\n```'
        else:
            with tempfile.TemporaryDirectory('_empd') as tmpdir:
                remote_url = ('https://EMPD-admin:%s@github.com/'
                              f'{pr_owner}/{pr_repo}.git')
                repo = Repo.clone_from(
                    remote_url % os.getenv('GH_TOKEN'), tmpdir,
                    branch=pr_branch)
                pytest_args, files = setup_pytest_args(ns)

                try:
                    meta = test.get_meta_file(tmpdir)
                except Exception:
                    ret += "Could not find meta file in " + remote_url
                else:
                    if len(meta.splitlines()) > 1:
                        ret += "Found multiple potential meta files:\n"
                        ret += '\n'.join(map(osp.basename, meta.splitlines()))
                    else:
                        success, log, md = test.run_test(
                            meta, pytest_args, files)
                        ret += textwrap.dedent("""
                            {}

                            {}
                            <details><summary>Full test report</summary>

                            ```
                            {}
                            ```
                            </details>""").format(
                                "PASSED" if success else "FAILED", log, md)
                # push new commits
                if sum(1 for c in repo.iter_commits(
                        f'origin/{pr_branch}..{pr_branch}')):
                    repo.remotes('origin').push()
    return ret


# --- tests
def test_no_command():
    msg = process_comment_line('should not trigger anything',
                               'EMPD2', 'EMPD-data', 'test-data')
    assert msg is None


def test_help():
    msg = process_comment_line('@EMPD-admin help',
                               'EMPD2', 'EMPD-data', 'test-data')
    parser = argparse.ArgumentParser('@EMPD-admin', add_help=False)
    setup_subparsers(parser)
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        parser.format_help().strip()


def test_help_test():
    msg = process_comment_line('@EMPD-admin help test',
                               'EMPD2', 'EMPD-data', 'test-data')
    parser = argparse.ArgumentParser('@EMPD-admin', add_help=False)
    subparsers = setup_subparsers(parser)
    parser = subparsers.choices['test']
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        parser.format_help().strip()


def test_test_collect():
    msg = process_comment_line('@EMPD-admin test -k precip --collect-only',
                               'EMPD2', 'EMPD-data', 'test-data')
    assert 'test_precip' in msg, msg
    assert 'test_temperature' not in msg


def test_test():
    msg = process_comment_line('@EMPD-admin test -k precip',
                               'EMPD2', 'EMPD-data', 'test-data')
    assert 'test_precip' in msg
    assert 'test_temperature' not in msg


def test_fix():
    msg = process_comment_line('@EMPD-admin fix -k country --no-commit',
                               'EMPD2', 'EMPD-data', 'test-data')

    assert 'fix_country' in msg
    assert 'fix_temperature' not in msg
