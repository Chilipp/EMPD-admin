import sys
import os
import re
import os.path as osp
import contextlib
import time
import subprocess as spr
import shutil

import github
import tempfile
import textwrap
from collections import OrderedDict
from empd_admin.common import get_test_dir, get_psql_scripts

from git import GitCommandError, Repo


@contextlib.contextmanager
def remember_cwd():
    """Context manager to switch back to the current working directory"""
    curdir = os.getcwd()
    try:
        yield
    finally:
        os.chdir(curdir)


@contextlib.contextmanager
def remember_env(key):
    val = os.getenv(key)
    try:
        yield
    finally:
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def wait_for_pg_server(timeout=120):
    for i in range(timeout):
        if not osp.exists(osp.expanduser(osp.join(
                '~', 'starting_pg_server.lock'))):
            return
        time.sleep(1)
    raise TimeoutError(
        "Postgres server has not started within %i seconds" % timeout)


@contextlib.contextmanager
def temporary_database(dbname=None):
    import psycopg2 as psql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    base_url = os.getenv('DATABASE_URL', 'postgres://postgres@localhost/')
    wait_for_pg_server()
    if dbname is not None:
        yield osp.join(base_url, dbname)
    else:
        tmpdir = tempfile.mkdtemp('_empd')
        dbname = osp.basename(tmpdir)
        conn = psql.connect(osp.join(base_url, 'postgres'))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        cursor.execute('CREATE DATABASE ' + dbname)
        conn.commit()
        try:
            yield osp.join(base_url, dbname)
        finally:
            cursor.execute('DROP DATABASE ' + dbname)
            conn.commit()
            conn.close()
            os.rmdir(tmpdir)


def fetch_upstream(repo):
    try:
        remote = repo.remotes['upstream']
    except IndexError:
        remote = repo.create_remote(
            'upstream', 'https://github.com/EMPD2/EMPD-data.git')
    try:
        remote.fetch()
    except GitCommandError:
        pass


def get_meta_file(dirname='.'):
    if not osp.exists(osp.join(dirname, 'meta.tsv')):
        raise ValueError(
            dirname + " does not seem to look like an EMPD-data repo!")
    with remember_cwd():
        os.chdir(dirname)
        files = [f for f in os.listdir('.')
                 if osp.isfile(f) and not f.startswith('.')]
        repo = Repo('.')
        fetch_upstream(repo)
        meta = repo.git.diff(
            'upstream/master', '--name-only', '--diff-filter=A',
            *files).split()
        if meta:
            return '\n'.join(osp.join(dirname, f) for f in meta)

    return osp.join(dirname, 'meta.tsv')


def import_database(meta, dbname=None, commit=False, populate=None,
                    rebuild_fixed=[]):

    SQLSCRIPTS = get_psql_scripts()

    with temporary_database(dbname) as db_url:

        # populate temporary database
        create_tables = fill_tables = True

        if dbname is not None and populate is None:
            import psycopg2 as psql
            with psql.connect(db_url) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT * FROM countries")
                except psql.ProgrammingError:
                    populate = True
                else:
                    conn.commit()
                    res = cursor.fetchall()
                    create_tables = False
                    fill_tables = not bool(res)
                    populate = fill_tables
        if dbname is None or populate:
            if create_tables:
                spr.check_call(['psql', db_url, '-q', '-f',
                                osp.join(SQLSCRIPTS, 'create_empd2.sql')])
            if fill_tables:
                spr.check_call([
                    sys.executable, osp.join(SQLSCRIPTS, 'makeFixedTables.py'),
                    db_url])

        # import the data
        if rebuild_fixed:
            cmd = [sys.executable,
                   osp.join(SQLSCRIPTS, 'updateFixedTables.py'),
                   db_url] + rebuild_fixed
        else:
            cmd = [sys.executable,
                   osp.join(SQLSCRIPTS, 'import_into_empd2.py'),
                   meta, '--database-url', db_url]

        print("Importing in %s with %s" % (db_url, ' '.join(cmd)))
        proc = spr.Popen(cmd, stdout=spr.PIPE, stderr=spr.STDOUT)
        stdout, stderr = proc.communicate()
        success = proc.returncode == 0

        sql_dump = None

        if success and commit:
            repo = Repo(osp.dirname(meta))
            if repo.git.diff(osp.join('postgres', 'scripts', 'tables')):
                repo.index.add(
                    [osp.basename(meta),
                     osp.join('postgres', 'scripts', 'tables')])
                repo.index.commit('Updated fixed tables')
            if dbname:
                meta_base = dbname
            elif osp.basename(meta) == 'meta.tsv':
                meta_base = "EMPD2"
            else:
                meta_base = osp.splitext(osp.basename(meta))[0]

            sql_dump = osp.join(osp.dirname(meta), 'postgres',
                                meta_base + '.sql')
            with open(sql_dump, 'w') as f:
                proc = spr.Popen(['pg_dump', db_url], stdout=f)
                proc.communicate()
                success = proc.returncode == 0
            if success:
                repo.index.add([osp.join('postgres', osp.basename(sql_dump))])
                repo.index.commit(
                    'Added postgres dump for %s' % osp.basename(meta))

    return success, stdout.decode('utf-8'), sql_dump


