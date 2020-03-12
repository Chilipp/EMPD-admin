# module to compute the difference between two EMPD meta files
import os
import os.path as osp
import re
import textwrap
from urllib import request
import tempfile
import pandas as pd
import numpy as np
from empd_admin.common import read_empd_meta, NUMERIC_COLS, dump_empd_meta
from git import Repo


# url regex from Django
url_regex = regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'   # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def diff(meta, left=None, right=None, output=None, commit=False,
         maxdiff=200, *args, **kwargs):
    """Compute the diff between two EMPD metadata files

    This function computes the difference between two EMPD-data files using the
    :func:`compute_diff` function. It takes the meta data of an EMPD-data
    repository and compares it to another

    Parameters
    ----------
    meta: str
        The path to the tab-delimited meta data of a cloned EMPD-data
        repository
    left: str
        The path to the first meta data file, relative to the directory of
        `meta`. Alternatively it can also be a url. If `left` is None, the
        `meta` will be used
    right: str
        The path to the second meta data file, relative to the directory of
        `meta`. Alternatively it can also be a url. If `right` is None, the
        `meta` will be used, or (if `left` is the same as `meta` or None),
        the meta data of the EMPD2/EMPD-data repository at
        https://raw.githubusercontent.com/EMPD2/EMPD-data/master/meta.tsv
        is used.
    output: str
        The filename to use for saving the diff. If set, it will be saved in
        the ``'queries'`` directory, relative to `meta`. If not set but
        `commit` is True, it will be saved to ``'queries/diff.tsv'``.
    commit: bool
        If True, commit the added `output` to the git repository of `meta`
    maxdiff: int
        The maximum number of lines for the diff
    ``*args,**kwargs``
        Any other parameter for the :func:`compute_diff` function

    Returns
    -------
    str
        The path where the data has been saved (if `output` is set or `commit`
        is True)
    str
        The computed difference as markdown table

    Examples
    --------
    For a data contribution, e.g. the test-data branch, you can compute the
    difference to the EMPD meta.tsv via::

        import git
        git.Repo.clone_from('https://github.com/EMPD2/EMPD-data',
                            branch='test-data')
        diff('EMPD-data/test.tsv')

    which is essentially the same as::

        diff('EMPD-data/test.tsv', 'test.tsv', 'meta.tsv')

    You will reveive nothing, however, because `how` is set to ``'inner'`` and
    ``'test.tsv'`` contains new samples. Instead, you can set `how` to
    ``'left'`` to include the samples of ``'test.tsv'`` that are not in
    ``'meta.tsv'``::

        diff('EMPD-data/test.tsv', how='left')
    """
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
        dump_empd_meta(diff, target)
    if commit:
        repo.index.add([osp.join('queries', output)])
        repo.index.commit(f"Added diff between {left} and {right}")

    diff.reset_index(inplace=True)

    diff = pd.concat([
        pd.DataFrame([('---', ) * len(diff.columns)], columns=diff.columns),
        diff], ignore_index=True)

    ret = f'<details><summary>{left}..{right}</summary>\n\n' + textwrap.indent(
        dump_empd_meta(diff.head(maxdiff), sep='|'),
        '| ')
    ret += '\n\nDisplaying %i of %i rows' % (min(len(diff) - 1, maxdiff),
                                             len(diff) - 1)

    return output, ret


def compute_diff(left, right, how='inner', on=None, exclude=[],
                 columns='leftdiff', atol=1e-3):
    """Compute the difference between two EMPD meta dataframes

    Parameters
    ----------
    left: pandas.DataFrame
        The first EMPD-data metadata (see
        :func:`~empd_admin.common.read_empd_meta`)
    right: pandas.DataFrame
        The second EMPD-data metadata(see
        :func:`~empd_admin.common.read_empd_meta`).
    how: str
        How to merge `right` into `left`. Possiblities are

        inner (default)
            use intersection of samples from both frames, similar to a SQL
            inner join; preserve the order of the left keys.
        outer
            use union of samples from both frames, similar to a SQL full outer
            join; sort keys lexicographically.
        left
            use only samples from left frame, similar to a SQL left outer join;
            preserve key order.
        right
            use only samples from right frame, similar to a SQL right outer
            join; preserve key order.
    on: list of str
        The names of the columns to compute the diff on. If None, we use the
        intersection of columns between `left` and `right.`
    exclude: list of str
        Columns names that should be excluded in the diff.
    columns: str or list of str
        The columns of the returned dataframe. It can either be a list of
        column names to use or one of

        leftdiff (default)
            To use the columns from `left` that differ from `right`
        left
            To use all columns from `left`
        rightdiff
            To use the columns from `right` that differ from `left`
        right
            To use all columns from `right`
        inner
            To use the intersection of `left` and `right`
        bothdiff
            To use the differing columns from `right` and `left` (columns from
            `right` are suffixed with an ``'_r'``)
        both
            To use all columns from `left` and `right` (columns from `right`
            are suffixed with an ``'_r'``)

        In any of these cases (except if you specify the column names
        explicitly), the columns the data frame will include a ``diff`` column
        that contains for each sample the columns names of the differing cells.
    atol: float
        Absolute tolerance to use for numeric columns (see the
        :attr:`empd_admin.common.NUMERIC_COLS`).

    Returns
    -------
    pandas.DataFrame
        The dataframe highlighting the difference between `left` and `right`.
        The index is the sample name, the colums are determined by the
        `columns` parameter"""

    def is_iterable(l):
        try:
            iter(l)
        except (TypeError, ValueError):
            return False
        return True

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
    merged.loc[~valid_left, 'diff'] += 'missing in left,'
    merged.loc[~valid_right, 'diff'] += 'missing in right,'

    for col in on:
        lcol = merged[col]
        rcol = merged[col + '_r']
        if col in NUMERIC_COLS:
            lcol = lcol.replace('', 'nan').astype(float)
            rcol = rcol.replace('', 'nan').astype(float)
            diff = (lcol.notnull() & rcol.notnull() &
                    (~np.isclose(lcol, rcol, atol=atol)))
        elif col in ['Temperature', 'Precipitation']:
            s1 = np.array(lcol.str.split(',').apply(np.array).apply(
                    lambda l: ([np.nan] * 17 if not is_iterable(l)
                               else l)).tolist(),
                          dtype=float)
            s2 = np.array(
                rcol.str.split(',').apply(np.array).apply(
                    lambda l: ([np.nan] * 17 if not is_iterable(l)
                               else l)).tolist(),
                dtype=float)
            diff = ((~np.isnan(s1)) & (~np.isnan(s1)) &
                    (~np.isclose(s1, s2, atol=atol))).any(axis=1)
        else:
            if (hasattr(merged[col], 'str') and hasattr(left[col], 'str') and
                    hasattr(right[col], 'str')):
                lcol = lcol.str.strip().str.replace('\n', ' ')
                rcol = rcol.str.strip().str.replace('\n', ' ')
            diff = (lcol.notnull() & rcol.notnull() & (lcol != rcol))
        diff |= lcol.isnull() & rcol.notnull()
        diff |= lcol.notnull() & rcol.isnull()
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
    """Test function for :func:`compute_diff`"""
    from pandas.testing import assert_frame_equal
    left = pd.DataFrame([[1, 2, 3], [3, 4, 5]], index=[1, 2],
                        columns=list('abc'))
    right = pd.DataFrame([[1, 2], [4, 4]], index=[1, 2], columns=list('ab'))
    diff = compute_diff(left, right)
    assert_frame_equal(diff, pd.DataFrame([[3, 'a']], columns=['a', 'diff'],
                                          index=[2]))
