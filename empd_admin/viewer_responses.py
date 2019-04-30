"""Module to handle requests from the EMPD2.github.io viewer"""
import os
import os.path as osp
import json
import github
import tempfile
import pandas as pd
import numpy as np
from git import Repo, GitCommandError
import hmac
import yaml
from empd_admin.repo_test import comment_on_pr
from empd_admin.common import read_empd_meta


def transform_list(items):
    if isinstance(items, str):
        return items.replace('[', '').replace(']', '')
    items = [item if item is not None else np.nan
             for item in items]
    return ','.join(map('{:1.8g}'.format, map(float, items)))


def handle_viewer_request(metadata, submitter, repo='EMPD2/EMPD-data',
                          branch='master', meta='meta.tsv', submitter_gh=None,
                          commit_msg=''):
    # read the meta data json
    metadata = pd.DataFrame.from_dict(
        {d.pop('SampleName'): d for d in metadata}, 'index')
    if 'Temperature' in metadata.columns:
        metadata['Temperature'] = metadata.Temperature.apply(transform_list)
    if 'Precipitation' in metadata.columns:
        metadata['Precipitation'] = metadata.Precipitation.apply(
            transform_list)
    metadata.index.name = 'SampleName'

    # write the data frame and load it again to have a consistent dump
    with tempfile.TemporaryDirectory() as d2:
        metadata.to_csv(osp.join(d2, 'tmp.tsv'), sep='\t',
                        float_format='%1.8g')
        metadata = read_empd_meta(osp.join(d2, 'tmp.tsv'))

    if repo == 'EMPD2/EMPD-data' and branch == 'master':
        return create_new_pull_request(metadata, submitter, submitter_gh,
                                       commit_msg)
    # check if we can find an existing pull request for the given repository
    pulls = github.Github(os.environ['GH_TOKEN']).get_repo(
        'EMPD2/EMPD-data').get_pulls()
    for pull in pulls:
        if (pull.state == 'open' and pull.head.repo.full_name == repo and
                pull.head.label.split(':')[1] == branch):
            return edit_pull_request(
                pull, meta, metadata, submitter, submitter_gh,
                commit_msg)

    return False, f"Could not find an open pull request for {repo}:{branch}"


def create_new_pull_request(metadata, submitter, submitter_gh=None,
                            commit_msg=''):
    """Create a new branch and pull request with the given metadata"""
    return False, "Edits from EMPD2/EMPD-data:master are not yet supported"


def edit_pull_request(pull, meta, metadata, submitter, submitter_gh=None,
                      commit_msg='', commit=True):
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
        old_meta = read_empd_meta(osp.join(tmpdir, meta))
        save_meta = old_meta.copy(True)
        cols = [col for col in metadata.columns if col in old_meta.columns]
        old_meta.loc[metadata.index, cols] = metadata
        n = len(metadata)
        nsamples = '%i sample%s' % (n, 's' if n > 1 else '')
        if old_meta.shape == save_meta.shape and old_meta.equals(save_meta):
            return False, "No data has been edited."
        else:
            old_meta.to_csv(osp.join(tmpdir, meta), sep='\t',
                            float_format='%1.8g')
            repo.index.add([meta])
            commit_msg += '\n\n' if commit_msg else ''
            repo.index.commit(
                commit_msg +
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


def handle_issue_submission(body):
    import datetime as dt
    remote_url = ('https://EMPD-admin:%s@github.com/'
                  'Chilipp/EMPD-issues.git')
    token = hmac.new(os.urandom(1024), body, 'sha1')
    with tempfile.TemporaryDirectory('_empd') as tmpdir:
        repo = Repo.clone_from(remote_url % os.environ['GH_TOKEN'], tmpdir)
        branch = 'issue_' + token.hexdigest()
        repo.git.branch(branch)
        repo.git.checkout(branch)
        with open(osp.join(tmpdir, 'body'), 'wb') as f:
            f.write(body)
        with open(osp.join(tmpdir, 'info.yml'), 'w') as f:
            yaml.dump({'submitted': dt.datetime.now().isoformat()}, f,
                      default_flow_style=False)
        repo.index.add(['body', 'info.yml'])
        repo.index.commit('Added body from issue submission')
        repo.git.push('origin', branch)

    return token


def handle_verified_issue(token):

    def commit_info(msg):
        with open(osp.join(tmpdir, 'info.yml'), 'w') as f:
            yaml.dump(info, f, default_flow_style=False)
        repo.index.add(['info.yml'])
        repo.index.commit(msg)
        try:
            repo.git.push('origin', branch)
        except GitCommandError:
            return ("Failed to process the request (probably there are "
                    f"multiple requests for {token})")

    import datetime as dt
    remote_url = ('https://EMPD-admin:%s@github.com/'
                  'Chilipp/EMPD-issues.git')

    with tempfile.TemporaryDirectory('_empd') as tmpdir:
        branch = 'issue_' + token
        try:
            repo = Repo.clone_from(
                remote_url % os.environ['GH_TOKEN'], tmpdir, branch=branch)
        except GitCommandError:
            return False, f"Could not find a submission for {token}"
        with open(osp.join(tmpdir, 'info.yml')) as f:
            info = yaml.load(f)
        if 'processed' in info:
            if "url" in info:
                url = info['url']
                num = info['num']
                return False, (
                    f"The issue for {token} has already been opened "
                    f"as issue <a href='{url}'>#{num}</a>")
            return False, f"The issue for {token} is already processing."
        td = dt.datetime.now() - dt.datetime.fromisoformat(info['submitted'])
        if td > dt.timedelta(1):
            return False, (
                "The issue has been submitted more than 24 hours ago. Please "
                "resubmit through "
                "<a href='https://EMPD2.github.io'>EMPD2.github.io</a>.")
        info['processed'] = dt.datetime.now().isoformat()
        msg = commit_info('Added processed time')
        if msg:
            return False, msg
        with open(osp.join(tmpdir, 'body'), 'rb') as f:
            body = json.loads(f.read(), strict=False)
        title = body['issue_title']
        msg = body['issue_msg']
        submitter = (body['submitter_firstname'] + ' ' +
                     body['submitter_lastname'])

        if body.get('submitter_username'):
            submitter += ' (@{submitter_username})'.format(**body)

        msg += ("\n\n"
                "<sub>This issue has been submitted via EMPD2.github.io by "
                f"{submitter}</sub>")
        issue = submit_issue(title, msg)
        info['url'] = issue.html_url
        info['num'] = issue.number

        msg = commit_info('Added issue number and url')
        if msg:
            return False, msg

        return True, (
            "Thanks for your submission! The issue has been opened as number "
            f"<a href={issue.html_url}>#{issue.number}</a>.")


def submit_issue(title, msg):
    gh = github.Github(os.environ['GH_TOKEN'])

    repo = gh.get_repo('EMPD2/EMPD-data')
    issue = repo.create_issue(title, msg)
    return issue
