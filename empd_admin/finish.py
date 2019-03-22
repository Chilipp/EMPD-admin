"""Command to finish the merging of a PR"""
import os
import os.path as osp
from functools import partial
import pandas as pd
from git import Repo
from empd_admin.repo_test import import_database


def finish_pr(meta, commit=True):
    rebase_master(meta)
    merge_meta(meta, commit)
    merge_postgres(meta, commit)

    if commit and osp.basename(meta) != 'meta.tsv':
        repo = Repo(osp.dirname(meta))
        repo.git.rm(meta)
        repo.index.commit("Removed %s to finish the PR" % osp.basename(meta))


def merge_meta(meta, commit=True):

    read_tsv = partial(pd.read_csv, index_col='SampleName', sep='\t')
    local_repo = osp.dirname(meta)

    meta_df = read_tsv(meta)

    base_meta = osp.join(local_repo, 'meta.tsv')
    base_meta_df = read_tsv(base_meta)

    # update the meta file and save
    base_meta_df = base_meta_df.join(meta_df[[]], how='outer')
    base_meta_df.loc[meta_df.index, meta_df.columns] = meta_df

    base_meta_df.to_csv(base_meta, sep='\t')

    if commit:
        repo = Repo(local_repo)
        repo.index.add(['meta.tsv'])
        repo.index.commit("Merged {} into meta.tsv [skip ci]".format(
            osp.basename(meta)))


def rebase_master(meta):
    # Merge the master branch into the feature branch using rebase
    repo = Repo(osp.dirname(meta))
    try:
        repo.remotes['upstream']
    except IndexError:
        remote = repo.create_remote(
            'upstream', 'https://github.com/EMPD2/EMPD-data.git')
        remote.fetch()
    repo.git.rebase('upstream/master')
    repo.git.pull('--rebase')  # pull the remote origin


def merge_postgres(meta, commit=True):
    # import the data into the EMPD2 database
    if commit:
        import_database(meta, 'EMPD2', commit=commit)

        sql_dump = osp.join(osp.dirname(meta), 'postgres',
                            osp.splitext(osp.basename(meta))[0] + '.sql')
        if osp.exists(sql_dump):
            os.remove(sql_dump)
            if commit:
                repo = Repo(osp.dirname(meta))
                repo.git.rm(osp.join('postgres', osp.basename(sql_dump)))
                repo.index.commit(
                    "Removed postgres dump of %s" % osp.basename(meta))

    else:
        import_database(meta, commit=True)  # to dump it to a temporary file
