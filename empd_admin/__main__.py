# Main module for the empd-admin
import sys
import os.path as osp
import re
from empd_admin.parsers import setup_pytest_args, get_parser


def main(args=None, namespace=None):
    """Process command line args

    This function calls the :func:`empd_admin.parsers.get_parser` method and
    processes the given `args` or, if they are ``None``, :attr:`sys.argv`

    Parameters
    ----------
    args: list
        The command line arguments that are passed to the
        :meth:`argparse.ArgumentParser.parse_args` function
    namespace: argparse.Namespace
        The namespace that should be extended.

    .. note::

        This function is called when running `empd-admin` in the shell"""
    parser = get_parser()
    args = parser.parse_args(args)
    if args.parser == 'help':
        args.print_help(args.command)
        parser.exit()
    elif args.parser is None:
        parser.print_help()
        parser.exit()
        return
    else:
        from empd_admin.repo_test import \
            get_meta_file, run_test, import_database

    try:
        meta = get_meta_file(args.directory)
    except Exception:
        raise IOError("Could not find meta file in %s." % args.directory)
    else:
        if len(meta.splitlines()) > 1:
            raise IOError("Found multiple potential meta files:\n" + meta)

    local_repo = args.directory

    import empd_admin.common as common
    common.DATADIR = local_repo

    if args.parser == 'finish':
        from empd_admin.finish import finish_pr
        finish_pr(meta, commit=args.commit)
    elif args.parser == 'merge-meta':
        from empd_admin.finish import merge_meta
        merge_meta(args.src, args.target, args.commit, osp.dirname(meta))
    elif args.parser == 'rebase':
        from empd_admin.finish import rebase_master
        rebase_master(meta)
    elif args.parser == 'accept':
        from empd_admin.accept import accept, accept_query
        args.meta_file = args.meta_file or osp.basename(meta)
        if args.query:
            accept_query(args.meta_file, args.query,
                         [t[-1] for t in args.acceptable],
                         not args.no_commit, local_repo=local_repo,
                         raise_error=True)
        else:
            accept(args.meta_file, args.acceptable, not args.no_commit,
                   raise_error=True, local_repo=local_repo,
                   exact=args.exact)
    elif args.parser == 'unaccept':
        from empd_admin.accept import unaccept, unaccept_query
        args.meta_file = args.meta_file or osp.basename(meta)
        if args.query:
            unaccept_query(
                args.meta_file, args.query, [t[-1] for t in args.unacceptable],
                not args.no_commit, raise_error=True, local_repo=local_repo)
        else:
            unaccept(
                args.meta_file, args.unacceptable, not args.no_commit,
                raise_error=True, exact=args.exact, local_repo=local_repo)
    elif args.parser == 'createdb':
        success, report, sql_dump = import_database(
            meta, dbname=args.database, commit=args.commit,
            dump_tables=args.commit)
        print(report)
        if not success:
            sys.exit(1)
    elif args.parser == 'query':
        from empd_admin.query import query_meta
        args.meta_file = args.meta_file or osp.basename(meta)
        print(query_meta(args.meta_file, args.query, args.columns, args.count,
                         args.output, args.commit, local_repo,
                         args.distinct)[1])
    elif args.parser == 'diff':
        from empd_admin.diff import diff
        print(diff(meta, args.left, args.right, args.output, args.commit,
                   how=args.how, on=args.on, columns=args.columns,
                   exclude=args.exclude, atol=args.atol,
                   maxdiff=args.maxdiff)[1])

    elif args.parser == 'generate':
        from empd_admin.generate_repo import db2repo
        print(db2repo(
            meta, args.postgres_dump, args.commit,
            output=args.output, dry_run=args.dry_run,
            keep=args.keep,
            meta_data=args.meta_data, count_data=args.count_data,
            how=args.how, on=args.on, columns=args.columns,
            exclude=args.exclude, atol=args.atol))
    elif args.parser == 'rebuild':
        success, report, sql_dump = import_database(
            meta, dbname=args.database, commit=args.commit,
            rebuild_fixed=args.tables,
            populate=osp.join(osp.dirname(meta), 'postgres', 'EMPD2.sql'))
        print(report)
        if not success:
            sys.exit(1)
    else:
        pytest_args, files = setup_pytest_args(args)

        success, report, md_report = run_test(meta, pytest_args, files)
        if success and args.parser == 'test' and (
                not args.collect_only and not args.full_report):
            print('All tests passed')
        else:
            print(report)
        if not success:
            sys.exit(1)


if __name__ == '__main__':
    main()