def replace_dots(s):
    """Replaced '.' and 's' in the pytest report"""
    s = re.sub(r'\[\s*\d+%\]', '', re.sub(r'(?m)^[\.s]{2,1000}', '', s))
    return '\n'.join(filter(None, map(str.strip, s.splitlines())))


def run_test(meta, pytest_args=[], tests=['']):

    TESTDIR = get_test_dir()

    def replace_testdir(s):
        return s.replace(my_testdir, TESTDIR).replace(my_testdir[1:], TESTDIR)

    with remember_env('PYTHONUNBUFFERED'):
        with tempfile.TemporaryDirectory('_test') as report_dir:
            # to make sure that the test directory is writable, we copy it to
            # the directory for the report
            my_testdir = osp.join(report_dir, 'tests')
            shutil.copytree(
                TESTDIR, my_testdir,
                ignore=lambda src, names: names if '__pycache__' in src else []
                )
            os.environ['PYTHONUNBUFFERED'] = '1'  # turn off output buffering
            cmd = [os.getenv('PYTEST', 'pytest'),
                   '--empd-meta=' + meta,
                   '--markdown-report=' + osp.join(report_dir, 'report.md')
                   ] + pytest_args + [osp.join(my_testdir, f) for f in tests]
            print("Starting test run with %s" % ' '.join(cmd))
            proc = spr.Popen(cmd, stdout=spr.PIPE, stderr=spr.STDOUT)
            stdout, stderr = proc.communicate()
            report_path = osp.join(report_dir, 'report.md')
            if not osp.exists(report_path):
                md_report = "Apparently the pytest command failed!"
            else:
                with open(report_path) as f:
                    md_report = f.read()
            success = proc.returncode == 0

    return (success, replace_dots(replace_testdir(stdout.decode('utf-8'))),
            replace_testdir(md_report))


def pr_info(local_repo, pr_owner=None, pr_repo=None, pr_branch=None,
            pr_id=None):
    repo = Repo(local_repo)
    ref_head = repo.refs[f'pull/{pr_id}/head']
    sha = ref_head.commit.hexsha

    meta = get_meta_file(local_repo)

    if len(meta.splitlines()) > 1:
        meta = '\n'.join(map(osp.basename, meta.splitlines()))
        message = textwrap.dedent("""
            Hi! I'm your friendly automated EMPD-admin bot!

            I was trying to test your data submission, but I am not sure, where you store the meta data. I found multiple possible candidates:

            ```
            %s
            ```

            Please only keep one of them and delete the other%s.

            Please ping `@Chilipp` if you believe this is a bug.
            """) % (meta, 's' if len(meta.splitlines()) > 2 else '')
        status = 'failure'

        test_info = {'message': message,
                     'status': status,
                     'sha': sha}

        return test_info

    meta = osp.basename(meta)

    if pr_owner is None:
        url = f'https://EMPD2.github.io/?commit={sha}&meta={meta}'
    else:
        url = (f'https://EMPD2.github.io/?repo={pr_owner}/{pr_repo}&'
               f'branch={pr_branch}&meta={meta}')

    message = textwrap.dedent(f"""
        Hi! I'm your friendly automated EMPD-admin bot!

        Thank you very much for your data submission! I will now run some tests on your data.
        In the meantime: please review your test data on the EMPD viewer using
        this link: {url}

        This bot is helping you merging your data. I am checking for common issues and I can fix your climate, country or elevation data.
        Type `@EMPD-admin help` in a new comment in this PR for usage information.

        <sub>Make sure, that all the commands for the `@EMPD-admin` are on one single line and nothing else. Only
        `@EMPD-admin help`
        will work, not something like
        `<other words> @EMPD-admin help`
        or
        `@EMPD-admin help <other words>`

        Note that you can also run these tests on your local machine with
        pytest.</sub>
        """)

    return {'message': message, 'status': 'pending', 'sha': sha}


