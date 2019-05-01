# Common functions for the EMPD-admin modules
import os
import os.path as osp
import pandas as pd
import numpy as np
import git

DATADIR = os.getenv(
    'EMPDDATA', osp.join(osp.expanduser('~'), '.local', 'share', 'EMPD-data'))


def read_empd_meta(fname):
    fname = fname

    ret = pd.read_csv(str(fname), sep='\t', index_col='SampleName',
                      dtype=str)

    for col in ['Latitude', 'Longitude', 'Elevation', 'AreaOfSite', 'AgeBP']:
        if col in ret.columns:
            ret[col] = ret[col].replace('', np.nan).astype(float)
    if 'ispercent' in ret.columns:
        ret['ispercent'] = ret['ispercent'].replace('', False).astype(bool)

    if 'okexcept' not in ret.columns:
        ret['okexcept'] = ''

    return ret


def get_empd_master_repo():
    """Get the repository to the data directory and download it if necessary"""
    if not osp.exists(DATADIR):
        return git.Repo.clone_from('https://github.com/EMPD2/EMPD-data.git')
    return git.Repo(DATADIR)


def get_test_dir():
    """The path to the tests directory"""
    repo = get_empd_master_repo()
    return osp.join(repo.working_dir, 'tests')


def get_psql_scripts():
    """The path to the postgres scripts directory"""
    repo = get_empd_master_repo()
    return osp.join(repo.working_dir, 'postgres', 'scripts')
