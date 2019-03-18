# Main module for the empd-admin
from empd_admin.repo_test import get_meta_file, run_test


def get_parser():
    import argparse
    from empd_admin.parser import setup_parser
    parser = argparse.ArgumentParser('empd-admin')

    parser.add_argument(
        '-d', '--directory', default='.',
        help=('Path to the local EMPD2/EMPD-data repository. '
              'Default: %(default)s'))

    setup_parser(parser)
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    try:
        meta = get_meta_file(args.directory)
    except Exception:
        raise IOError("Could not find meta file in %s." % args.directory)
    else:
        if len(meta.splitlines()) > 1:
            raise IOError("Found multiple potential meta files:\n" + meta)

    pytest_args = []
    if args.m:
        pytest_args.extend(['-m', args.m])
        if args.parser == 'fix':
            pytest_args[-1] += ' and dbfix'
            pytest_args.append('--fix-db')
    elif args.parser == 'fix':
        pytest_args.extend(['-m', 'dbfix', '--fix-db'])
        if not args.no_commit:
            pytest_args.append('--commit')
    if args.k:
        pytest_args.extend(['-k', args.k])
        pytest_args['-k'] = args.k
    if args.collect_only:
        pytest_args.append('--collect-only')
    if args.exitfirst:
        pytest_args.append('-x')

    files = ['fixes.py'] if args.parser == 'fix' else ['']
    success, report, md_report = run_test(meta, pytest_args, files)
    print(report)


if __name__ == '__main__':
    main()
