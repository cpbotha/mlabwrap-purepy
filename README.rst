mlabwrap-purepy
===============

The original `mlabwrap <http://mlabwrap.sourceforge.net/>`_ is a 
Python-Matlab bridge that enables one to execute Matlab code from 
Python, by automatically starting up a Matlab process in the background 
and talking to it.

However, mlabwrap requires a compilation step against Matlab, which 
can be quite an inconvenience. So Dani Valevski rewrote the low-level 
parts of mlabwrap in Python, and made these `available as open source 
on Google Code
<https://code.google.com/p/danapeerlab/source/browse/trunk/freecell/depends/common/python/>`_.

The code you are looking at now, is simply the pure python
mlabwrap code that has been packaged together and slightly
improved by `Charl Botha <http://charlbotha.com>`_.

Improvements
------------
* More intelligent determination of Matlab binary path and versioning.
* Many bug fixes for scipy 0.12 + matlab 2011b.
* ``mlab.name`` will return the value of matlab variable ``name``. This syntax
  only used to work for invoking functions.
* Error reporting.
* Documentation.
* setuptools configuration, so you can install mlabwrap with a
  single pip invocation! See below for details.

Quickstart
----------

Linux
~~~~~

Install mlabwrap-purepy::

    sudo easy_install pip
    sudo pip install numpy
    sudo pip install scipy
    sudo pip install git+https://github.com/cpbotha/mlabwrap-purepy.git

These instructions will install pip, numpy, scipy and mlabwrap-purepy 
system-wide. If you're hip enough to use `virtualenv`, you're hip 
enough to figure out how to do this in a virtualenv. :)

Using from Python
~~~~~~~~~~~~~~~~~

Also see the docstring in mlabwrap.py. It goes something like this::

    import mlabwrap
    mlab = mlabwrap.init()

If the main matlab executable (or a symlink to it) is not on your system PATH,
pass its full path as the first parameter to init. Now you can do::

    sorted = mlab.sort([1 2 3])

Or even::

    mlab._do("a = [3 2 1]; b = mean(a);", nout=0)
    print mlab.b