def download_pr(repo_owner, repo_name, pr_id, target_dir, force=False):
    gh = github.Github(os.environ['GH_TOKEN'])

    owner = gh.get_user(repo_owner)
    remote_repo = owner.get_repo(repo_name)

    mergeable = None
    while mergeable is None:
        time.sleep(1.0)
        pull_request = remote_repo.get_pull(pr_id)
        if pull_request.state != "open":
            return {}
        mergeable = pull_request.mergeable

    repo = Repo.clone_from(remote_repo.clone_url, target_dir)

    # Retrieve the PR refs.
    try:
        repo.remotes.origin.fetch([
            'pull/{pr}/head:pull/{pr}/head'.format(pr=pr_id),
            'pull/{pr}/merge:pull/{pr}/merge'.format(pr=pr_id)
        ])
        ref_head = repo.refs['pull/{pr}/head'.format(pr=pr_id)]
        ref_merge = repo.refs['pull/{pr}/merge'.format(pr=pr_id)]
    except GitCommandError:
        # Either `merge` doesn't exist because the PR was opened
        # in conflict or it is closed and it can't be the latter.
        repo.remotes.origin.fetch([
            'pull/{pr}/head:pull/{pr}/head'.format(pr=pr_id)
        ])
        ref_head = repo.refs['pull/{pr}/head'.format(pr=pr_id)]
    sha = str(ref_head.commit.hexsha)

    # Check if the tests are skipped via the commit message.
    skip_msgs = [
        "[ci skip]",
        "[skip ci]",
        "[admin skip]",
        "[skip admin]",
    ]
    commit_msg = repo.commit(sha).message
    should_skip = any([msg in commit_msg for msg in skip_msgs])
    if not force and should_skip:
        return {'status': 'skipped', 'message': 'skipped by commit msg',
                'sha': sha}

    # Raise an error if the PR is not mergeable.
    if not mergeable:
        message = textwrap.dedent("""
            Hi! I'm your friendly automated EMPD-admin bot!

            I was trying to test your data submission, but it appears we have a merge conflict.
            If you want me to fix this, just write
            `@EMPD-admin rebase`
            and I will rebase your pull request on the master branch of [EMPD2/EMPD-data](https://github.com/EMPD2/EMPD-data).

            Otherwise, please ping `@Chilipp` if you believe this is a bug.
            """)
        status = 'merge_conflict'

        test_info = {'message': message,
                     'status': status,
                     'sha': sha}

        return test_info

    ref_merge.checkout(force=True)
    return {}


