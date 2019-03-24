"""Command to finish the merging of a PR"""
import os
import os.path as osp
from functools import partial
import pandas as pd
from git import Repo
import github
from empd_admin.repo_test import import_database, temporary_database
import subprocess as spr
import textwrap


def finish_pr(meta, commit=True):
    rebase_master(meta)
    merge_meta(meta, commit)
    merge_postgres(meta, commit)

    if commit and osp.basename(meta) != 'meta.tsv':
        repo = Repo(osp.dirname(meta))
        repo.git.rm(meta)
        repo.index.commit("Removed %s to finish the PR" % osp.basename(meta))
    return


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

    else:
        import_database(meta, commit=True)  # to dump it to a temporary file


def look_for_changed_fixed_tables(meta, pr_owner, pr_repo, pr_branch):
    from urllib import request
    fixed = ['Country', 'GroupID', 'SampleContext', 'SampleMethod',
             'SampleType']
    msg = ''
    changed_tables = []
    local_tables = osp.join(osp.dirname(meta), 'postgres', 'scripts', 'tables')
    for table in fixed:
        upstream_url = ('https://raw.githubusercontent.com/EMPD2/EMPD-data/'
                        f'master/postgres/scripts/tables/{table}.tsv')
        fname = request.urlretrieve(upstream_url)[0]
        old = pd.read_csv(fname, sep='\t')
        os.remove(fname)
        new = pd.read_csv(osp.join(local_tables, table + '.tsv'), sep='\t')
        changed = set(map(tuple, new.values)) - set(map(tuple, old.values))
        if changed:
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
