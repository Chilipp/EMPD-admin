#!/usr/bin/env python
from setuptools import setup, find_packages


def main():
    setup(name='empd-admin',
          version='1.0',
          author='Philipp S. Sommer',
          author_email='philipp.sommer@unil.ch',
          url='https://github.com/EMPD2/EMPD-admin',
          entry_points=dict(
              console_scripts=['empd-admin = empd_admin.__main__:main']),
          packages=find_packages(),
          include_package_data=True,
          classifiers=[
            'Development Status :: 2 - Pre-Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
            'Programming Language :: Python :: 3.7',
            'Operating System :: Unix',
          ],
          license="GPLv3",
          )


if __name__ == '__main__':
    main()
