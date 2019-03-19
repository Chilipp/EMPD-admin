"""Module for accepting erroneous meta data"""
import os.path as osp
from git import Repo
import pandas as pd
import numpy as np


def accept(meta, what, commit=True, raise_error=False):
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t', index_col='SampleName')
    samples = np.unique([t[0] for t in what])
    valid = (samples == 'all') | np.isin(samples, meta_df.index)
    if not valid.all():
        msg = "Missing samples %s in %s" % (
            samples[~valid], osp.basename(meta))
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns:
        meta_df['okexcept'] = ''
    for sample, column in what:
        if sample == 'all':
            meta_df.loc[:, 'okexcept'] += column + ','
            message = f"Accept wrong {column} for all samples"
        else:
            meta_df.loc[sample, 'okexcept'] += column + ','
            message = f"Accept wrong {column} for sample {sample}"

        if commit:
            meta_df.to_csv(meta, sep='\t')
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message)
    if not commit:
        meta_df.to_csv(meta, sep='\t')
        return ("Marked the fields as accepted but without having it "
                "commited")


def unaccept(meta, what, commit=True, raise_error=False):
    repo = Repo(osp.dirname(meta))
    meta_df = pd.read_csv(meta, sep='\t', index_col='SampleName')
    samples = np.unique([t[0] for t in what])
    valid = (samples == 'all') | np.isin(samples, meta_df.index)
    if not valid.all():
        msg = "Missing samples %s in %s" % (
            samples[~valid], osp.basename(meta))
        if raise_error:
            raise ValueError(msg)
        else:
            return msg
    if 'okexcept' not in meta_df.columns:
        return  # everything is not accepted already
    old_okexcept = meta_df.okexcept.copy(True)
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
                meta_df.loc[sample, 'okexcept'] = ''
                message = f"Do not accept any failure for sample {sample}"
            else:
                meta_df.loc[sample, 'okexcept'] = meta_df.loc[
                    sample, 'okexcept'].replace(column + ',', '')
                message = f"Do not accept wrong {column} for sample {sample}"

        if commit and (old_okexcept != meta_df['okexcept']).any():
            meta_df.to_csv(meta, sep='\t')
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message)
        old_okexcept = meta_df['okexcept'].copy(True)
    if not commit:
        meta_df.to_csv(meta, sep='\t')
        return ("Reverted the acceptance of mentioned erroneous fields but "
                "did not commit.")
