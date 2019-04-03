"""Command to finish the merging of a PR"""
import os
import os.path as osp
import shutil
from functools import partial
import pandas as pd
from git import Repo, GitCommandError
from empd_admin.repo_test import (
    import_database, temporary_database, SQLSCRIPTS, get_meta_file)
import subprocess as spr
import textwrap


def finish_pr(meta, commit=True):
    rebase_master(meta)
    merge_postgres(meta, commit=commit)
    merge_meta(meta, commit)

    if commit and osp.basename(meta) != 'meta.tsv':
        repo = Repo(osp.dirname(meta))
        repo.git.rm(meta)
        repo.index.commit("Removed %s to finish the PR" % osp.basename(meta))
    return


def merge_meta(meta, target=None, commit=True, local_repo=None):

    read_tsv = partial(pd.read_csv, index_col='SampleName', sep='\t')
    if local_repo is None:
        local_repo = osp.dirname(meta)

    if target is None:
        target = osp.basename(get_meta_file(local_repo))
        if osp.samefile(meta, osp.join(local_repo, target)):
            target = 'meta.tsv'

    meta_df = read_tsv(meta)

    base_meta = osp.join(local_repo, target)
    base_meta_df = read_tsv(base_meta)

    # update the meta file and save
    base_meta_df = base_meta_df.join(meta_df[[]], how='outer')
    cols = [col for col in meta_df.columns if col in base_meta_df.columns]
    base_meta_df.loc[meta_df.index, cols] = meta_df

    base_meta_df.to_csv(base_meta, sep='\t', float_format='%1.8g')

    if commit:
        repo = Repo(local_repo)
        repo.index.add([target])
        repo.index.commit("Merged {} into {} [skip ci]".format(
            osp.basename(meta), target))


def rebase_master(meta):
    # Merge the master branch into the feature branch using rebase
    repo = Repo(osp.dirname(meta))
    try:
        repo.remotes['upstream']
    except IndexError:
        remote = repo.create_remote(
            'upstream', 'https://github.com/EMPD2/EMPD-data.git')
        remote.fetch()
    # first try a rebase
    try:
        repo.git.rebase('upstream/master')
    except GitCommandError:
        repo.git.rebase('--abort')
        repo.git.pull('upstream', 'master')
        branch = repo.active_branch.name
        repo.index.commit("Merge branch 'upstream/master' into " + branch)
    repo.git.pull('--rebase')  # pull the remote origin


def merge_postgres(meta, commit=True):
    # import the data into the EMPD2 database
    if commit:
        import_database(meta, 'EMPD2', commit=commit)

        old_sql_dump = osp.join(osp.dirname(meta), 'postgres',
                                osp.splitext(osp.basename(meta))[0] + '.sql')
        if osp.exists(old_sql_dump):
            os.remove(old_sql_dump)
            if commit:
                repo = Repo(osp.dirname(meta))
                repo.git.rm(osp.join('postgres', osp.basename(old_sql_dump)))
                repo.index.commit(
                    "Removed postgres dump of %s" % osp.basename(meta))

        # export database as tab-delimited tables
        tables_dir = osp.join(osp.dirname(meta), 'tab-delimited')
        with temporary_database('EMPD2') as db_url:
            query = "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            tables = spr.check_output(['psql', db_url, '-Atc', query]).decode(
                'utf-8').split()
            copy = "COPY public.%s TO STDOUT WITH CSV HEADER DELIMITER E'\\t'"
            for table in tables:
                spr.check_call(['psql', db_url, '-c', copy % table,
                                '-o', osp.join(tables_dir, table + '.tsv')])
            if commit:
                repo = Repo(osp.dirname(meta))
                repo.index.add([tables_dir])
                repo.index.commit(
                    "Updated tab-delimited files from EMPD2 postgres database")

    else:
        import_database(meta, commit=True)  # to dump it to a temporary file


def look_for_changed_fixed_tables(meta, pr_owner, pr_repo, pr_branch):
    fixed = ['Country', 'GroupID', 'SampleContext', 'SampleMethod',
             'SampleType']
    msg = ''
    changed_tables = []
    local_tables = osp.join(osp.dirname(meta), 'postgres', 'scripts', 'tables')
    for table in fixed:
        fname = osp.join(SQLSCRIPTS, 'tables', table + '.tsv')
        old = pd.read_csv(fname, sep='\t')
        new = pd.read_csv(osp.join(local_tables, table + '.tsv'), sep='\t')
        changed = set(map(tuple, new.values)) - set(map(tuple, old.values))
        if changed:
            shutil.copyfile(osp.join(local_tables, table + '.tsv'), fname)
            changed = pd.DataFrame(
                [('---', ) * len(new.columns)] + list(changed),
                columns=new.columns)
            changed_tables.append(table)
            msg += textwrap.dedent(f"""
                - postgres/scripts/tables/{table}.tsv - [Edit the file](https://github.com/{pr_owner}/{pr_repo}/edit/{pr_branch}/postgres/scripts/tables/{table}.tsv)

                  <details><summary>%i changed rows:</summary>

                  %s
                  </details>
                """) % (len(changed) - 1,
                        textwrap.indent(changed.to_csv(sep='|', index=False),
                                        '  | '))
    if changed_tables:
        if len(changed_tables) == 1:
            msg = ("**Note** that one of the fixed tables has been changed!"
                   "\n\n%s\n\nPlease review it. """) % msg
        else:
            msg = ("**Note** that some of the fixed tables have been changed!"
                   "\n\n%s\n\nPlease review them. ") % msg
        action_required = set(changed_tables) & {
            'GroupID', 'SampleType', 'Country'}
        if action_required:
            suffix = 's' if len(action_required) > 1 else ''
            msg += ("If you change the file%s, please tell me via\n"
                    "`@EMPD-admin rebuild %s`\n"
                    "to update the table%s in the database") % (
                        suffix, ' '.join(action_required), suffix)
    return msg
