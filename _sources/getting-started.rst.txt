.. _getting-started:

Getting started
===============
In this small tutorial, we will guide you through a standard procedure of how
to merge a new data contribution into the EMPD. In the following sections, the
three main steps are described shortly, that are:

1. :ref:`Testing and fixing the contribution <contrib-test>`
2. :ref:`Analysing the contribution <contrib-query>`
3. :ref:`Finishing the contribution <contrib-finish>`

Note that, as a contributor to the EMPD, you do not have to work through this
guide. Of course, you are welcomed to do this, but it is the objective of the
core-maintainers to validate your contribution with the methods presented here.

.. note::

	The commands here are run from an interactive python session (ipython). For
	this reason, we are prefixing and shell command with an exclamation mark
	(``!``). If you run the examples locally, leave them away.

.. note::

	Note, we run the commands here locally using the ``empd-admin`` shell
	command. But if you use it from a Pull Request into the EMPD-data
	repository, you have to use ``@EMPD-admin``. If you are using the
	EMPD-admin through Docker, you can type
	``docker run -t empd2/empd-admin empd-admin `` instead.


.. _contrib-download:

Downloading the test data
-------------------------

For our tutorial, we will use the test-data branch of the EMPD (see
`here <https://empd2.github.io/?repo=EMPD2/EMPD-data&branch=test-data&meta=test.tsv>`_).
It contains artificial data that we use for testing. If you want to test the
commands here with your own contribution to the EMPD, you can also use your
own fork of the EMPD-data_ repository.

The following two commands clone the branch from
`Github <https://github.com/EMPD2/EMPD-data/tree/test-data>`_ and changes
the working directory to the downloaded directory.

.. ipython::

	@verbatim
	In [1]: !git clone -q https://github.com/EMPD2/EMPD-data -b test-data

	@verbatim
	In [2]: cd EMPD-data

	@suppress
	In [1]: import tempfile, os
	   ...: cwd = os.getcwd()
	   ...: with tempfile.TemporaryDirectory() as tmpdir: pass
	   ...: !git clone -q https://github.com/EMPD2/EMPD-data {tmpdir} -b test-data
	   ...: os.chdir(tmpdir)

	In [3]: ls

.. _contrib-test:

Testing the repository
----------------------

The first step is now, to test the data contribution. For this, we can use
the :ref:`empd-admin test <test>` command. For the test-data
branch this will fail due to an invalid country in the *test_a1* sample.

.. ipython::

	@okexcept
	In [3]: !empd-admin test

The failed sample can be extracted using the `-e` option:

.. ipython::

	@verbatim
	In [4]: !empd-admin test -e failed.tsv

	@suppress
	In [5]: !empd-admin test -e failed.tsv

which extracted the failed metadata into ``failures/failed.tsv``:

.. ipython::

	In [5]: ls failures/failed.tsv

and allows you to analyse it further. In our case, we can fix the failed sample
with the :ref:`fix` command:

.. ipython::

	In [4]: !empd-admin fix country -s test_a1

This now fixed the country for the *test_a1* sample and the tests will run through

.. ipython::

	In [5]: !empd-admin test

.. _contrib-query:

Query the repository
--------------------

The empd-admin provides several diagnostics to investigate the data
contribution. You already saw one of them: the extraction of failures with the
``-e`` option the the :ref:`test` command.

Another one is the :ref:`query` command to query the database. This will use an
sql query to display a subset of your metadata. The syntax is like::

	empd-admin query WHERE_CLAUSE [Column1, [Column2, [Column2]]]

Which will transform into a query like::

	SELECT Column1, Column2, Column3 FROM metadata WHERE WHERE_CLAUSE;

For example::

	empd-admin query 'Country = "Germany"' SampleName

will transform into::

	SELECT SampleName FROM metadata WHERE Country = "Germany";

and result in a markdown table for the SampleName:

.. ipython::

	In [6]: !empd-admin query 'Country = "Germany"' SampleName

When combining this with pandoc_, you can also directly transform it to HTML

.. ipython::

	In [6]: !empd-admin query 'Country = "Germany"' SampleName | pandoc -o query.html

	@suppress
	In [6]: !rm query.html

.. raw:: html

	<details>
	Country = "Germany"
	<table>
	<thead><tr class="header"><th>SampleName</th></tr></thead>
	<tbody>
	<tr class="odd"><td>test_a1</td></tr>
	<tr class="even"><td>test_a2</td></tr>
	<tr class="odd"><td>test_a3</td></tr>
	</tbody>
	</table>
	Displaying 3 of 3 rows
	</details>

You can also dump them as a file to the `queries` folder of your repository
with the ``--output`` and ``--commit`` options:

.. ipython::

	In [6]: !empd-admin query 'Country = "Germany"' SampleName -c

	In [7]: cat queries/query.tsv

.. _contrib-postgres:

Transform into postgres
-----------------------
Assuming you have Postgres installed on your system and a running postgres
database server, you can transform the EMPD meta data in a relational database,
`as it is available in the EMPD-data repository <https://github.com/EMPD2/EMPD-data/blob/master/postgres/EMPD2.sql>`_.

Just create postgres database using

.. ipython::

	In [7]: !createdb MyEMPD

and then incorporate your data as

.. ipython::

	In [8]: !empd-admin createdb -db MyEMPD

Then you can access it via

.. ipython::

	@verbatim
	In [9]: !psql MyEMPD


.. _contrib-finish:

Finishing a data contribution
-----------------------------
When you are satisfied with your data contribution, you can :ref:`finish` the
contribution.

This will remove all the intermediate working files (e.g. our new meta data
``test.tsv`` or the failed samples ``failures/failed.tsv``) and merge the new
data into the base meta file `meta.tsv` of the EMPD.

.. ipython::

	In [5]: !empd-admin finish --commit

	In [6]: log = !git log -8
	   ...: print(log.n)

That's it. Now we could merge this contribution into the EMPD from within
Github.


.. ipython::
	:suppress:

	In [4]: os.chdir(cwd)
	   ...: # !rm -rf {tmpdir}

.. _EMPD-data: https://github.com/EMPD-data
.. _pandoc: https://pandoc.org/
