# command line parser for the EMPD-admin
import os
import argparse
import traceback
import io
import os.path as osp
import shlex
import tempfile
import textwrap
from git import Repo
import empd_admin.repo_test as test
from empd_admin.finish import (
    finish_pr, rebase_master, look_for_changed_fixed_tables)
from empd_admin.accept import accept, unaccept


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


def setup_subparsers(parser, pr_owner=None, pr_repo=None, pr_branch=None):

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
            'k', metavar='EXPRESSION', nargs='?',
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

    test_parser.add_argument(
        '--maxfail', metavar='num', default=20, type=int,
        help="exit after first num failures or errors.")

    test_parser.add_argument('-v', '--verbose', action='store_true',
                             help="Print the full test report")

    # createdb parser
    createdb_parser = subparsers.add_parser(
        'createdb', help='Create a postgres database out of the data',
        add_help=False)

    commit_help = "Dump the postgres database into a .sql file"
    if pr_owner:
        commit_help += (" and push it to the "
                        f"{pr_branch} branch of {pr_owner}/{pr_repo}")
    else:
        createdb_parser.add_argument(
            '-db', '--database',
            help=("The name of the database. If not given, a temporary "
                  "database will be created and deleted afterwards."))
    createdb_parser.add_argument(
        '-c', '--commit', action='store_true', help=commit_help)

    # rebuild parser
    rebuild_parser = subparsers.add_parser(
        'rebuild', help='Rebuild the fixed tables of the postgres database',
        add_help=False)

    rebuild_parser.add_argument(
        'tables', help='The table name to rebuild.',
        choices=['all', 'GroupID', 'SampleType', 'Country'], nargs='+')

    commit_help = "Dump the postgres database into a .sql file"
    if pr_owner:
        commit_help += (" and push it to the "
                        f"{pr_branch} branch of {pr_owner}/{pr_repo}")
    else:
        rebuild_parser.add_argument(
            '-db', '--database',
            help=("The name of the database. If not given, a temporary "
                  "database will be created and deleted afterwards."))
    rebuild_parser.add_argument(
        '-c', '--commit', action='store_true', help=commit_help)

    # rebase parser
    rebase_parser = subparsers.add_parser(
        'rebase', add_help=True,
        help=("Merge the master branch of EMPD2/EMPD-data into the current "
              "branch to resolve merge conflicts"))

    if pr_owner:
        rebase_parser.add_argument(
            '--no-commit', action='store_true',
            help=("Perform the merge but do not push it to "
                  f"{pr_owner}/{pr_repo}"))

    # finish parser
    finish_parser = subparsers.add_parser(
        'finish', help='Finish this PR and merge the data into meta.tsv',
        add_help=False)

    finish_help = "Commit the changes"
    if pr_owner:
        finish_help += (" and push them to the "
                        f"{pr_branch} branch of {pr_owner}/{pr_repo}")

    finish_parser.add_argument(
        '-c', '--commit', help=finish_help, action='store_true')

    # accept parser
    accept_parser = subparsers.add_parser(
        'accept', help="Mark incomplete or erroneous meta data as accepted",
        add_help=False)

    accept_parser.add_argument(
        'acceptable', metavar='SampleName:Column', nargs='+',
        type=lambda s: s.split(':'),
        help=("The sample name and the column that should be accepted despite "
              "being erroneous. For example use `my_sample_a1:Country` to not "
              "check the `Country` column for the sample `my_sample_a1`. "
              "`SampleName` might also be `all` to accept it for all samples.")
        )

    accept_parser.add_argument(
        '-e', '--exact', action='store_true',
        help=("Assume provided sample names to match exactly. Otherwise we "
              "expect a regex and search for it in the sample name."))

    # unaccept parser
    unaccept_parser = subparsers.add_parser(
        'unaccept',
        help="Reverse the acceptance of incomplete or erroneous meta data.",
        add_help=False)

    unaccept_parser.add_argument(
        'unacceptable', metavar='SampleName:Column', nargs='+',
        type=lambda s: s.split(':'),
        help=("The sample name and the column that should be rejected if it is"
              " erroneous. For example use `my_sample_a1:Country` to "
              "check the `Country` column for the sample `my_sample_a1` again."
              " `SampleName` and/or `Column` might also be `all` to enable the"
              " tests for all the samples and/or meta data fields again.")
        )

    unaccept_parser.add_argument(
        '-e', '--exact', action='store_true',
        help=("Assume provided sample names to match exactly. Otherwise we "
              "expect a regex and search for it in the sample name."))

    no_commit_help = "Do not commit the changes."
    if pr_owner:
        no_commit_help += (
            " If not set, changes are commited and pushed to the"
            f"{pr_branch} branch of {pr_owner}/{pr_repo}")

    for subparser in [accept_parser, unaccept_parser, fix_parser]:
        subparser.add_argument(
            '--no-commit', action='store_true', help=no_commit_help)
        subparser.add_argument(
            '--skip-ci', action='store_true',
            help=("Do not build the commits with the continous integration. "
                  "Has no effect if the `--no-commit` argument is passed as "
                  "well."))

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
        if namespace.skip_ci:
            pytest_args.append('--skip-ci')
    if namespace.k:
        pytest_args.extend(['-k', namespace.k])
    if namespace.collect_only:
        pytest_args.append('--collect-only')
    if namespace.exitfirst:
        pytest_args.append('-x')
    if getattr(namespace, 'maxfail', None) is not None:
        pytest_args.append('--maxfail=%i' % namespace.maxfail)

    files = ['fixes.py'] if namespace.parser == 'fix' else ['']

    return pytest_args, files