def full_repo_test(local_repo, pr_id):
    local_repo = osp.join(local_repo, '')
    repo = Repo(local_repo)
    sha = repo.refs['pull/{pr}/head'.format(pr=pr_id)].commit.hexsha

    meta = get_meta_file(local_repo)
    results = OrderedDict()

    # run cricital tests
    results['Critical tests'] = crit_success, crit_log, crit_md = run_test(
        meta, '-m critical --tb=line --maxfail=20'.split())

    if crit_success:
        results['Formatting tests'] = run_test(
            meta, ['--maxfail=20', '--tb=line'], tests=['test_formatting.py'])
        results['Metadata tests'] = run_test(
            meta, ['--maxfail=20', '--tb=line'], tests=['test_meta.py'])

    test_summary = '\n\n'.join(
        textwrap.dedent("""
            ## {}..{}

            {}
            <details><summary>Full test report</summary>

            ```
            {}
            ```
            </details>""").format(
                key, "PASSED" if success else "FAILED",
                log.replace(local_repo, 'data/'),
                md.replace(local_repo, 'data/'))
        for key, (success, md, log) in results.items())

    good = textwrap.dedent("""
        Hi! I'm your friendly automated EMPD-admin bot!

        This is just to inform you that I tested your data submission in your PR (``%s``) and found it in an excellent condition!

        """ % osp.basename(meta))

    mixed = good + textwrap.dedent("""
        I just have some more information for you:

        """) + test_summary

    failed = textwrap.dedent("""
        Hi! I'm your friendly automated EMPD-admin bot!

        I found some errors in your data submission. You may fix some of them using the `@EMPD-admin fix` command.
        Please ping `@Chilipp` if you have difficulties with your submission.

        """) + test_summary
    if not all(t[0] for t in results.values()):
        status = 'failure'
        message = failed
    elif any(t[2] for t in results.values()):
        status = 'mixed'
        message = mixed
    else:
        status = 'good'
        message = good

    if status in ['mixed', 'good']:
        # test the import into postgres
        success, log, sql_dump = import_database(meta)
        if not success:
            message += '\n\n' + textwrap.dedent("""
                ## Postgres import

                I tried to import your data into the postgres database, but
                did not success!

                <details>

                ```
                {}
                ```
                </details>
                """).format(log.replace(local_repo, 'data/'))

    return {'message': message, 'status': status, 'sha': sha}


def comment_on_pr(owner, repo_name, pr_id, message, force=False,
                  onlyif='last'):
    gh = github.Github(os.environ['GH_TOKEN'])

    user = gh.get_user(owner)
    repo = user.get_repo(repo_name)
    issue = repo.get_issue(pr_id)

    if force:
        return issue.create_comment(message)

    comments = list(issue.get_comments())
    comment_owners = [comment.user.login for comment in comments]

    my_last_comment = None
    my_login = gh.get_user().login
    if my_login in comment_owners:
        my_comments = [comment for comment in comments
                       if comment.user.login == my_login]
        my_last_comment = my_comments[-1]
        if onlyif == 'last':
            # Only comment if we haven't before, or if the message we have is
            # different
            if my_last_comment is None or my_last_comment.body != message:
                my_last_comment = issue.create_comment(message)
        elif onlyif == 'any':
            # Only comment if there is not any other message like this
            if my_last_comment is None or all(
                    comment.body != message for comment in my_comments):
                my_last_comment = issue.create_comment(message)
    else:
        my_last_comment = issue.create_comment(message)

    return my_last_comment


def set_pr_status(owner, repo_name, test_info, target_url=None):
    gh = github.Github(os.environ['GH_TOKEN'])

    user = gh.get_user(owner)
    repo = user.get_repo(repo_name)
    if test_info:
        commit = repo.get_commit(test_info['sha'])
        if test_info['status'] == 'good':
            commit.create_status(
                "success", description="All data is excellent.",
                context="empd-admin-check", target_url=target_url)
        elif test_info['status'] == 'mixed':
            commit.create_status(
                "success", description="Some data have issues.",
                context="empd-admin-check", target_url=target_url)
        elif test_info['status'] == 'pending':
            commit.create_status(
                "pending", description="Waiting for tests to complete.",
                context='empd-admin-check', target_url=target_url)
        else:
            commit.create_status(
                "failure", description="Some data need some changes.",
                context="empd-admin-check", target_url=target_url)


def test_get_meta_file(local_repo):
    repo_dir = local_repo.working_dir
    assert get_meta_file(repo_dir) == osp.join(repo_dir, 'test.tsv')


def test_repo_test(pr_id, tmpdir):
    test_info = download_pr('EMPD2', 'EMPD-data', pr_id, tmpdir)

    assert not test_info

    test_info = full_repo_test(tmpdir, pr_id)

    assert test_info
    assert test_info['status'] == 'failure'
    # make sure all temporary paths have been removed
    assert 'tmp' not in test_info['message'], test_info['message']


def test_pr_info(pr_id, tmpdir):
    test_info = download_pr('EMPD2', 'EMPD-data', pr_id, tmpdir)

    assert not test_info

    test_info = pr_info(tmpdir, pr_id=pr_id)

    assert test_info
    assert test_info['status'] == 'pending'


def test_import_database(local_repo):
    repo_dir = local_repo.working_dir
    success, log, sql_dump = import_database(osp.join(repo_dir, 'test.tsv'))
    assert success, log
