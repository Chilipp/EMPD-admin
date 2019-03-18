# command line parser for the EMPD-admin
import argparse


class WebParser(argparse.ArgumentParser):
    """An ArgumentParser that does not sys.exit"""

    def exit(self, status=0, message=None):
        self._exited = True
        self._exit_status = status
        if message:
            self._exit_message = message
        raise RuntimeError(message)

    def error(self, message):
        self._errored = True
        args = {'prog': self.prog, 'message': message}
        self.exit(2, '%(prog)s: error: %(message)s' % args)

    def parse_known_args(self, *args, **kwargs):
        self._exited = self._errored = self._exit_status = \
            self._exit_message = False
        return super().parse_known_args(*args, **kwargs)


def setup_parser(parser):

    subparsers = parser.add_subparsers(title='Commands', dest='parser')

    test_parser = subparsers.add_parser('test', help='test the database')
    fix_parser = subparsers.add_parser('fix', help='fix the database')

    for parser in [test_parser, fix_parser]:
        parser.add_argument(
            '--collect-only', help="only collect tests, don't execute them.",
            action='store_true')
        parser.add_argument(
            '-x', '--exitfirst',
            help="exit instantly on first error or failed test.",
            action='store_true')
        parser.add_argument(
            '-m', help=("only run tests matching given mark expression. "
                        "example: -m 'mark1 and not mark2'.'"),
            metavar='MARKEXPR')
        parser.add_argument(
            '-k', metavar='EXPRESSION',
            help=('only run tests which match the given substring'
                  'expression. An expression is a python evaluatable'
                  'expression where all names are substring-matched'
                  'against test names and their parent classes. Example:'
                  "-k 'test_method or test_other' matches all test"
                  'functions and classes whose name contains'
                  "'test_method' or 'test_other', while -k 'not"
                  "test_method' matches those that don't contain"
                  "'test_method' in their names. Additionally keywords"
                  'are matched to classes and functions containing extra'
                  "names in their 'extra_keyword_matches' set, as well as"
                  'functions which have names assigned directly to them.'))

    fix_parser.add_argument(
        '--no-commit', help="Do not commit the changes", action='store_true')
