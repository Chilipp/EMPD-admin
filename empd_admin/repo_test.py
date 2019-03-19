import os
import os.path as osp
import contextlib
import time
import subprocess as spr
import shutil

import github
import tempfile
import textwrap
from collections import OrderedDict

from git import GitCommandError, Repo


TESTDIR = osp.join(osp.dirname(__file__), 'data-tests')


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


def get_meta_file(dirname='.'):
    if not osp.exists(osp.join(dirname, 'meta.tsv')):
        raise ValueError(
            dirname + " does not seem to look like an EMPD-data repo!")
    with remember_cwd():
        os.chdir(dirname)
        files = [f for f in os.listdir('.')
                 if osp.isfile(f) and not f.startswith('.')]
        cmd = 'git diff origin/master --name-only --diff-filter=A'.split()
        meta = spr.check_output(cmd + files).decode('utf-8').strip()
        if meta:
            return '\n'.join(osp.join(dirname, f) for f in meta.splitlines())

    return osp.join(dirname, 'meta.tsv')


def run_test(meta, pytest_args=[], tests=['']):
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
            cmd = [os.getenv('PYTEST', 'pytest'), '-v',
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

    return (success,
            stdout.decode('utf-8').replace(report_dir, TESTDIR),
            md_report.replace(report_dir, TESTDIR))


def pr_info(local_repo, pr_owner=None, pr_repo=None, pr_branch=None):
    repo = Repo(local_repo)
    sha = repo.head.commit.hexsha

    meta = get_meta_file(local_repo)

    if len(meta.splitlines()) > 1:
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
        Type `@EMPD-admin --help` in a new comment in this PR for usage information.

        <sub>Make sure, that all the commands for the `@EMPD-admin` are on one single line and nothing else. Only
        `@EMPD-admin --help`
        will work, not something like
        `<other words> @EMPD-admin --help`
        or
        `@EMPD-admin --help <other words>`

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
            Please try to merge or rebase with the base branch to resolve this conflict.

            Please ping `@Chilipp` if you believe this is a bug.
            """)
        status = 'merge_conflict'

        test_info = {'message': message,
                     'status': status,
                     'sha': sha}

        return test_info

    ref_merge.checkout(force=True)
    return {}


def full_repo_test(local_repo):
    local_repo = osp.join(local_repo, '')
    repo = Repo(local_repo)
    sha = repo.head.commit.hexsha

    meta = get_meta_file(local_repo)
    results = OrderedDict()

    # run cricital tests
    results['Critical tests'] = crit_success, crit_log, crit_md = run_test(
        meta, '-m critical'.split())

    if crit_success:
        results['Formatting tests'] = run_test(
            meta, tests=['test_formatting.py'])
        results['Metadata tests'] = run_test(
            meta, tests=['test_meta.py'])

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
    elif any(t[1] for t in results.values()):
        status = 'mixed'
        message = mixed
    else:
        status = 'good'
        message = good

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

    test_info = full_repo_test(tmpdir)

    assert test_info
    assert test_info['status'] == 'failure'


def test_pr_info(pr_id, tmpdir):
    test_info = download_pr('EMPD2', 'EMPD-data', pr_id, tmpdir)

    assert not test_info

    test_info = pr_info(tmpdir)

    assert test_info
    assert test_info['status'] == 'pending'
