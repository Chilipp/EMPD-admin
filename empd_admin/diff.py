# module to compute the difference between two EMPD meta files
import os
import os.path as osp
import re
import textwrap
from urllib import request
import tempfile
import pandas as pd
from empd_admin.common import read_empd_meta
from git import Repo


# url regex from Django
url_regex = regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'   # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def diff(meta, left=None, right=None, output=None,
         commit=False, *args, **kwargs):
    local_repo = osp.dirname(meta)
    meta = osp.basename(meta)
    repo = Repo(local_repo)
    master_url = ('https://raw.githubusercontent.com/EMPD2/EMPD-data/'
                  'master/meta.tsv')
    if left is None:
        left = meta
    if right is None:
        if left == meta:
            base_meta = osp.join(local_repo, 'meta.tsv')
            if osp.samefile(meta, base_meta):
                right = master_url
            else:
                right = 'meta.tsv'
        elif left == 'meta.tsv':
            right = master_url
        else:
            right = meta
    if url_regex.match(left):
        with tempfile.TemporaryDirectory() as tmpdir:
            download_target = osp.join(tmpdir, 'meta.tsv')
            request.urlretrieve(left, download_target)
            left_df = read_empd_meta(download_target)
    else:
        left_df = read_empd_meta(osp.join(local_repo, left))

    if url_regex.match(right):
        with tempfile.TemporaryDirectory() as tmpdir:
            download_target = osp.join(tmpdir, 'meta.tsv')
            request.urlretrieve(right, download_target)
            right_df = read_empd_meta(download_target)
    else:
        right_df = read_empd_meta(osp.join(local_repo, right))

    diff = compute_diff(left_df, right_df, *args, **kwargs)

    if commit and not output:
        output = 'diff.tsv'
    if output:
        target = osp.join(local_repo, 'queries', output)
        if not osp.exists(osp.dirname(target)):
            os.makedirs(osp.dirname(target))
        diff.to_csv(target, '\t', float_format='%1.8g')
    if commit:
        repo.index.add([osp.join('queries', output)])
        repo.index.commit(f"Added diff between {left} and {right}")

    diff.reset_index(inplace=True)

    diff = pd.concat([
        pd.DataFrame([('---', ) * len(diff.columns)], columns=diff.columns),
        diff], ignore_index=True)

    ret = f'<details><summary>{left}..{right}</summary>\n\n' + textwrap.indent(
        diff.head(200).to_csv(sep='|', index=False, float_format='%1.8g'),
        '| ')
    ret += '\n\nDisplaying %i of %i rows' % (min(len(diff) - 1, 200),
                                             len(diff) - 1)

    return output, ret


def compute_diff(left, right, how='inner', on=None, columns='leftdiff'):
    left = left.copy()
    right = right.copy()

    left['left'] = True
    right['right'] = True
    merged = left.merge(right, how=how, left_index=True, right_index=True,
                        suffixes=['', '_y'])
    if on is None:
        on = [col for col in left.columns if col in right.columns]
    changed = []
    merged['diff'] = ''
    valid_left = merged.left.notnull()
    valid_right = merged.right.notnull()
    merged.loc[~valid_left, 'diff'] += 'missing in right,'
    merged.loc[~valid_right, 'diff'] += 'missing in left,'

    for col in on:
        diff = (merged[col].notnull() & merged[col + '_y'].notnull() &
                (merged[col] != merged[col + '_y']))
        diff |= merged[col].isnull() & merged[col + '_y'].notnull()
        diff |= merged[col].notnull() & merged[col + '_y'].isnull()
        diff &= valid_left & valid_right
        if diff.any():
            changed.append(col)
            merged.loc[diff, 'diff'] += col + ','

    merged = merged[merged['diff'].astype(bool)]
    # remove the last comma
    merged['diff'] = merged['diff'].str.slice(0, -1)

    if isinstance(columns, str):
        columns = [columns]

    if 'leftdiff' in columns:
        columns = changed
    elif 'left' in columns:
        columns = left.columns.tolist()
    elif 'right' in columns:
        columns = [(col + '_y' if col in merged.columns else col)
                   for col in right.columns]
    elif 'rightdiff' in columns:
        columns = [col + '_y' for col in changed]
    elif 'inner' in columns:
        columns = [col for col in left.columns if col in right.columns]
    columns = [(col + '_y' if col not in merged.columns else col)
               for col in columns]
    return merged[columns + ['diff']].rename(
        {col: col[:-2] for col in columns if col.endswith('_y')})


def test_diff():
    from pandas.testing import assert_frame_equal
    left = pd.DataFrame([[1, 2, 3], [3, 4, 5]], index=[1, 2],
                        columns=list('abc'))
    right = pd.DataFrame([[1, 2], [4, 4]], index=[1, 2], columns=list('ab'))
    diff = compute_diff(left, right)
    assert_frame_equal(diff, pd.DataFrame([[3, 'a']], columns=['a', 'diff'],
                                          index=[2]))
