# Main module for the empd-admin
from empd_admin.parsers import setup_pytest_args, get_parser
from empd_admin.repo_test import get_meta_file, run_test


def main():
    parser = get_parser()
    args = parser.parse_args()
    if args.parser == 'help':
        args.print_help(args.command)
        parser.exit()
    elif args.parser is None:
        parser.print_help()
        parser.exit()

    try:
        meta = get_meta_file(args.directory)
    except Exception:
        raise IOError("Could not find meta file in %s." % args.directory)
    else:
        if len(meta.splitlines()) > 1:
            raise IOError("Found multiple potential meta files:\n" + meta)

    pytest_args, files = setup_pytest_args(args)

    success, report, md_report = run_test(meta, pytest_args, files)
    print(report)


if __name__ == '__main__':
    main()