def process_comment(comment, pr_owner, pr_repo, pr_branch, pr_num):
    reports = []
    for line in comment.splitlines():
        report = process_comment_line(line, pr_owner, pr_repo, pr_branch,
                                      pr_num)
        if report:
            reports.append(report)
    if reports:
        message = textwrap.dedent("""
        Hi! I'm your friendly automated EMPD-admin bot!

        I processed your command%s and hope that I can help you!
        """ % ('s' if len(reports) > 1 else ''))
        return message + '\n\n' + '\n\n---\n\n'.join(reports)


def process_comment_line(line, pr_owner, pr_repo, pr_branch, pr_num):
    if not line or not line.startswith('@EMPD-admin'):
        return
    args = shlex.split(line)
    parser = WebParser('@EMPD-admin', add_help=False)
    setup_subparsers(parser, pr_owner, pr_repo, pr_branch)

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
            ret += '```\n' + ns.format_help(ns.command) + '```'
        elif ns.parser is None:
            ret += '```\n' + parser.format_help() + '```'
        else:
            with tempfile.TemporaryDirectory('_empd') as tmpdir:
                tmpdir = osp.join(tmpdir, '')
                remote_url = ('https://github.com/'
                              f'{pr_owner}/{pr_repo}.git')
                repo = Repo.clone_from(remote_url, tmpdir, branch=pr_branch)
                try:
                    meta = test.get_meta_file(tmpdir)
                except Exception:
                    ret += "Could not find meta file in " + remote_url
                else:
                    if len(meta.splitlines()) > 1:
                        ret += "Found multiple potential meta files:\n"
                        ret += '\n'.join(map(osp.basename, meta.splitlines()))
                    else:
                        if ns.parser in ['test', 'fix']:
                            pytest_args, files = setup_pytest_args(ns)

                            success, log, md = test.run_test(meta, pytest_args,
                                                             files)
                            if success and ns.parser == 'test' and (
                                    not ns.collect_only and not ns.verbose):
                                ret += "All tests passed!"
                            else:
                                ret += textwrap.dedent("""
                                    {}

                                    {}
                                    <details><summary>Full test report</summary>

                                    ```
                                    {}
                                    ```
                                    </details>
                                    """).format(
                                        "PASSED" if success else "FAILED",
                                        md.replace(tmpdir, 'data/'),
                                        log.replace(tmpdir, 'data/'))
                        elif ns.parser == 'accept':
                            msg = accept(meta, ns.acceptable,
                                         not ns.no_commit, ns.skip_ci,
                                         exact=ns.exact)
                            ret = ret + msg if msg else ''
                        elif ns.parser == 'unaccept':
                            msg = unaccept(meta, ns.unacceptable,
                                           not ns.no_commit, ns.skip_ci,
                                           exact=ns.exact)
                            ret = ret + msg if msg else ''
                        elif ns.parser == 'createdb':
                            success, msg, sql_dump = test.import_database(
                                meta, commit=ns.commit)
                            if success:
                                ret += "Postgres import succeded "
                                if sql_dump:
                                    ret += ("and dumped into "
                                            "postgres/%s.sql." % sql_dump)

                                else:
                                    ret += "(but has not been committed)."
                            else:
                                ret += ("Failed to import into postgres!\n\n"
                                        f"```\n{msg}\n```")
                        elif ns.parser == 'rebuild':
                            success, msg, sql_dump = test.import_database(
                                meta, commit=ns.commit,
                                rebuild_fixed=ns.tables)
                            if success:
                                ret += "Postgres import succeded "
                                if sql_dump:
                                    ret += ("and dumped into "
                                            "postgres/%s.sql." % sql_dump)

                                else:
                                    ret += "(but has not been committed)."
                            else:
                                ret += ("Failed to import into postgres!\n\n"
                                        f"```\n{msg}\n```")
                        elif ns.parser == 'rebase':
                            try:
                                rebase_master(meta)
                            except Exception:
                                s = io.StringIO()
                                traceback.print_exc(file=s)

                                ret += textwrap.dedent(f"""
                                    Sorry but I could not rebase {pr_owner}/{pr_repo}:{pr_branch} on EMPD2/EMPD-data:master because of the following Exception:

                                    ```
                                    {{}}
                                    ```

                                    If you don't know, what is wrong here, you should ping `@Chilipp`.""").format(s.getvalue())
                                ns.no_commit = True
                            else:
                                ret += f"I successfully rebased {pr_owner}/{pr_repo}:{pr_branch} on EMPD2/EMPD-data:master"
                                if ns.no_commit:
                                    ret += f" (but did not push to {pr_owner}/{pr_repo})"
                                ret += "."
                        elif ns.parser == 'finish':
                            try:
                                changed = finish_pr(meta, commit=ns.commit)
                            except Exception:
                                s = io.StringIO()
                                traceback.print_exc(file=s)

                                ret += textwrap.dedent("""
                                    Sorry but I could not finish the PR because of the following exception:

                                    ```
                                    {{}}
                                    ```

                                    If you don't know, what is wrong here, you should ping `@Chilipp`.""").format(s.getvalue())
                                ns.commit = False
                            else:
                                if not ns.commit:
                                    # run the tests to check if everything
                                    # goes well
                                    success, log, md = test.run_test(
                                        osp.join(tmpdir, 'meta.tsv'))
                                    if success:
                                        ret += textwrap.dedent(f"""
                                            Finished the PR and everything went fine.
                                            Feel free to run `@EMPD-admin finish --commit` now to push everything to [{pr_owner}/{pr_repo}](https://github.com/{pr_owner}/{pr_repo})
                                            """)
                                    else:
                                        ret += textwrap.dedent("""
                                            Tests failed after finishing the PR!

                                            {}
                                            <details><summary>Full test report</summary>

                                            ```
                                            {}
                                            ```
                                            </details>
                                            """).format(
                                                md.replace(tmpdir, 'data/'),
                                                log.replace(tmpdir, 'data/'))
                                else:
                                    ret += textwrap.dedent(f"""
                                        Finished the PR!

                                        You may want to have a final look into the viewer (https://EMPD2.github.io/?repo={pr_owner}/{pr_repo}&branch={pr_branch}) and then merge it.
                                        """) + look_for_changed_fixed_tables(
                                            meta, pr_owner, pr_repo, pr_branch)

                        # push new commits
                        push2remote = (
                            getattr(ns, 'commit', not getattr(
                                ns, 'no_commit', False)) and
                            sum(1 for c in repo.iter_commits(
                                f'origin/{pr_branch}..{pr_branch}'))
                            )
                        if push2remote:
                            remote_url = ('https://EMPD-admin:%s@github.com/'
                                          f'{pr_owner}/{pr_repo}.git')
                            remote = repo.create_remote(
                                'push_remote',
                                remote_url % os.environ['GH_TOKEN'])
                            remote.push()
    return ret


