.. EMPD-admin documentation master file, created by
   sphinx-quickstart on Sat May 11 12:36:00 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to EMPD-admin's documentation!
======================================

The EMPD-admin is a python package to administer the
`Eurasian Modern Pollen Database`_ (EMPD). This package helps contributors and
especially maintainers to test and fix new data contributions.

The main objective of the EMPD-admin is to be used in Github pull requests
in the EMPD-data_ repository. If you write::

    @EMPD-admin help

in a comment in a pull request (see `here <https://github.com/EMPD2/EMPD-data/pull/2#issuecomment-491545548>`_
for example), or any other command from the
:ref:`command line interface <cli>`, it will be handled by a webapp at
https://empd-admin.herokuapp.com. See the :ref:`pulls` section for more
details.

The EMPD-admin, however, can also be installed locally to test the contribution
before entering a pull request on Github. See the :ref:`getting-started`
section for an overview on how to use the EMPD-admin for new contributions and
the :ref:`install` instructions on how to install the EMPD-admin locally.

.. seealso::

    - The interactive viewer of the EMPD: https://EMPD2.github.io
    - The data repository of the EMPD: https://github.com/EMPD2/EMPD-data

.. _Eurasian Modern Pollen Database: https://EMPD2.github.io
.. _EMPD-data: https://github.com/EMPD-data

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   pulls
   install
   getting-started
   cli
   api/empd_admin.rst



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
