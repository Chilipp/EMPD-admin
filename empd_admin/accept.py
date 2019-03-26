"""Module for accepting erroneous meta data"""
import os.path as osp
from git import Repo
import pandas as pd
import numpy as np


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

        if commit:
            meta_df.to_csv(meta, sep='\t', index=False)
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False)
        return ("Marked the fields as accepted but without having it "
                "commited")


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

        if commit and (old_okexcept != meta_df['okexcept']).any():
            meta_df.to_csv(meta, sep='\t', index=False)
            repo.index.add([osp.basename(meta)])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
        old_okexcept = meta_df['okexcept'].copy(True)
    if not commit:
        meta_df.to_csv(meta, sep='\t', index=False)
        return ("Reverted the acceptance of mentioned erroneous fields but "
                "did not commit.")
