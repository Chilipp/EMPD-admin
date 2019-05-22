"""Module for accepting erroneous meta data

Errornous fields, i.e. meta data cells that do not pass the EMPD-data, tests,
can be accepted by modifying the `okexcept` column in the meta data sheet.

The functions here are also available as :ref:`unaccept` and :ref:`accept`
commnds of the :ref:`empd-admin` shell command."""
import os.path as osp
from git import Repo
import pandas as pd
import numpy as np
from empd_admin.query import query_samples
from empd_admin.common import read_empd_meta, dump_empd_meta


def accept_query(meta, query, columns, commit=True, skip_ci=False,
                 raise_error=False, local_repo=None):
    """Accept failed metadata based on a query for the pandas.DataFrame.query

    This function can accept failed `columns` for samples based on a `query`.

    The sql expression would be something like::

        UPDATE meta SET okexcept = ','.join(columns) WHERE query

    Parameters
    ----------
    meta: str
        The path to the metadata that shall be queried
    query: str
        The ``WHERE`` part of the query (see
        :func:`empd_admin.query.query_samples`).
    columns: list of str
        The columns that shall be marked as accepted (they will be appended to
        the existing columns)
    commit: bool
        If True, commit the changes in the repository `local_repo`
    skip_ci: bool
        If True and `commit`, then ``[skip ci]`` will be added to the commit
        message
    raise_error: bool
        If True, raise an error on Failure, otherwise return the error msg
    local_repo: str
        The path of the local EMPD-data repository. If None, it will be assumed
        to be the directory of the given `meta`.

    Returns
    -------
    str
        The status message. None if everything is allright.

    See Also
    --------
    accept

    Examples
    --------
    Accept missing Latitudes and Longitudes::

        accept_query(
            meta, "Latitude is NULL or Longitude is NULL", ['Country'])
    """
    if local_repo is None:
        local_repo = osp.dirname(meta)
        base_meta = osp.basename(meta)
    else:
        base_meta = meta
        meta = osp.join(local_repo, meta)
    repo = Repo(local_repo)
    meta_df = read_empd_meta(meta)
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
        meta_df.loc[samples, 'okexcept'] = meta_df.loc[
            samples, 'okexcept'].apply(
                lambda s: ','.join(sorted(set(s[:-1].split(',')))) + ',')
        message = (f"Accept wrong {column} for {nsamples} samples\n\n"
                   f"based on '{query}'")

    if commit:
        dump_empd_meta(meta_df, meta)
        repo.index.add([base_meta])
        repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        dump_empd_meta(meta_df, meta)
        return ("Marked the fields as accepted but without having it "
                "commited. %i sample%s would have been affected.") % (
                    nsamples, 's' if nsamples > 1 else '')


def accept(meta, what, commit=True, skip_ci=False, raise_error=False,
           exact=False, local_repo=None):
    """Accept failed metadata

    This function marks columns for specific cells as `okexcept`, such that it
    passes the EMPD-data tests

    Parameters
    ----------
    meta: str
        The path to the metadata
    what: list of str
        A list of strings like `sample:column` where `sample` is a regular
        expression (or the name of the sample if `exact`) and the `column` is
        the column for the corresponding sample that shall be accepted. The
        `sample` can also be ``'all'`` to match all samples in the metadata
    commit: bool
        If True, commit the changes in the repository of `meta`
    skip_ci: bool
        If True and `commit`, then ``[skip ci]`` will be added to the commit
        message
    raise_error: bool
        If True, raise an error on Failure, otherwise return the error msg
    except: bool
        If True, samples must be euqal to the `sample` part in `what`.
        Otherwise we use regular expressions
    local_repo: str
        The path of the local EMPD-data repository. If None, it will be assumed
        to be the directory of the given `meta`.

    Returs
    ------
    str
        The status message. None if everything is allright.

    Examples
    --------
    Accept wrong countries for all samples::

        accept(meta, ['all:Country'])

    Accept wrong latitudes and longitudes for all samples that start with
    ``'Barboni'``::

        accept(meta, ['Barboni:Latitude', 'Barboni:Longitude'])

    Accept wrong Temperature for the sample ``'Beaudouin_a1'`` and nothing
    else::

        accept(meta, ['Beaudouin_a1:Temperature'], exact=True)

    .. note::

        If you skip the `exact` parameter above, wrong temperatures would
        also be accepted for the sample ``Beaudouin_a10``!"""

    if local_repo is None:
        local_repo = osp.dirname(meta)
        base_meta = osp.basename(meta)
    else:
        base_meta = meta
        meta = osp.join(local_repo, meta)
    repo = Repo(local_repo)
    meta_df = read_empd_meta(meta).reset_index()
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
            slicer = slice(None)
            message = f"Accept wrong {column} for all samples"
        else:
            if exact:
                slicer = names == sample
            else:
                slicer = names.str.contains(sample)
            message = f"Accept wrong {column} for sample {sample}"
        meta_df.loc[slicer, 'okexcept'] += column + ','
        meta_df.loc[slicer, 'okexcept'] = meta_df.loc[
            slicer, 'okexcept'].apply(
                lambda s: ','.join(sorted(set(s[:-1].split(',')))) + ',')
        messages.append(message)

        if commit:
            dump_empd_meta(meta_df, meta)
            repo.index.add([base_meta])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        dump_empd_meta(meta_df, meta)
        return ("Marked the fields as accepted but without having it "
                "commited\n\n- " + "\n- ".join(messages))


