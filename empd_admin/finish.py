"""Command to finish the merging of a PR"""
import os
import os.path as osp
import shutil
from functools import partial
import pandas as pd
from git import Repo, GitCommandError
from empd_admin.repo_test import (
    import_database, temporary_database, SQLSCRIPTS, get_meta_file,
    run_test, remember_cwd)
import subprocess as spr
import textwrap


def finish_pr(meta, commit=True):
    rebase_master(meta)
#    fix_sample_formats(meta, commit)
    merge_postgres(meta, commit=commit)
    merge_meta(meta, commit=commit)

    with remember_cwd():
        os.chdir(osp.dirname(meta))
        repo = Repo('.')

        if commit and osp.exists('failures'):
            repo.git.rm('-r', 'failures')
            repo.index.commit("Removed extracted failures")

        if commit and osp.exists('queries'):
            repo.git.rm('-r', 'queries')
            repo.index.commit("Removed extracted queries")

        if commit and osp.basename(meta) != 'meta.tsv':
            repo.git.rm(osp.basename(meta))
            repo.index.commit(
                "Removed %s to finish the PR" % osp.basename(meta))
    return


def merge_meta(meta, target=None, commit=True, local_repo=None):

    read_tsv = partial(pd.read_csv, index_col='SampleName', sep='\t')
    if local_repo is None:
        local_repo = osp.dirname(meta)

    if not target:
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

    return target


def rebase_master(meta):
    # Merge the master branch into the feature branch using rebase
    repo = Repo(osp.dirname(meta))
    try:
        repo.remotes['upstream']
    except IndexError:
        remote = repo.create_remote(
            'upstream', 'https://github.com/EMPD2/EMPD-data.git')
        remote.fetch()
    branch = repo.active_branch.name
    # first try a rebase
    try:
        repo.git.rebase('upstream/master')
    except GitCommandError:
        repo.git.rebase('--abort')
        repo.git.pull('upstream', 'master')
        repo.index.commit("Merge branch 'upstream/master' into " + branch)
    repo.git.pull('origin', branch, '--rebase')  # pull the remote origin


def fix_sample_formats(meta, commit=True):
    pytest_args = ['--fix-db', '-v', '-k', 'fix_sample_data_formatting']
    if commit:
        pytest_args.append('--commit')

    run_test(meta, pytest_args, ['fixes.py'])


def merge_postgres(meta, commit=True):
    # import the data into the EMPD2 database
    if commit:
        success, msg, dump = import_database(meta, 'EMPD2', commit=commit)

        assert success, msg

        with remember_cwd():
            os.chdir(osp.dirname(meta))
            repo = Repo('.')
            old_sql_dump = osp.join(
                'postgres', osp.splitext(osp.basename(meta))[0] + '.sql')
            if osp.exists(old_sql_dump):
                repo.git.rm(osp.join('postgres', osp.basename(old_sql_dump)))
                repo.index.commit(
                    "Removed postgres dump of %s" % osp.basename(meta))

            # export database as tab-delimited tables
            tables_dir = 'tab-delimited'
            with temporary_database('EMPD2') as db_url:
                query = ("SELECT tablename FROM pg_tables "
                         "WHERE schemaname='public'")
                tables = spr.check_output(
                    ['psql', db_url, '-Atc', query]).decode('utf-8').split()
                copy = ("COPY public.%s TO STDOUT "
                        "WITH CSV HEADER DELIMITER E'\\t'")
                for table in tables:
                    cmd = ['psql', db_url, '-c', copy % table, '-o',
                           osp.join(tables_dir, table + '.tsv')]
                    spr.check_call(cmd)
                repo.index.add([osp.join(tables_dir, table + '.tsv')
                                for table in tables])
                repo.index.commit(
                    "Updated tab-delimited files from EMPD2 postgres database")
            print('Committed')

    else:
        # to dump it to a temporary file
        success, msg, dump = import_database(meta, commit=True)

        assert success, msg


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
                        textwrap.indent(changed.to_csv(sep='|', index=False,
                                                       float_format='%1.8g'),
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
