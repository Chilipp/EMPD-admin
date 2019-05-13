.. _install:

Installation
============


Installing the EMPD-admin locally
---------------------------------
The EMPD-admin runs as a webapp (see :ref:`pulls`), so you actually do not
have to install it on your own laptop. However, the webapp has limitations in
it's performance. So you might want to install it locally to speed up the
data contribution.

At the moment, we support installation from source or using the
`edmp2/empd-admin docker image`_. The latter has the advantage that it avoids
the installation of additional dependencies (that are quite heavy) and it
runs in a virtual machine, separated from the rest of your system.


.. contents::
	:local:


.. _docker-install:

Installation through Docker
***************************
The easiest way to get the EMPD-admin is to use the docker image that we
provide as `empd2/empd-admin`_. Here you do not have to install anything,
instead you pull the latest image from the docker hub. `Install docker` for
your system, and then pull the latest image via::

	docker pull empd2/empd-admin

And then run the command line utility via::

	docker run empd2/empd-admin empd-admin

The docker image also has the latest version of the EMPD-data_ repository
under ``/opt/empd-data``. This is what the ``empd-admin`` command uses. If you
want to use your own data contribution, mount it at that directory via::

	docker run -v PATH-TO-YOUR-REPO:/opt/empd-data empd2/empd-admin empd-admin

For example, to use the `test-data branch of the EMPD2/EMPD-data`_ repository,
as we use it in our :ref:`getting-started` guide, you can clone it via::

	git clone -q https://github.com/EMPD2/EMPD-data -b test-data

And then test it via::

	docker run -v `pwd`/EMPD-data:/opt/empd-data empd2/empd-admin empd-admin test

.. _empd2/empd-admin: https://hub.docker.com/r/empd2/empd-admin
.. _test-data branch of the EMPD2/EMPD-data: https://github.com/EMPD2/EMPD-data/tree/test-data
.. _Install docker: https://docs.docker.com/


.. _install-source:

Installation from source
************************
To install the EMPD-admin, clone the repository from github via::

	git clone https://github.com/EMPD2/EMPD-admin

or :download:`download the zipped source files from Github <https://github.com/EMPD2/EMPD-admin/archive/master.zip>`.

The dependencies of the EMPD-admin are quite heavy, in particularly we rely on

- python_ >= 3.7, pip_: The python operating system
- pandas_: For handling and processing the EMPD data
- git_, gitpython_ and pygithub_: To use the version control features of the EMPD
- pytest_, geopandas_, netcdf4_, latlon-utils_, shapely_: To run the tests of the EMPD
- sqlalchemy_ and psycopg2_: To use the EMPD as a relational postgres database
- tornado_, requests_, pyyaml_: optional dependencies for the webapp

.. _empd2/empd-admin docker image: https://hub.docker.com/r/empd2/empd-admin
.. _EMPD-data: https://github.com/EMPD2/EMPD-data
.. _conda: https://conda.io/docs/
.. _anaconda: https://www.anaconda.com/download/
.. _miniconda: https://conda.io/miniconda.html
.. _python: http://www.python.org/
.. _pip: https://pip.pypa.io/en/stable/
.. _tornado: http://www.tornadoweb.org/
.. _git: https://git-scm.com/
.. _gitpython: https://github.com/gitpython-developers/GitPython
.. _pandas: http://pandas.pydata.org/
.. _pytest: https://docs.pytest.org/en/latest/
.. _geopandas: http://geopandas.org/
.. _netcdf4: http://github.com/Unidata/netcdf4-python
.. _pygithub: http://pygithub.github.io/PyGithub/v1/index.html
.. _latlon-utils: https://github.com/Chilipp/latlon-utils
.. _shapely: https://github.com/Toblerity/Shapely
.. _sqlalchemy: http://www.sqlalchemy.org/
.. _psycopg2: http://initd.org/psycopg/
.. _tornado: http://www.tornadoweb.org/
.. _requests: http://python-requests.org/
.. _pyyaml: http://pyyaml.org/wiki/PyYAML

We highly recommend to use conda_ to install these dependencies. Here you can
either the anaconda_ or miniconda_ installer.

Please download the conda :download:`environment file <https://raw.githubusercontent.com/EMPD2/empd-admin-base/master/empd-admin-environment.yml>` and create a new conda environment for conda via::

	conda env create -f PATH-TO-DOWNLOADED-FILE

and activate it via::

	conda activate empd-admin

Finally install the EMPD-admin via::

	pip install EMPD-admin

You can then run the empd-admin via

.. command-output:: empd-admin --help

.. note::

	You can also skip the installation of the dependencies through conda, and
	directly run ``pip install EMPD-admin``, but do that on your own risk.
	There is no guarantee that packages like netCDF4 or pandas work through
	``pip`` installation


.. _build-docs:

Building the docs
-----------------
The docs are also built through the :ref:`docker image <docker-install>`.
Clone the EMPD-admin repository::

	git clone https://github.com/EMPD2/EMPD-admin.git
	cd EMPD-admin

Then use the ``Dockerfile`` in ``docs/Dockerfile`` to built the
`empd-admin-docs` image::

	docker build -t empd-admin-docs docs

Now mount the directory where you want the documentation to be generated (in
the example below ``docs/_build/html``) as ``/opt/empd-admin-docs`` and run the
`` build-empd-admin-docs``command::

	docker run -v `pwd`/docs/_build/html:/opt/empd-admin-docs build-empd-admin-docs /opt/empd-admin-docs


.. _run-tests:

Testing the EMPD-admin
----------------------
Testing the EMPD-admin requires a `Github API token`_ to test the webapp
features. Login to Github and create a token (without any scopes) at
https://github.com/settings/tokens. Copy the token and run the tests of the
EMPD-admin through the docker image::

	docker run -e GH_TOKEN=YOUR-SECRET-TOKEN empd2/empd-admin test-empd-admin

Alternatively, if you installed the EMPD-admin
:ref:`from source <install-source>`, you can run the tests by executing
``pytest`` from within the downloaded Github repository, i.e.::

	git clone https://github.com/EMPD2/EMPD-admin.git
	cd EMPD-admin
	pytest

.. _Github API token: https://github.blog/2013-05-16-personal-api-tokens/
