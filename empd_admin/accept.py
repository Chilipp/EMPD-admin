"""Module for accepting erroneous meta data"""
import os.path as osp
from git import Repo
import pandas as pd
import numpy as np
from empd_admin.query import query_samples


def accept_query(meta, query, columns, commit=True, skip_ci=False,
                 raise_error=False,):
    """Accept the columns based on a query for the pandas.DataFrame.query"""
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t', index_col='SampleName')
    samples = query_samples(meta_df, query)
    if not len(samples):
        msg = "No samples selected with %r" % (query, )
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns:
        meta_df['okexcept'] = ''
    else:
        meta_df['okexcept'] = meta_df.okexcept.fillna('')
    nsamples = len(samples)
    for column in columns:
        meta_df.loc[samples, 'okexcept'] += column + ','
        message = (f"Accept wrong {column} for {nsamples} samples\n\n"
                   f"based on '{query}'")

    if commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        repo.index.add([osp.basename(meta)])
        repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        return ("Marked the fields as accepted but without having it "
                "commited. %i sample%s would have been affected.") % (
                    nsamples, 's' if nsamples > 1 else '')


def accept(meta, what, commit=True, skip_ci=False, raise_error=False,
           exact=False):
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t')
    samples = np.unique([t[0] for t in what])

    valid = (samples == 'all')
    if exact:
        valid |= np.isin(samples, meta_df.SampleName.values)
    else:
        valid |= np.array(
            [meta_df.SampleName.str.contains(s).any() for s in samples])

    if not valid.all():
        msg = "Missing samples %s in %s" % (
            samples[~valid], osp.basename(meta))
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns:
        meta_df['okexcept'] = ''
    else:
        meta_df['okexcept'] = meta_df.okexcept.fillna('')
    names = meta_df.SampleName
    messages = []
    for sample, column in what:
        if sample == 'all':
            meta_df.loc[:, 'okexcept'] += column + ','
            message = f"Accept wrong {column} for all samples"
        else:
            if exact:
                meta_df.loc[names == sample, 'okexcept'] += column + ','
            else:
                meta_df.loc[names.str.contains(sample),
                            'okexcept'] += column + ','
            message = f"Accept wrong {column} for sample {sample}"
        messages.append(message)

        if commit:
            meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        return ("Marked the fields as accepted but without having it "
                "commited\n\n- " + "\n- ".join(messages))


def unaccept(meta, what, commit=True, skip_ci=False, raise_error=False,
             exact=False):
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t')
    samples = np.unique([t[0] for t in what])

    valid = (samples == 'all')
    if exact:
        valid |= np.isin(samples, meta_df.SampleName.values)
    else:
        valid |= np.array(
            [meta_df.SampleName.str.contains(s).any() for s in samples])

    if not valid.all():
        msg = "Missing samples %s in %s" % (
            samples[~valid], osp.basename(meta))
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns or not meta_df.okexcept.any():
        return  # no failures are already
    old_okexcept = meta_df.okexcept.copy(True)
    names = meta_df.SampleName
    messages = []
    for sample, column in what:
        if sample == 'all':
            if column == 'all':
                meta_df['okexcept'] = ''
                message = 'Do not accept any failure'
            else:
                meta_df['okexcept'] = meta_df['okexcept'].str.replace(
                    column + ',', '')
                message = f"Do not accept wrong {column} for all samples"
        else:
            if column == 'all':
                if exact:
                    meta_df.loc[names == sample, 'okexcept'] = ''
                else:
                    meta_df.loc[names.str.contains(sample), 'okexcept'] = ''
                message = f"Do not accept any failure for sample {sample}"
            else:
                if exact:
                    meta_df.loc[names == sample, 'okexcept'] = \
                        meta_df.loc[names == sample, 'okexcept'].replace(
                            column + ',', '')
                else:
                    meta_df.loc[names.str.contains(sample), 'okexcept'] = \
                        meta_df.loc[names.str.contains(sample),
                                    'okexcept'].replace(column + ',', '')
                message = f"Do not accept wrong {column} for sample {sample}"

            messages.append(message)

        if commit and (old_okexcept != meta_df['okexcept']).any():
            meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
        old_okexcept = meta_df['okexcept'].copy(True)
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        return ("Reverted the acceptance of mentioned erroneous fields but "
                "did not commit.\n\n- " + "\n- ".join(messages))


def unaccept_query(meta, query, columns, commit=True, skip_ci=False,
                   raise_error=False,):
    """Accept the columns based on a query for the pandas.DataFrame.query"""
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t', index_col='SampleName')
    samples = query_samples(meta_df, query)

    if not len(samples):
        msg = "No samples selected with %r" % (query, )
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns:
        meta_df['okexcept'] = ''
    else:
        meta_df['okexcept'] = meta_df.okexcept.fillna('')
    nsamples = len(samples)
    for column in columns:
        if column == 'all':
            meta_df.loc[samples, 'okexcept'] = ''
            message = (f"Do not accept any failure for {nsamples} samples\n\n"
                       f"based on '{query}'")
        else:
            meta_df.loc[samples, 'okexcept'] = meta_df.loc[
                samples, 'okexcept'].replace(column + ',', '')
            message = (
                f"Do not accept wrong {column} for {nsamples} samples\n\n"
                f"based on '{query}'")

    if commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        repo.index.add([osp.basename(meta)])
        repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False, float_format='%1.8g')
        return ("Marked the fields as accepted but without having it "
                "commited. %i sample%s would have been affected.") % (
                    nsamples, 's' if nsamples > 1 else '')
