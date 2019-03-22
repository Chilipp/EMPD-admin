# Main module for the empd-admin
import sys
from empd_admin.parsers import setup_pytest_args, get_parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    if args.parser == 'help':
        args.print_help(args.command)
        parser.exit()
    elif args.parser is None:
        parser.print_help()
        parser.exit()
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

    if args.parser == 'finish':
        from empd_admin.finish import finish_pr
        finish_pr(meta, commit=args.commit)
    elif args.parser == 'accept':
        from empd_admin.accept import accept
        accept(meta, args.acceptable, not args.no_commit, raise_error=True)
    elif args.parser == 'unaccept':
        from empd_admin.accept import unaccept
        unaccept(meta, args.unacceptable, not args.no_commit, raise_error=True)
    elif args.parser == 'createdb':
        success, report, sql_dump = import_database(
            meta, dbname=args.database, commit=args.commit)
        print(report)
        if not success:
            sys.exit(1)
    else:
        pytest_args, files = setup_pytest_args(args)

        success, report, md_report = run_test(meta, pytest_args, files)
        print(report)
        if not success:
            sys.exit(1)


if __name__ == '__main__':
    main()
