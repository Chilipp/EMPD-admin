# Main module for the empd-admin
import sys
import os.path as osp
import re
from empd_admin.parsers import setup_pytest_args, get_parser


def filter_pytest():
    """Filter lines that only contain dots and s from pytest runs"""
    perc_pat = re.compile(r'\[\s*\d+%\]')
    dot_pat = re.compile(r'(?m)^[\.s]{2,1000}')
    for s in sys.stdin:
        s = perc_pat.sub('', dot_pat.sub('', s)).strip()
        if s:
            print(s)


def main():
    parser = get_parser()
    args = parser.parse_args()
    if args.parser == 'help':
        args.print_help(args.command)
        parser.exit()
    elif args.parser is None:
        parser.print_help()
        parser.exit()
    elif args.parser == 'filter-log':
        filter_pytest()
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
            meta, dbname=args.database, commit=args.commit)
        print(report)
        if not success:
            sys.exit(1)
    elif args.parser == 'query':
        from empd_admin.query import query_meta
        args.meta_file = args.meta_file or osp.basename(meta)
        print(query_meta(args.meta_file, args.query, args.columns, args.count,
                         args.output, args.commit, local_repo,
                         args.distinct)[1])
    elif args.parser == 'rebuild':
        success, report, sql_dump = import_database(
            meta, dbname=args.database, commit=args.commit,
            rebuild_fixed=args.tables)
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
