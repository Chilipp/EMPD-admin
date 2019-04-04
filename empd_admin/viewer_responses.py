"""Module to handle requests from the EMPD2.github.io viewer"""
import os
import os.path as osp
import io
import github
import tempfile
import pandas as pd
from git import Repo
from empd_admin.repo_test import comment_on_pr
import textwrap


def handle_viewer_request(metadata, submitter, repo='EMPD2/EMPD-data',
                          branch='master', meta='meta.tsv', submitter_gh=None):
    # read the meta data json
    metadata = pd.DataFrame.from_dict(
        {d.pop('SampleName'): d for d in metadata}, 'index')
    metadata.index.name = 'SampleName'

    # write the data frame and load it again to have a consistent dump
    with tempfile.TemporaryDirectory() as d2:
        metadata.to_csv(osp.join(d2, 'tmp.tsv'), sep='\t')
        metadata = pd.read_csv(osp.join(d2, 'tmp.tsv'), sep='\t',
                               index_col='SampleName')

    if repo == 'EMPD2/EMPD-data' and branch == 'master':
        return create_new_pull_request(metadata, submitter, submitter_gh)
    # check if we can find an existing pull request for the given repository
    pulls = github.Github(os.environ['GH_TOKEN']).get_repo(
        'EMPD2/EMPD-data').get_pulls()
    for pull in pulls:
        if (pull.state == 'open' and pull.head.repo.full_name == repo and
                pull.head.label.split(':')[1] == branch):
            return edit_pull_request(
                pull, meta, metadata, submitter, submitter_gh)

    return False, f"Could not find an open pull request for {repo}:{branch}"


def create_new_pull_request(metadata, submitter, submitter_gh=None):
    """Create a new branch and pull request with the given metadata"""
    return False, "Edits from EMPD2/EMPD-data:master are not yet supported"


def edit_pull_request(pull, meta, metadata, submitter, submitter_gh=None,
                      commit=True):
    """Edit the meta data of an existing pull request"""
    full_repo = pull.head.repo.full_name
    remote_url = f'https://github.com/{full_repo}.git'
    branch = pull.head.label.split(':')[1]
    if not pull.labels or not any(
            l.name == 'viewer-editable' for l in pull.labels):
        return False, (
            f"Pull request {pull.number} for {full_repo}:{branch} is not "
            "marked as editable. To change this, post a new comment in the "
            f"<a href='{pull.html_url}' target='_blank'>PR</a> with "
            "<code>@EMPD-admin allow-edits</code></a>")

    with tempfile.TemporaryDirectory('_empd') as tmpdir:
        repo = Repo.clone_from(remote_url, tmpdir, branch=branch)
        old_meta = pd.read_csv(osp.join(tmpdir, meta), '\t',
                               index_col='SampleName')
        save_meta = old_meta.copy(True)
        cols = [col for col in metadata.columns if col in old_meta.columns]
        old_meta.loc[metadata.index, cols] = metadata
        n = len(metadata)
        nsamples = '%i sample%s' % (n, 's' if n > 1 else '')
        if old_meta.shape == save_meta.shape and old_meta.equals(save_meta):
            return False, "No data has been edited."
        else:
            old_meta.to_csv(osp.join(tmpdir, meta), sep='\t')
            repo.index.add([meta])
            repo.index.commit(
                f"Updated {nsamples} in {meta} as requested by "
                f"{submitter}")
            remote_url = ('https://EMPD-admin:%s@github.com/'
                          f'{full_repo}.git')
            remote = repo.create_remote(
                'push_remote',
                remote_url % os.environ['GH_TOKEN'])
            if commit:
                remote.push(branch)
    pr_owner = '@' + pull.user.login
    uri = pull.html_url
    if submitter_gh and '@' + submitter_gh != pr_owner:
        pr_owner += ' and @' + submitter_gh
    pr_msg = (
       f"Dear {pr_owner}, I just updated {nsamples} in your {meta} file "
       f"as requested via [EMPD2.github.io](https://empd2.github.io/) by "
       f"{submitter}.\n"
       f"If you believe that this is a bug or has been a wrong edit: "
       f"Please ping `@Chilipp`.")
    if commit:
        comment = comment_on_pr('EMPD2', 'EMPD-data', pull.number, pr_msg,
                                force=True)
        uri = comment.html_url

    return True, (f'Successfully pushed {nsamples} into {full_repo}/{meta} '
                  f'and PR <a href="{uri}" title="PR #{pull.number}: {pull.title}">'
                  f'#{pull.number}</a>.')
