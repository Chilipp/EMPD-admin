.. _pulls:

EMPD-data pull requests
=======================
The main idea of the EMPD-admin is to use it as an interactive webapp in new
data contributions to the EMPD. These data contributions come in as pull
requests to the `EMPD2/EMPD-data`_ repository.

The EMPD-admin has a dedicated `Github user account`_ that you can contact if
you write ``@EMPD-admin`` in a comment in a pull request. You can then send him
any of the :ref:`command line commands <cli>`. E.g. you can test the data
contribution with the :ref:`test` command, by writing

	.. raw:: html

		<b><a href="https://github.com/EMPD-admin">@EMPD-admin</a></b> test

Please refer to the :ref:`cli` for a documentation on the other available
commands and to the :ref:`getting-started` section for an introduction on the
workflow of a data contribution.

.. note::

	Before contacting the EMPD-admin, you should make sure that he is up and
	running. You can do so by visiting `empd-admin.herokuapp.com <https://empd-admin.herokuapp.com>`_

	The EMPD-admin runs as a free webapp on heroku. Because of
	this, it get's suspended if there has been no request for more than 30
	minutes. It will be started if someone writes a command at Github, but that
	may take too long, leading to a rejection of your command. If that happens,
	just send the command again after one minute, and it will be processed.

	Please note that expensive commands may also take their time to be
	processed. Generally, everything that involves importing the data into
	postgres or running the tests for large contributions, takes their time.


.. _EMPD2/EMPD-data: https://github.com/EMPD-data/pulls
.. _Github user account: https://github.com/EMPD2/EMPD-admin
