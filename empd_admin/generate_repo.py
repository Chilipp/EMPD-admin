"""Module to generate the EMPD-data repository from the postgres database

This module defines the db2folder function that generates the EMPD-data
repository out of the postgres database"""


# Fill the EMPD-data repository from the postgres database on the server

# This script requires port-forwarding to connect to the database server::

#     ssh -L 63333:localhost:5432 fgse-davis01.unil.ch

from git import Repo
from empd_admin.repo_test import temporary_database
import tempfile
from empd_admin.common import read_empd_meta, dump_empd_meta
from empd_admin.diff import compute_diff
import sqlalchemy
import subprocess as spr

import os.path as osp
import numpy as np
import pandas as pd


def fill_repo(meta, db_url, root_db=None, dry_run=False,
              meta_data=True, count_data=True, keep=None,
              how='left', on=None, exclude=[], columns='left', atol=1e-3):
    """Fill the EMPD-data repo with the database in the given URL

    Parameters
    ----------
    meta: str
        The path where to save the data
    db_url: str
        The url where the postgres database can be accessed. Note that we
        expect this database to have a ``'metaViewer'`` table
    root_db: str
        The url where the EMPD2 postgres database can be accessed. This
        parameter is only necessary where ``how != 'left-only'``
    dry_run: bool
        If True, do not create any file but only report what would have been
        saved
    meta_data: bool
        If True (default), dump the meta data into `meta`
    count_data: bool
        If True (default), dump the pollen counts in the corresponding file
        of the sample
    keep: list
        Columns to keep from the `root_df`
    how: str
        How to merge the `root` meta data into the new one. Possiblities are

        inner
            use intersection of samples from both frames, similar to a SQL
            inner join; preserve the order of the left keys.
        outer
            use union of samples from both frames, similar to a SQL full outer
            join; sort keys lexicographically.
        left (default)
            use only samples from the new frame, similar to a SQL left outer
            join; preserve key order.
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
    str
        The markdown formatted report
    list
        The filenames that have changed (or would have been changed, if
        `dry_run` is True)"""
    engine = sqlalchemy.create_engine(
        db_url, poolclass=sqlalchemy.pool.NullPool)

    outdir = osp.dirname(meta)

    exclude = list(exclude) + ['var_', 'acc_var_']

    meta_df = pd.read_sql('metaViewer', engine)

    climate = pd.read_sql('climate', engine)
    climate['Temperature'] = list(map(
        ','.join, climate.iloc[:, 1:18].values.astype(str)))
    climate['Precipitation'] = list(map(
        ','.join, climate.iloc[:, 18:-1].values.astype(str)))

    meta_df = meta_df.merge(
        climate[['samplename', 'Temperature', 'Precipitation']].rename(
            columns={'samplename': 'SampleName'}), on='SampleName', how='left')

    meta_df.set_index('SampleName', inplace=True)

    # save meta data and load it again to make sure we have a consistent table
    with tempfile.NamedTemporaryFile(suffix='_empd.tsv') as f:
        dump_empd_meta(meta_df, f.name)
        meta_df = read_empd_meta(f.name)

    if 'okexcept' not in meta_df:
        meta_df['okexcept'] = ''

    files = []
    message = ""

    if how != 'left-only':
        diff_kws = dict(how=how, on=on, exclude=exclude, columns=columns,
                        atol=atol)
        root_df = read_empd_meta(osp.join(outdir, 'meta.tsv'))
        meta_df = compute_diff(meta_df, root_df, **diff_kws)
        if keep:
            meta_df.loc[:, keep] = meta_df[[]].join(root_df[keep], how='left')
    if meta_data and len(meta_df):
        files += [meta]
        if not dry_run:
            dump_empd_meta(meta_df, meta)
        message = f"Dumped {meta_df.shape[0]} lines to {osp.basename(meta)}."
    else:
        message = "No meta data has changed."

    if count_data:
        engine = sqlalchemy.create_engine(
            db_url, poolclass=sqlalchemy.pool.NullPool)
        counts = pd.read_sql_query(
            'SELECT * FROM p_counts LEFT JOIN p_vars USING (var_)', engine,
            index_col=['samplename', 'original_varname'])

        if how != 'left-only':
            engine = sqlalchemy.create_engine(
                root_db, poolclass=sqlalchemy.pool.NullPool)
            root_counts = pd.read_sql_query(
                'SELECT * FROM p_counts LEFT JOIN p_vars USING (var_)', engine,
                index_col=['samplename', 'original_varname'])
            diff = compute_diff(counts, root_counts, **diff_kws)
            changed = np.unique(diff.index.get_level_values(0))
            files.extend(map('samples/{}.tsv'.format, changed))

            if not dry_run:
                for key, group in counts.reset_index(-1).loc[changed].groupby(
                        level=0):
                    target = osp.join(outdir, 'samples', f'{key}.tsv')
                    dump_empd_meta(group, target)
        else:
            changed = np.unique(counts.index.get_level_values(0))
            files.extend(map('samples/{}.tsv'.format, changed))
            if not dry_run:
                for key, group in counts.groupby(level=0):
                    target = osp.join(outdir, 'samples', f'{key}.tsv')
                    dump_empd_meta(group, target)

    if count_data:
        message += f" Changed {len(changed)} count files."

    if dry_run:
        message += '\n\nNo action has been performed because it was a dry run.'

    return message, files


def db2repo(meta, postgres_dump, commit=False, output=None,
            dry_run=False, *args, **kwargs):
    """Generate the EMPD-data repository out of a `postgres_dump`

    Parameters
    ----------
    meta: str
        The path to the local EMPD2 meta data file
    postgres_dump: str
        The path to the postgres file (relative to `meta`). This dump must
        define a `metaViewer` table that contains the new meta data
    commit: bool
        If True, commit the added files
    output: str
        The path where to save the new meta data. If this is None, the
        following cases are considered:

        1. `meta` is ``'meta.tsv'``: `output` will be set to ``'update.tsv'``
        2. `meta` is anything else: `output` will be set to `meta`
    dry_run: bool
        If True, do not create any file but only report what would have been
        saved

    Returns
    -------
    str
        The markdown formatted report"""
    basedir = osp.dirname(meta)

    local_repo = osp.dirname(meta)
    meta = osp.basename(meta)
    repo = Repo(local_repo)

    if output is None:
        output = osp.basename(meta)

    if output == 'meta.tsv':
        output = 'update.tsv'

    with temporary_database() as db_url:
        spr.check_call(['psql', db_url, '-q', '-f',
                        osp.join(basedir, postgres_dump)],
                       stdout=spr.DEVNULL)
        with temporary_database() as root_db:
            spr.check_call(['psql', root_db, '-q', '-f',
                            osp.join(basedir, 'postgres', 'EMPD2.sql')],
                           stdout=spr.DEVNULL)

            message, files = fill_repo(
                osp.join(local_repo, output), db_url, root_db,
                dry_run, *args, **kwargs)

    if not dry_run and commit and files:
        repo.index.add(files)
        repo.index.commit(
            f"Updated {len(files)} files from postgres/{postgres_dump}")

    return message
