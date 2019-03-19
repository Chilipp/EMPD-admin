"""Command to finish the merging of a PR"""
import os
import os.path as osp
from functools import partial
import pandas as pd
from git import Repo


def finish_pr(meta, commit=True):

    read_tsv = partial(pd.read_csv, index_col='SampleName', sep='\t')
    local_repo = osp.dirname(meta)

    meta_df = read_tsv(meta)

    base_meta = osp.join(local_repo, 'meta.tsv')
    base_meta_df = read_tsv(base_meta)

    # update the meta file and save
    base_meta_df = base_meta_df.join(meta_df[[]], how='outer')
    base_meta_df.loc[meta_df.index, meta_df.columns] = meta_df

    base_meta_df.to_csv(base_meta, sep='\t')

    # remove the meta file of the PR
    os.remove(meta)

    if commit:
        repo = Repo(local_repo)
        repo.index.add(
            [osp.basename(meta), 'meta.tsv'])
        repo.index.commit(f"Merged {meta} into meta.tsv")
