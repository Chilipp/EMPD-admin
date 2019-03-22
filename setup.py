#!/usr/bin/env python
import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import os.path as osp


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        import shlex
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


def readme():
    with open('README.rst') as f:
        return f.read()


def main():
    setup(name='empd-admin',
          version='1.0',
          description='Automatic adminstrator of the EMPD',
          long_description=readme(),
          author='Philipp S. Sommer',
          author_email='philipp.sommer@unil.ch',
          url='https://github.com/EMPD2/EMPD-admin',
          entry_points=dict(
              console_scripts=['empd-admin = empd_admin.__main__:main']),
          packages=find_packages(),
          package_data={'empd_admin': [
              osp.join('empd_admin', 'data-tests', '*.py'),
              osp.join('empd_admin', 'data', 'postgres', 'scripts', '*.py'),
              osp.join('empd_admin', 'data', 'postgres', 'scripts', '*.sql'),
              ]},
          include_package_data=True,
          install_requires=[
              'tornado',
              'PyGithub',
              'gitpython',
              'pytest',
              'pandas',
              'xlrd',
          ],
          classifiers=[
            'Development Status :: 2 - Pre-Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
            'Programming Language :: Python :: 3.7',
            'Operating System :: Unix',
          ],
          license="GPLv3",
          tests_require=['pytest', 'psutil'],
          cmdclass={'test': PyTest},
          )


if __name__ == '__main__':
    main()
