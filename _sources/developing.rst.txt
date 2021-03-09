Developing Frischen
===================

Requirements
------------

Frischen uses a decently large technology stack. For a complete development
environment, you need:

* Docker and Docker Compose:

  To have an MQTT broker available locally, Frischen uses
  `Docker <https://www.docker.com/get-started>`_ and
  `Docker Compose <https://docs.docker.com/compose/>`_ to run
  `Mosquitto <https://mosquitto.org>`_.

* Python 3.7 and pipenv

  Most of the tower control software as well as the utilities are written in
  `Python <https://www.python.org>`_. Make sure you install version 3.7 or
  newer, as Frischen uses a number of features not available in older versions.

  After installing Python 3.7, install
  `pipenv <https://pipenv.readthedocs.io>`_.

* A code editor or IDE with support for Python and JavaScript

  While a standard text editor is sufficient, a code editor or an integrated
  development environment can be quite helpful. These work quite decently:

  * `Atom <https://atom.io>`_ (open source, free)
  * `IntelliJ PyCharm <https://www.jetbrains.com/pycharm/>`_ and
    `IntelliJ WebStorm <https://www.jetbrains.com/webstorm/>`_ (free for
    personal use community edition, or commercial)
  * `Microsoft VisualStudio Code <https://visualstudio.microsoft.com/>`_
    (free use)


Setting Up a Development Environment
------------------------------------

Starting the MQTT Broker
........................

In the main directory, run:

.. code-block:: shell

    $ docker-compose up -d
    Creating network "frischen_default" with the default driver
    Pulling broker (eclipse-mosquitto:)...
    latest: Pulling from library/eclipse-mosquitto
    4fe2ade4980c: Pull complete
    9ed5ccc7b14f: Pull complete
    848281416363: Pull complete
    Digest: sha256:b96c387e1ea3c7531f7fe45447462e60e75b76b9d3d9e26c50a46283353953e6
    Status: Downloaded newer image for eclipse-mosquitto:latest
    Creating frischen_broker_1 ... done

This will start the mosquitto docker container.  The container listens on TCP
port 1883 for MQTT and on port 9001 for HTTP/WebSocket.

The built-in web server serves files from the ``web/`` directory, so you can
go to http://localhost:9001/ to see the available HTML/JavaScript apps.

Setting Up The Python Environment
.................................

Using a Python virtual environment ensures that you have the right versions of
Python packages needed. First, make sure you have ``pipenv`` installed:

.. code-block:: shell

    $ python3 -m pip install pipenv

Then, you can use ``pipenv`` to create a fresh environment and enter it:

.. code-block:: shell

    $ pipenv install --dev
    Pipfile.lock (3ea1da) out of date, updating to (4895ab)…
    Locking [dev-packages] dependencies…
    ✔ Success!
    Locking [packages] dependencies…
    ✔ Success!
    Updated Pipfile.lock (3ea1da)!
    Installing dependencies from Pipfile.lock (3ea1da)…
    To activate this project's virtualenv, run pipenv shell.
    Alternatively, run a command inside the virtualenv with pipenv run.

Finally, you can activate the freshly installed environment:

.. code-block:: shell

    $ pipenv shell
    Launching subshell in virtual environment…
     . /Users/me/.local/share/virtualenvs/frischen-0szepg5g/bin/activate
    $  . /Users/me/.local/share/virtualenvs/frischen-0szepg5g/bin/activate

You can now run the Python scripts in the top level of the project directory.


Working With Python Code
------------------------

Unit Tests And Test Coverage
............................

The Python modules have unit tests. To run the tests, use the standard Python
``unittest`` package.  To check test coverage, the ``coverage`` package is
installed:

.. code-block:: shell

    $ coverage run -m unittest && coverage report && coverage html

This will create coverage data and a report in ``coverage/``.

Documentation
-------------

Building
........

The project uses sphinx to generate HTML pages, including API docs for the
Python and JavaScript modules. The documentation sources are in ``docs/``.
To rebuild the HTML pages, run:

.. code-block:: shell

  $ cd docs
  $ make html

The output is available in ``docs/build/html`` and can be viewed in a browser.