def unaccept(meta, what, commit=True, skip_ci=False, raise_error=False,
             exact=False, local_repo=None):
    """Reverse acceptance for failed meta data

    This function reverses the acceptance made by the :func:`accept` or
    :func:`accept_query` function. Arguments are the same as for the
    :ref:`accept` function, despite the fact that the `column` part in `what`
    can also be `all`.

    Parameters
    ----------
    meta: str
        The path to the metadata
    what: list of str
        A list of strings like `sample:column` where `sample` is a regular
        expression (or the name of the sample if `exact`) and the `column` is
        the column for the corresponding sample that shall be accepted
    commit: bool
        If True, commit the changes in the repository of `meta`
    skip_ci: bool
        If True and `commit`, then ``[skip ci]`` will be added to the commit
        message
    raise_error: bool
        If True, raise an error on Failure, otherwise return the error msg
    except: bool
        If True, samples must be euqal to the `sample` part in `what`.
        Otherwise we use regular expressions
    local_repo: str
        The path of the local EMPD-data repository. If None, it will be assumed
        to be the directory of the given `meta`.

    Returs
    ------
    str
        The status message. None if everything is allright.

    Examples
    --------
    Do not accept any failure for any column::

        unaccept(meta, ['all:all'])

    Do not accept any failure for latitudes or longitudes with samples that
    start with ``'Barboni'``::

        unaccept(meta, ['Barboni:Latitude', 'Barboni:Longitude'])

    Do not accept wrong Temperature for the sample ``'Beaudouin_a1'``::

        unaccept(meta, ['Beaudouin_a1:Temperature'], exact=True)

    .. note::

        If you skip the `exact` parameter above, wrong temperatures would
        also be not accepted anymore for the sample ``Beaudouin_a10``!
    """
    if local_repo is None:
        local_repo = osp.dirname(meta)
        base_meta = osp.basename(meta)
    else:
        base_meta = meta
        meta = osp.join(local_repo, meta)
    repo = Repo(local_repo)
    meta_df = read_empd_meta(meta).reset_index()
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
            dump_empd_meta(meta_df, meta)
            repo.index.add([base_meta])
            repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
        old_okexcept = meta_df['okexcept'].copy(True)
    if not commit:
        dump_empd_meta(meta_df, meta)
        return ("Reverted the acceptance of mentioned erroneous fields but "
                "did not commit.\n\n- " + "\n- ".join(messages))


def unaccept_query(meta, query, columns, commit=True, skip_ci=False,
                   raise_error=False, local_repo=None):
    """Reverse acceptance for failed meta data based on a SQL query

    This function reverses the acceptance made by the :func:`accept` or
    :func:`accept_query` function, based on a SQL query. The arguments are
    the same as for the :func:`accept_query` function.

    Parameters
    ----------
    meta: str
        The path to the metadata that shall be queried
    query: str
        The ``WHERE`` part of the query (see
        :func:`empd_admin.query.query_samples`).
    columns: list of str
        The columns that shall not be accepted any more
    commit: bool
        If True, commit the changes in the repository of `meta`
    skip_ci: bool
        If True and `commit`, then ``[skip ci]`` will be added to the commit
        message
    raise_error: bool
        If True, raise an error on Failure, otherwise return the error msg
    local_repo: str
        The path of the local EMPD-data repository. If None, it will be assumed
        to be the directory of the given `meta`.

    Returns
    -------
    str
        The status message. None if everything is allright.

    See Also
    --------
    unaccept

    Examples
    --------
    Do not accept any failure for samples where the Country equals "Germany"::

        unaccept_query(meta, "Country = 'Germany'", ['Country'])
    """
    if local_repo is None:
        local_repo = osp.dirname(meta)
        base_meta = osp.basename(meta)
    else:
        base_meta = meta
        meta = osp.join(local_repo, meta)
    repo = Repo(local_repo)
    meta_df = read_empd_meta(meta)
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
        dump_empd_meta(meta_df, meta)
        repo.index.add([base_meta])
        repo.index.commit(message + ('\n\n[skip ci]' if skip_ci else ''))
    if not commit:
        dump_empd_meta(meta_df, meta)
        return ("Marked the fields as accepted but without having it "
                "commited. %i sample%s would have been affected.") % (
                    nsamples, 's' if nsamples > 1 else '')
