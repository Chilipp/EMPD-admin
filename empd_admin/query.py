# A module to filter and display meta data
import os
import os.path as osp
import numpy as np
import pandas as pd
import textwrap
from sqlalchemy import create_engine
import tempfile
from git import Repo
from empd_admin.common import read_empd_meta, dump_empd_meta


def query_samples(meta_df, query):
    """Query the samples based on their metadata

    This function saves the given `meta_df` to a sqlite database and queries
    it based on the given filter. The performed query is such as::

        SELECT SampleName FROM meta_df WHERE query

    Parameters
    ----------
    meta_df: pandas.DataFrame
        The EMPD meta data (see :func:`empd_admin.common.read_empd_meta`)
    query: str
        The WHERE clause of the SQL query

    Returns
    -------
    np.ndarray
        The samples that have been selected by the given `query`"""
    # create a temporary sqlite database to execute the query
    with tempfile.TemporaryDirectory('_empd') as tmpdir:
        engine = create_engine(f'sqlite:///{tmpdir}/meta.sqlite')
        meta_df.to_sql('meta', engine)
        samples = pd.read_sql(
            f"SELECT SampleName FROM meta WHERE {query}",
            engine).SampleName.values
    return samples


def query_meta(meta, query, columns='notnull', count=False,
               output=None, commit=False, local_repo=None,
               distinct=False):
    """Query the meta data of a data contribution

    This function uses the :func:`query_samples` function to return a subset
    of the EMPD metadata. The performed query is such as::

        SELECT columns FROM meta WHERE query

    Parameters
    ----------
    meta: str
        The path to the metadata that shall be queried (see
        :func:`~empd_admin.common.read_empd_meta`)
    query: str
        The WHERE clause of the SQL query
    columns: list of str
        The columns that shall be returned. It can either be a list of columns,
        ``'all'`` to return all columns, or ``'notnull'`` (default) to return
        the non-empty columns
    count: bool
        If True, do not return the values per column but the number of valid
        entries per column (i.e. ``SELECT COUNT(*) FROM meta WHERE query``)
    output: str
        The path where to save the tab-delimited result of the query. If None
        and `commit` is ``True``, it will be saved to ``queries/query.tsv``,
        relative to the `local_repo`
    commit: bool
        If True, commit the changes in the repository `local_repo`
    local_repo: str
        The path of the local EMPD-data repository. If None, it will be assumed
        to be the directory of the given `meta`.
    distinct: list of str
        If not null, return a distinct query based on the columns listed in
        this parameter. For example ``distinct=['Country', 'SampleContext']``
        will result in ``SELECT DISTINCT ON ('Country', 'SampleContext') ...``

    Returns
    -------
    str
        The path where the query has been saved (see `output` and `commit`) or
        None
    str
        The result of the query as a markdown table, at maximum 200 rows
    """
    if local_repo is None:
        local_repo = osp.dirname(meta)
    else:
        meta = osp.join(local_repo, meta)
    meta_df = read_empd_meta(meta).replace('', np.nan)
    samples = query_samples(meta_df, query)

    sub = meta_df.loc[samples].reset_index()
    if isinstance(columns, str):
        columns = [columns]

    if 'notnull' in columns:
        missing = []
        notnull = sub.notnull().any(axis=0)
        columns = notnull[notnull].index
    elif 'all' in columns:
        missing = []
        columns = sub.columns
    else:
        columns = np.array(columns)
        mask = np.isin(columns, sub.columns)
        missing = columns[~mask]
        columns = columns[mask]
    if count:
        sub = sub[columns].count().to_frame().reset_index().fillna('')
        sub.columns = ['Column', 'Count']
    else:
        sub = sub[columns].fillna('')
    if commit:
        output = output or 'query.tsv'
    if output:
        ofile = osp.join(local_repo, 'queries', output)
        os.makedirs(osp.dirname(ofile), exist_ok=True)
        dump_empd_meta(sub, ofile)

    if commit:
        repo = Repo(local_repo)
        repo.index.add([osp.join('queries', output)])
        repo.index.commit(f'Added {output} [skip ci]\n\n{query}')

    sub = pd.concat([
        pd.DataFrame([('---', ) * len(sub.columns)], columns=sub.columns),
        sub], ignore_index=True)

    if distinct:
        if 'all' in distinct:
            distinct = sub.columns
        sub.drop_duplicates(distinct, inplace=True)

    ret = f'<details><summary>{query}</summary>\n\n' + textwrap.indent(
        dump_empd_meta(sub.head(200), sep='|'), '| ')
    ret += '\n\nDisplaying %i of %i rows' % (min(len(sub) - 1, 200),
                                             len(sub) - 1)
    if len(missing):
        ret += '\n\nMissing columns ' + ', '.join(missing)
    return output, ret + '\n</details>'
