import os
import time
import subprocess as spr

import github
import tempfile
import textwrap

from git import GitCommandError, Repo


def test_repo(repo_owner, repo_name, pr_id, ignore_base=False):
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

        return {'message': 'Ready to go', 'status': 'good', 'sha': sha}


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
                "success", description="All recipes are excellent.",
                context="conda-forge-linter", target_url=target_url)
        elif test_info['status'] == 'mixed':
            commit.create_status(
                "success", description="Some recipes have hints.",
                context="conda-forge-linter", target_url=target_url)
        else:
            commit.create_status(
                "failure", description="Some recipes need some changes.",
                context="conda-forge-linter", target_url=target_url)
