# module to compute the difference between two EMPD meta files
import os
import os.path as osp
import re
import textwrap
from urllib import request
import tempfile
import pandas as pd
import numpy as np
from empd_admin.common import read_empd_meta, NUMERIC_COLS
from git import Repo


# url regex from Django
url_regex = regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'   # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def diff(meta, left=None, right=None, output=None, commit=False, *args,
         **kwargs):
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


def compute_diff(left, right, how='inner', on=None, exclude=[],
                 columns='leftdiff', atol=1e-3):
    left = left.copy()
    right = right.copy()

    left['left'] = True
    right['right'] = True
    merged = left.merge(right, how=how, left_index=True, right_index=True,
                        suffixes=['', '_r'])
    if on is None:
        on = [col for col in left.columns if col in right.columns]
    on = [col for col in on if col not in exclude]
    changed = []
    merged['diff'] = ''
    valid_left = merged.left.notnull()
    valid_right = merged.right.notnull()
    merged.loc[~valid_left, 'diff'] += 'missing in right,'
    merged.loc[~valid_right, 'diff'] += 'missing in left,'

    for col in on:
        if col in NUMERIC_COLS:
            diff = (merged[col].notnull() & merged[col + '_r'].notnull() &
                    (~np.isclose(merged[col], merged[col + '_r'], atol=atol)))
        elif col in ['Temperature', 'Precipitation']:
            s1 = np.array(merged[col].str.split(',').apply(np.array).tolist(),
                          dtype=float)
            s2 = np.array(
                merged[col + '_r'].str.split(',').apply(np.array).tolist(),
                dtype=float)
            diff = ((~np.isnan(s1)) & (~np.isnan(s1)) &
                    (~np.isclose(s1, s2, atol=atol))).any(axis=1)
        else:
            diff = (merged[col].notnull() & merged[col + '_r'].notnull() &
                    (merged[col] != merged[col + '_r']))
        diff |= merged[col].isnull() & merged[col + '_r'].notnull()
        diff |= merged[col].notnull() & merged[col + '_r'].isnull()
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
    elif 'rightdiff' in columns:
        columns = [col + '_r' for col in changed]
    elif 'right' in columns:
        columns = [(col + '_r' if col in merged.columns else col)
                   for col in right.columns]
    elif 'inner' in columns:
        columns = [col for col in left.columns if col in right.columns]
    elif 'bothdiff' in columns:
        columns = changed + [col + '_r' for col in changed
                             if col + '_r' in merged.columns]
    elif 'both' in columns:
        columns = merged.columns

    columns = [(col + '_r' if col not in merged.columns else col)
               for col in columns]
    ref_cols = [col.replace('_r', '') for col in merged.columns]
    columns.sort(key=lambda col: (ref_cols.index(col.replace('_r', '')), col))
    ret = merged[columns + ['diff']]
    if 'right' in columns or 'rightdiff' in columns:
        ret = ret.rename(columns={
            col: col[:-2] for col in columns if col.endswith('_r')})
    return ret


def test_diff():
    from pandas.testing import assert_frame_equal
    left = pd.DataFrame([[1, 2, 3], [3, 4, 5]], index=[1, 2],
                        columns=list('abc'))
    right = pd.DataFrame([[1, 2], [4, 4]], index=[1, 2], columns=list('ab'))
    diff = compute_diff(left, right)
    assert_frame_equal(diff, pd.DataFrame([[3, 'a']], columns=['a', 'diff'],
                                          index=[2]))