# --- tests
def test_no_command():
    msg = process_comment_line('should not trigger anything',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    assert msg is None


def test_help():
    msg = process_comment_line('@EMPD-admin help',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    parser = argparse.ArgumentParser('@EMPD-admin', add_help=False)
    setup_subparsers(parser)
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        '```\n' + parser.format_help() + '```'


def test_help_test():
    msg = process_comment_line('@EMPD-admin help test',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    parser = argparse.ArgumentParser('@EMPD-admin', add_help=False)
    subparsers = setup_subparsers(parser)
    parser = subparsers.choices['test']
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        '```\n' + parser.format_help().strip() + '\n```'


def test_test_collect():
    msg = process_comment_line('@EMPD-admin test precip --collect-only',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'test_precip' in msg, msg
    assert 'test_temperature' not in msg


def test_test():
    msg = process_comment_line('@EMPD-admin test precip -v',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'test_precip' in msg
    assert 'test_temperature' not in msg


def test_fix():
    msg = process_comment_line('@EMPD-admin fix country --no-commit',
                               'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'fix_country' in msg, 'Wrong message:\n' + msg
    assert 'fix_temperature' not in msg, 'Wrong message:\n' + msg


def test_finish():
    msg = process_comment_line('@EMPD-admin finish',
                               'EMPD2', 'EMPD-data', 'test-data', 2)

    assert "Tests failed after finishing the PR" in msg, msg


def test_accept():
    msg = process_comment_line(
        '@EMPD-admin accept test_a1:Country --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'test_a1' in msg and 'Country' in msg


def test_unaccept():
    msg = process_comment_line(
        '@EMPD-admin unaccept test_a2:Country --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'test_a2' in msg and 'Country' in msg


def test_createdb():
    msg = process_comment_line(
        '@EMPD-admin createdb', 'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'Postgres import succeded' in msg, "Wrong message:\n" + msg
    assert 'not been committed' in msg, "Wrong message:\n" + msg


def test_rebuild():
    msg = process_comment_line(
        '@EMPD-admin rebuild all', 'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'Postgres import succeded' in msg, "Wrong message:\n" + msg
    assert 'not been committed' in msg, "Wrong message:\n" + msg


def test_rebase():
    msg = process_comment_line(
        '@EMPD-admin rebase --no-commit', 'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'successfully rebased' in msg, "Wrong message:\n" + msg
    assert 'did not push' in msg, "Wrong message:\n" + msg
