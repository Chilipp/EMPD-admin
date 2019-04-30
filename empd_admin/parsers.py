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
import github
import empd_admin.repo_test as test
from empd_admin.finish import (
    finish_pr, rebase_master, look_for_changed_fixed_tables, merge_meta)
import empd_admin.accept as accept
from empd_admin.query import query_meta


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
    parser = argparse.ArgumentParser('empd-admin', add_help=True)

    parser.add_argument(
        '-d', '--directory', default='.',
        help=('Path to the local EMPD2/EMPD-data repository. '
              'Default: %(default)s'))

    subparsers = setup_subparsers(parser)
    subparsers.add_parser(
        'filter-log',
        help="Filter pytest runs with lots of dots")
    return parser


def setup_subparsers(parser, pr_owner=None, pr_repo=None, pr_branch=None,
                     add_help=True):

    subparsers = parser.add_subparsers(title='Commands', dest='parser')

    test_parser = subparsers.add_parser(
        'test', help='test the database', add_help=add_help)
    fix_parser = subparsers.add_parser(
        'fix', help='fix the database', add_help=add_help)

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
            '-s', '--sample', metavar='SampleName', default='.*',
            help=("Name of samples to test. If provided, only samples that "
                  "match the given pattern are tested."))
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
        subparser.add_argument('-v', '--verbose', action='store_true',
                               help='increase verbosity.')

    test_parser.add_argument(
        '--maxfail', metavar='num', default=20, type=int,
        help="exit after first num failures or errors.")

    test_parser.add_argument('-f', '--full-report', action='store_true',
                             help="Print the full test report")

    test_parser.add_argument(
        '-e', '--extract-failed', metavar='filename.tsv', nargs='?',
        const='failed.tsv', default=False,
        help=("Extract the meta data of failed samples into a separate file "
              "in the `failures` directory. Without argument, failed samples "
              "will be extracted to ``%(const)s``."))

    # createdb parser
    createdb_parser = subparsers.add_parser(
        'createdb', help='Create a postgres database out of the data',
        add_help=add_help)

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
        add_help=add_help)

    rebuild_parser.add_argument(
        'tables', help='The table name to rebuild.',
        choices=['all', 'SampleType', 'Country'], nargs='+')

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
        add_help=add_help)

    finish_help = "Commit the changes"
    if pr_owner:
        finish_help += (" and push them to the "
                        f"{pr_branch} branch of {pr_owner}/{pr_repo}")

    finish_parser.add_argument(
        '-c', '--commit', help=finish_help, action='store_true')
    finish_parser.add_argument(
        '-nt', '--no-tests', help="Do not run the tests at the end.",
        action='store_false', dest='test')

    # accept parser
    accept_parser = subparsers.add_parser(
        'accept', add_help=add_help,
        help="Mark incomplete or erroneous meta data as accepted",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    accept_parser.add_argument(
        'acceptable', metavar='SampleName:Column', nargs='+',
        type=lambda s: s.split(':'),
        help=("The sample name and the column that should be accepted despite "
              "being erroneous. For example use `my_sample_a1:Country` to not "
              "check the `Country` column for the sample `my_sample_a1`. "
              "`SampleName` might also be `all` to accept it for all samples. "
              "NOTE: When using --query argument, the SampleName is ignored.")
        )

    accept_parser.epilog = textwrap.dedent(f"""
        Examples
        --------

        - Accept wrong countries for samples starting with "sample_a"::

              {parser.prog} accept sample_a:Country

        - Accept a wrong Country for the sample "sample_a1"::

              {parser.prog} accept -e sample_a1:Country

        - To accept missing Latitudes and Longitudes, use::

              {parser.prog} accept Country -q "Latitude is NULL or Longitude is NULL"
        """)

    # unaccept parser
    unaccept_parser = subparsers.add_parser(
        'unaccept', formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Reverse the acceptance of incomplete or erroneous meta data.",
        add_help=add_help)

    unaccept_parser.add_argument(
        'unacceptable', metavar='SampleName:Column', nargs='+',
        type=lambda s: s.split(':'),
        help=("The sample name and the column that should be rejected if it is"
              " erroneous. For example use `my_sample_a1:Country` to "
              "check the `Country` column for the sample `my_sample_a1` again."
              " `SampleName` and/or `Column` might also be `all` to enable the"
              " tests for all the samples and/or meta data fields again. "
              "NOTE: When using --query argument, the SampleName is ignored.")
        )

    unaccept_parser.epilog = textwrap.dedent(f"""

        Examples
        --------

        - Do not accept any failure for the Country column for samples
          starting with "sample_a"::

              {parser.prog} unaccept sample_a:Country

        - Do not accept any failure for the Country column and one single
          sample "sample_a1"::

              {parser.prog} unaccept -e sample_a1:Country

        - Do not accept any failure for samples where the Country equals
          "Germany"::

              {parser.prog} unaccept Country -q "Country = 'Germany'"
        """)

    for subparser in [accept_parser, unaccept_parser]:
        subparser.add_argument(
            '-e', '--exact', action='store_true',
            help=("Assume provided sample names to match exactly. Otherwise "
                  "we expect a regex and search for it in the sample name."))
        subparser.add_argument(
            '-q', '--query',
            help="""
                Select the samples through an SQLite query instead of the
                `SampleName:Column` syntax. If this argument is provided,
                the resulting query is passed to the WHERE clause of an SQL
                query. E.g. `%(prog)s -q "Country = 'Germany'"` will be
                executed as
                `SELECT SampleName FROM meta WHERE Country = 'Germany'`.
                Note that any provided SampleName in the positional arguments
                (`SampleName:Column`) are then ignored""")
        subparser.add_argument(
            '-m', '--meta-file', metavar="<<metafile>>.tsv",
            help=("The meta file to use. If None, the default meta file of "
                  "repository is used. The path has to be relative to the "
                  "root of the repository."))

    no_commit_help = "Do not commit the changes."
    if pr_owner:
        no_commit_help += (
            " If not set, changes are commited and pushed to the"
            f"{pr_branch} branch of {pr_owner}/{pr_repo}")

    for subparser in [accept_parser, unaccept_parser, fix_parser, test_parser]:
        subparser.add_argument(
            '--no-commit', action='store_true', help=no_commit_help)
        subparser.add_argument(
            '--skip-ci', action='store_true',
            help=("Do not build the commits with the continous integration. "
                  "Has no effect if the `--no-commit` argument is passed as "
                  "well."))

    # filter parser
    query_parser = subparsers.add_parser(
        'query', add_help=add_help,
        help="Query and display the meta data",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    query_parser.add_argument(
        'query',
        help=("The query that is passed to the pandas.DataFrame.query method "
              "to select a subsection of the data. See the examples below for "
              "further details."))
    query_parser.add_argument(
        'columns', nargs='*', default='notnull',
        help=("The columns in the metadata to show. The default is `notnull`, "
              "to only display columns that have at least one valid value. "
              "You can change this by setting it to 'all'"))

    query_parser.add_argument(
        '-d', '--distinct', nargs='+', default=False, metavar='column',
        help=("Be distinct on the given columns (i.e. drop duplicates). "
              "It can also be `all` to consider all columns."))

    query_parser.add_argument(
        '-count', action='store_true',
        help=("Display the number of not-null values (i.e. `COUNT(column)`) "
              "in the selected columns instead of the data table."))

    query_parser.add_argument(
        '-m', '--meta-file', metavar="<<metafile>>.tsv",
        help=("The meta file to use. If None, the default meta file of "
              "repository is used. The path has to be relative to the "
              "root of the repository."))

    commit_help = "Commit the generated file."
    if pr_owner:
        commit_help += (" and push it to the "
                        f"{pr_branch} branch of {pr_owner}/{pr_repo}")

    query_parser.add_argument(
        '-c', '--commit', help=commit_help, action='store_true')

    query_parser.add_argument(
        '-o', '--output', default=None,
        help=("Save the query in the `queries` directory. If not set but "
              "`--commit` is set, then it will be saved as "
              "`queries/query.tsv`."))

    query_parser.epilog = textwrap.dedent(f"""
        Examples
        --------
        Display the samples in Germany::

            {parser.prog} query "Country = 'Germany'"

        Display only the sample names of samples in Germany::

            {parser.prog} query "Country == 'Germany'" SampleName

        Display the samples with a 'forest' SampleContext::

            {parser.prog} query "SampleContext LIKE '%forest%'"
        """)

    merge_meta_parser = subparsers.add_parser(
        'merge-meta', help="Merge two metafiles", add_help=add_help)

    merge_meta_parser.add_argument(
        'src', help=("The tab-separated source file that shall be merged into "
                     "the target file"))

    merge_meta_parser.add_argument(
        'target', nargs='?', default=None,
        help=("The meta file in which `src` should be merged into. If not "
              "set, it is either the new meta file in the root directory of "
              "the repository (if existent) or `meta.tsv`."))

    merge_meta_parser.add_argument(
        '--no-commit', action='store_false', dest='commit',
        help="Do not commit the merge.")

    if pr_owner:
        # add a command to enable edits of a commit
        edit_parser = subparsers.add_parser(
            'allow-edits', help='Allow edits through https://empd2.github.io/')
        noedit_parser = subparsers.add_parser(
            'disable-edits',
            help='Disable edits through https://empd2.github.io/')

    # help parser
    choices = subparsers.choices

    help_parser = subparsers.add_parser(
        'help', help='Print the help on a command', add_help=add_help)

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
    if namespace.skip_ci:
        pytest_args.append('--skip-ci')
    if not namespace.no_commit:
        pytest_args.append('--commit')
    if namespace.k:
        pytest_args.extend(['-k', namespace.k])
    if namespace.collect_only:
        pytest_args.append('--collect-only')
    if namespace.exitfirst:
        pytest_args.append('-x')
    if getattr(namespace, 'maxfail', None) is not None:
        pytest_args.append('--maxfail=%i' % namespace.maxfail)
    if getattr(namespace, 'verbose', False):
        pytest_args.append('-v')
    if getattr(namespace, 'extract_failed', False):
        pytest_args.extend(
            ['--extract-failed=' + (
                 namespace.extract_failed.strip() or 'failed.tsv')])
    pytest_args.append('--sample=' + namespace.sample)

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

    # split args using shlex. We add ` (accent grave) as a quote character
    lex = shlex.shlex(line, posix=True)
    lex.quotes += '`'
    lex.whitespace_split = True
    lex.commenters = ''
    args = list(lex)

    parser = WebParser('@EMPD-admin', add_help=False)
    setup_subparsers(parser, pr_owner, pr_repo, pr_branch, add_help=False)

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
            ret = '```\n' + parser.format_help() + '```'
        elif ns.parser == 'allow-edits':
            pull = github.Github(os.environ['GH_TOKEN']).get_repo(
                'EMPD2/EMPD-data').get_pull(pr_num)
            pull.add_to_labels('viewer-editable')
            ret += ("Ok, I made this PR editable through "
                    "https://empd2.github.io/. If you want to disable this "
                    "again, tell me `@EMPD-admin disable-edits` or remove "
                    "the `viewer-editable` label.")
        elif ns.parser == 'disable-edits':
            pull = github.Github(os.environ['GH_TOKEN']).get_repo(
                'EMPD2/EMPD-data').get_pull(pr_num)
            pull.remove_from_labels('viewer-editable')
            ret += ("Ok, I removed the `viewer-editable` label and wont "
                    "accept data submits through https://empd2.github.io/.")
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
                                    not ns.collect_only and
                                    not ns.full_report):
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
                                if getattr(ns, 'extract_failed', None):
                                    ret += f"\nYou can look at the extracted failures in the viewer at https://EMPD2.github.io/?repo={pr_owner}/{pr_repo}&branch={pr_branch}&meta=failures/{ns.extract_failed}\n"

                        elif ns.parser == 'query':
                            ns.meta_file = ns.meta_file or osp.basename(meta)
                            try:
                                output, msg = query_meta(
                                    ns.meta_file, ns.query, ns.columns,
                                    ns.count, ns.output, ns.commit, tmpdir,
                                    distinct=ns.distinct)
                            except Exception:
                                s = io.StringIO()
                                traceback.print_exc(file=s)
                                output = None
                                msg = ("Sorry buy I failed to do the query:\n"
                                       "\n```{}```").format(s.getvalue())
                            ret += msg
                            if output:
                                ret += f"\n\nYou can look at the extracted data in the viewer at https://EMPD2.github.io/?repo={pr_owner}/{pr_repo}&branch={pr_branch}&meta=queries/{output}\n"
                        elif ns.parser == 'accept':
                            ns.meta_file = ns.meta_file or osp.basename(meta)
                            if ns.query:
                                msg = accept.accept_query(
                                    ns.meta_file, ns.query,
                                    [t[-1] for t in ns.acceptable],
                                    not ns.no_commit, ns.skip_ci,
                                    local_repo=tmpdir)
                            else:
                                msg = accept.accept(
                                    ns.meta_file, ns.acceptable,
                                    not ns.no_commit, ns.skip_ci,
                                    exact=ns.exact, local_repo=tmpdir)
                            ret = ret + msg if msg else ''
                        elif ns.parser == 'unaccept':
                            ns.meta_file = ns.meta_file or osp.basename(meta)
                            if ns.query:
                                msg = accept.unaccept_query(
                                    ns.meta_file, ns.query,
                                    [t[-1] for t in ns.unacceptable],
                                    not ns.no_commit, ns.skip_ci,
                                    local_repo=tmpdir)
                            else:
                                msg = accept.unaccept(
                                    ns.meta_file, ns.unacceptable,
                                    not ns.no_commit, ns.skip_ci,
                                    exact=ns.exact, local_repo=tmpdir)
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
                        elif ns.parser == 'merge-meta':
                            target = merge_meta(
                                osp.join(osp.dirname(meta), ns.src), ns.target,
                                commit=True, local_repo=osp.dirname(meta))
                            ret += f"Ok, I merged {ns.src} into {target}"
                        elif ns.parser == 'finish':
                            try:
                                changed = finish_pr(meta, commit=ns.commit)
                            except Exception:
                                s = io.StringIO()
                                traceback.print_exc(file=s)

                                ret += textwrap.dedent("""
                                    Sorry but I could not finish the PR because of the following exception:

                                    ```
                                    {}
                                    ```

                                    If you don't know, what is wrong here, you should ping `@Chilipp`.""").format(s.getvalue())
                                ns.commit = False
                            else:
                                if not ns.commit:
                                    if ns.test:
                                        # run the tests to check if everything
                                        # goes well
                                        success, log, md = test.run_test(
                                            osp.join(tmpdir, 'meta.tsv'))
                                    else:
                                        success = True
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
                            remote.push(pr_branch)
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
    setup_subparsers(parser, 'EMPD2', 'EMPD-data', 'test-data', add_help=False)
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        '```\n' + parser.format_help() + '```'


def test_help_merge_meta():
    msg = process_comment_line('@EMPD-admin help merge-meta',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    parser = argparse.ArgumentParser('@EMPD-admin', add_help=False)
    subparsers = setup_subparsers(parser, add_help=False)
    parser = subparsers.choices['merge-meta']
    assert '\n'.join(msg.splitlines()[1:]).strip() == \
        '```\n' + parser.format_help().strip() + '\n```'


def test_test_collect():
    msg = process_comment_line('@EMPD-admin test -v precip --collect-only',
                               'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'test_precip' in msg, msg
    assert 'test_temperature' not in msg


def test_test():
    msg = process_comment_line(
        '@EMPD-admin test precip -v -f --extract-failed --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'test_precip' in msg
    assert 'test_temperature' not in msg
    assert 'meta=failures/failed.tsv' in msg


def test_fix():
    msg = process_comment_line('@EMPD-admin fix -v country --no-commit',
                               'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'fix_country' in msg, 'Wrong message:\n' + msg
    assert 'fix_temperature' not in msg, 'Wrong message:\n' + msg


def test_finish():
    msg = process_comment_line('@EMPD-admin finish --no-tests',
                               'EMPD2', 'EMPD-data', 'test-data', 2)

    assert "Finished the PR and everything went fine" in msg, msg


def test_accept():
    msg = process_comment_line(
        '@EMPD-admin accept test_a1:Country --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'Accept wrong Country for sample test_a1' in msg


def test_accept_query():
    msg = process_comment_line(
        ('@EMPD-admin accept -q "SampleName = \'test_a1\'" Country'
         ' --no-commit'),
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert '1 sample' in msg


def test_unaccept():
    msg = process_comment_line(
        '@EMPD-admin unaccept test_a2:Country --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert 'Do not accept wrong Country for sample test_a2' in msg


def test_unaccept_query():
    msg = process_comment_line(
        ('@EMPD-admin unaccept -q "SampleName = \'test_a1\'" Country '
         '--no-commit'),
        'EMPD2', 'EMPD-data', 'test-data', 2)

    assert '1 sample' in msg


def test_query():
    msg = process_comment_line(
        "@EMPD-admin query `okexcept LIKE '%Country%'` SampleName",
        'EMPD2', 'EMPD-data', 'test-data', 2)
    assert 'test_a2' in msg, "Wrong message:\n" + msg
    assert 'test_a1' not in msg, "Wrong message:\n" + msg


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


def test_merge_meta():
    msg = process_comment_line(
        '@EMPD-admin merge-meta failures/failed.tsv --no-commit',
        'EMPD2', 'EMPD-data', 'test-data', 2)
    assert "I merged failures/failed.tsv into test.tsv" in msg
