# A module to filter and display meta information
import numpy as np
import pandas as pd
import textwrap
from sqlalchemy import create_engine
import tempfile


def query_samples(meta_df, query):

    # create a temporary sqlite database to execute the query
    with tempfile.TemporaryDirectory('_empd') as tmpdir:
        engine = create_engine(f'sqlite:///{tmpdir}/meta.sqlite')
        meta_df.to_sql('meta', engine)
        samples = pd.read_sql(
            f"SELECT SampleName FROM meta WHERE {query}",
            engine).SampleName.values
    return samples


def query_meta(meta, query, columns='notnull', count=False):
    meta_df = pd.read_csv(meta, sep='\t', index_col='SampleName').replace(
        '', np.nan)
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
    sub = pd.concat([
        pd.DataFrame([('---', ) * len(sub.columns)], columns=sub.columns),
        sub], ignore_index=True)
    ret = f'<details><summary>{query}</summary>\n\n' + textwrap.indent(
        sub.to_csv(sep='|', index=False), '| ')
    if len(missing):
        ret += '\n\nMissing columns ' + ', '.join(missing)
    return ret + '\n</details>'
