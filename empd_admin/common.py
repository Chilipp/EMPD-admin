# Common functions for the EMPD-admin modules
import os
import time
import os.path as osp
import pandas as pd
import numpy as np
import git
import contextlib

#: Path to the local directory of the cloned EMPD2/EMPD-data repository. The
#: path can be set through the ``EMPDDATA`` environment variable. Otherwise,
#: it is assumed to be ``'$HOME/.local/share/EMPD-data'``
DATADIR = os.getenv(
    'EMPDDATA', osp.join(osp.expanduser('~'), '.local', 'share', 'EMPD-data'))


#: Columns in the EMPD-data metadata sheet that hold numeric values
NUMERIC_COLS = ['Latitude', 'Longitude', 'Elevation', 'AreaOfSite', 'AgeBP',
                'count', 'percentage']


#: Lock file to lock the repository :attr:`DATADIR`. By default, this is at
#: ``'$HOME/cloning_master.lock'`` and is used by the :func:`lock_empd_master`
#: and :func:`wait_for_empd_master` functions.
DATA_LOCKFILE = osp.join(osp.expanduser('~'), 'cloning_master.lock')


def read_empd_meta(fname=None, addokexcept=True):
    """Read an EMPD-data metadata file into a pandas DataFrame

    This function is the same as :func:`pandas.read_csv` but it also ensures
    the correct dtype for the various columns.

    Parameters
    ----------
    fname: str
        The path to the (tab-delimited) meta data file. If None, it will
        default to the meta data in the :attr:`DATADIR`, i.e.
        ``DATADIR + '/meta.tsv'``

    Returns
    -------
    pandas.DataFrame
        The given `fname` as a data frame. The index column will be the
        `SampleName` column in `fname`.

    Examples
    --------
    Read the meta data of the EMPD-data repository::

        import git
        from empd_admin.common import read_empd_meta
        git.Repo.clone_from('https://github.com/EMPD2/EMPD-data.git')
        meta = read_empd_meta('EMPD-data/meta.tsv')

    See Also
    --------
    dump_empd_meta: To save the meta data"""
    if fname is None:
        repo = get_empd_master_repo()
        fname = osp.join(repo.working_dir, 'meta.tsv')

    ret = pd.read_csv(str(fname), sep='\t', dtype=str)
    if 'SampleName' in ret.columns:
        ret.set_index('SampleName', inplace=True)
    elif 'samplename' in ret.columns:
        ret.set_index('samplename', inplace=True)

    for col in NUMERIC_COLS:
        if col in ret.columns:
            ret[col] = ret[col].replace('', np.nan).astype(float)
    if 'ispercent' in ret.columns:
        ret.rename(columns={'ispercent': 'ispercent_str'}, inplace=True)
        ret['ispercent'] = False
        ret.loc[ret.ispercent_str.str.startswith('t', na=False) |
                ret.ispercent_str.str.startswith('T', na=False), 'ispercent'] = True
        del ret['ispercent_str']

    if addokexcept and 'okexcept' not in ret.columns:
        ret['okexcept'] = ''

    return ret


def dump_empd_meta(meta, fname=None, **kwargs):
    """Dump the EMPD meta data to a file

    This function dumps the meta data of the EMPD to a file with some standard
    formatting

    Parameters
    ----------
    meta: pandas.DataFrame
        The dataframe holding the meta data (see :func:`read_empd_meta`)
    fname: str
        The filename where to save it (see :func:`pandas.DataFrame.to_csv`)
    ``**kwargs``
        Any other argument that is parsed to the
        :func:`pandas.DataFrame.to_csv` function

    Examples
    --------
    Read the EMPD meta file and dump it again::

        from empd_admin.common import read_empd_meta, dump_empd_meta
        meta = read_empd_meta('EMPD-data/meta.tsv')
        dump_empd_meta(meta, 'EMPD-data/meta.tsv')"""
    if 'SampleName' in meta.index.names or 'samplename' in meta.index.names:
        kwargs.setdefault('index', True)
    else:
        kwargs.setdefault('index', False)
    kwargs.setdefault('sep', '\t')
    kwargs.setdefault('float_format', '%1.8g')
    return meta.to_csv(fname, **kwargs)


def wait_for_empd_master(timeout=120):
    """Wait until the data repository is available

    This convenience function makes sure, that there is no process locking the
    EMPD-data repository that is accessed through the EMPD-admin"""
    for i in range(timeout):
        if not osp.exists(DATA_LOCKFILE):
            return
        time.sleep(1)
    raise TimeoutError(
        "Data repository is still locked by %r after %i seconds. Please "
        "remove the lock file if that is an error" % (DATA_LOCKFILE, timeout))


@contextlib.contextmanager
def lock_empd_master():
    """Lock the data repository

    This will lock the data repository and blocks any access to it. The locking
    is done through a lock file (usually in ``'$HOME/cloning_master.lock'``,
    see the :attr:`DATA_LOCKFILE`).

    Use this function as a context manager, i.e. such as::

        with lock_empd_master():
            # now the repository is locked
            do_something()
        # now it is not locked anymore
    """
    try:
        with open(DATA_LOCKFILE, 'w') as f:
            yield f
    finally:
        if osp.exists(DATA_LOCKFILE):
            os.remove(DATA_LOCKFILE)


def get_empd_master_repo():
    """Get the repository to the data directory and download it if necessary

    This function returns a :class:`git.Repo` instance for the :attr:`DATADIR`.

    Returns
    -------
    git.Repo
        The local repository of the EMPD-data. If necessary, it has been cloned
        from https://github.com/EMPD2/EMPD-data.git.
    """
    wait_for_empd_master()
    if not osp.exists(DATADIR):
        with lock_empd_master():
            url = "https://github.com/EMPD2/EMPD-data.git"
            print("Cloning the EMPD-data repository from " + url)
            git.Repo.clone_from(url, DATADIR)
    return git.Repo(DATADIR)


def get_test_dir():
    """The path to the tests directory in the data directory

    Returns
    -------
    str
        The path to the tests of the data repository

    See Also
    --------
    get_empd_master_repo: To get the data repository"""
    repo = get_empd_master_repo()
    return osp.join(repo.working_dir, 'tests')


def get_psql_scripts():
    """The path to the postgres scripts in the EMPD-data repository

    Returns
    -------
    str
        The path to the postgres scripts of the data repository

    See Also
    --------
    get_empd_master_repo: To get the data repository"""
    repo = get_empd_master_repo()
    return osp.join(repo.working_dir, 'postgres', 'scripts')


# ----------------------- Tests ----------------------------
def test_ispercent_read_empd_data():
    import tempfile
    df = pd.DataFrame(index=pd.Index(['a1', 'a2', 'a3'], name='SampleName'))
    df['ispercent'] = ['False', '', 'True']
    with tempfile.NamedTemporaryFile(prefix="empd_", suffix=".tsv") as f:
        df.to_csv(f.name, '\t')
        test = read_empd_meta(f.name)
    assert test.ispercent.values.tolist() == [False, False, True]

