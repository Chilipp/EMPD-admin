import os
import os.path as osp
import contextlib
import time
import subprocess as spr

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
    return osp.join(dirname, meta or 'meta.tsv')


def run_test(meta, pytest_args=[], tests=['']):
    with remember_env('PYTHONUNBUFFERED'):
        with tempfile.TemporaryDirectory('_test') as report_dir:
            os.environ['PYTHONUNBUFFERED'] = '1'  # turn off output buffering
            cmd = ['pytest', '-v',
                   '--empd-meta=' + meta,
                   '--markdown-report=' + osp.join(report_dir, 'report.md')
                   ] + pytest_args + [osp.join(TESTDIR, f) for f in tests]
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

    return success, stdout.decode('utf-8'), md_report


def repo_test(repo_owner, repo_name, pr_id, ignore_base=False):
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

    with tempfile.TemporaryDirectory('_empd') as tmp_dir:
        repo = Repo.clone_from(remote_repo.clone_url, tmp_dir)

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
            "[lint skip]",
            "[skip lint]",
        ]
        commit_msg = repo.commit(sha).message
        should_skip = any([msg in commit_msg for msg in skip_msgs])
        if should_skip:
            return {}        # Raise an error if the PR is not mergeable.

        if not mergeable:
            message = textwrap.dedent("""
                Hi! This is the friendly automated EMPD service.

                I was trying to test your data submission, but it appears we have a merge conflict.
                Please try to merge or rebase with the base branch to resolve this conflict.

                Please ping the 'Chilipp' (using the @ notation in a comment) if you believe this is a bug.
                """)
            status = 'merge_conflict'

            test_info = {'message': message,
                         'status': status,
                         'sha': sha}

            return test_info

        ref_merge.checkout(force=True)

        meta = get_meta_file(tmp_dir)
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
                ## {}

                {}
                <details><summary>Full test report</summary>

                ```
                {}
                ```
                </details>""").format(key, log, md)
            for key, (succes, md, log) in results.items())

        good = textwrap.dedent("""
            Hi! I'm your friendly automated EMPD-admin bot!

            This is just to inform you that I tested your data submission in your PR (``%s``) and found it in an excellent condition!

            """ % meta)

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


def comment_on_pr(owner, repo_name, pr_id, message, force=False):
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
        my_last_comment = [comment for comment in comments
                           if comment.user.login == my_login][-1]

    # Only comment if we haven't before, or if the message we have is different
    if my_last_comment is None or my_last_comment.body != message:
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
        else:
            commit.create_status(
                "failure", description="Some data need some changes.",
                context="empd-admin-check", target_url=target_url)


def test_get_meta_file(local_repo):
    repo_dir = local_repo.working_dir
    assert get_meta_file(repo_dir) == osp.join(repo_dir, 'test.tsv')


def test_repo_test(pr_id):
    test_info = repo_test('EMPD2', 'EMPD-data', pr_id)

    assert test_info
    assert test_info['status'] == 'failure'
