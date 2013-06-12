#!/usr/bin/env python

""" A python module for raw communication with Matlab(TM) using pipes under
unix.

This module exposes the same interface as mlabraw.cpp, so it can be used along
with mlabwrap.py.
The module sends commands to the matlab process using the standard input pipe.
It loads data from/to the matlab process using the undocumented save/load stdio
commands. Only unix (or mac osx) versions of Matlab support pipe communication,
so this module will only work under unix (or mac osx). 

Author: Dani Valevski <daniva@gmail.com>
Dependencies: scipy
Tested Matlab Versions: 2009b, 2010a, 2010b, 2011a, 2011b
License: MIT

Fixes and improvements by `Charl Botha <http://charlbotha.com>`_ (scipy 0.12,
documentation, finding matlab, code cleanups).
"""

from cStringIO import StringIO
import fcntl
import numpy as np
import os
import scipy.io as mlabio
import select
import subprocess
import sys


class MatlabError(Exception):
    """Raised when a Matlab evaluation results in an error inside Matlab."""
    pass


class MatlabConnectionError(Exception):
    """Raised for errors related to the Matlab connection."""
    pass


def find_executable_in_path(executable):
    """Find executable in path.

    Based on http://stackoverflow.com/a/5227009/532513, this goes
    through all the paths in your PATH environment variable, and returns
    the first one containing executable. It is similar to the unix
    `which` command.

    :author: Charl P. Botha <cpbotha@vxlabs.com>
    """

    paths = os.environ.get('PATH', '').split(os.pathsep)
    for path in paths:
        full = os.path.join(path, executable)
        if os.path.exists(full):
            return full

    return None


def find_matlab_process():
    """" Tries to guess matlab process path on unix and osx machines.

    On non-mac machines, simply tries to find matlab in the path.

    On Macs, the paths we will search are in the format:
    /Applications/MATLAB_R[YEAR][VERSION].app/bin/matlab
    We will try the latest version first. If no path is found, None is reutrned.

    :returns: Full path to the matlab executable.
    """

    if sys.platform == 'mac':
        # this is from the old code. I don't have a Mac to test, but it
        # looks OK.
        base_path = '/Applications/MATLAB_R%d%s.app/bin/matlab'
        years = range(2050, 1990, -1)
        versions = ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a']
        for year in years:
            for version in versions:
                matlab_path = base_path % (year, version)
                if os.path.exists(matlab_path):
                    return matlab_path
        return None

    else:
        # see if we can find this in the path
        return find_executable_in_path('matlab')


def find_matlab_version(process_path):
    """ Tries to guess matlab's version according to its process path.

    If we couldn't guess the version, None is returned.
    """

    bin_path = os.path.dirname(process_path)
    matlab_path = os.path.dirname(bin_path)

    # cpbotha says:
    # in Linux at least, there is a file called .VERSION in the matlab
    # path.
    # In future, rather parse matlab_path/toolbox/matlab/general/contents.m
    # for string like "% MATLAB Version 7.11 (R2010b) 03-Aug-2010"
    version_file = os.path.join(matlab_path, '.VERSION')

    # the file contains just R2010b
    # we want to end up with 2010b (that's what the code expects)
    version = file(version_file).read().strip()[1:]
    print "Found version:", version, "at", process_path

    if not is_valid_version_code(version):
        return None

    return version


def is_valid_version_code(version):
    """ Checks that the given version code is valid.
    """
    return version is not None and len(version) == 5 and \
        int(version[:4]) in range(1990, 2050) and \
        version[4] in ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a']


class MatlabPipe(object):
    """ Manages a connection to a matlab process.

    Matlab version is in the format [YEAR][VERSION] for example: 2011a.
    The process can be opened and close with the open/close methods.
    To send a command to the matlab shell use 'eval'.
    To load numpy data to the matlab shell use 'put'.
    To retrieve numpy data from the matlab shell use 'get'.
    """

    def __init__(self, matlab_binary_path=None, matlab_version=None):
        """ Inits the class.

        :param matlab_binary_path: path to the matlab executeable. For example:
            `/Applications/MATLAB_R2010b.app/bin/matlab`. If None, will try
            to find it in the system path.
        :param matlab_version: 4 or 5 digit version, e.g. 2010b (without the R).
            If None, will try to determine automatically from path.
        """

        if matlab_binary_path is None:
            matlab_binary_path = find_matlab_process()

        if matlab_version is None:
            matlab_version = find_matlab_version(matlab_binary_path)

        if not is_valid_version_code(matlab_version):
            raise ValueError('Invalid version code %s' % matlab_version)
        
        if not os.path.exists(matlab_binary_path):
            raise ValueError(
                'Matlab process path %s does not exist' % matlab_binary_path)
        
        self.matlab_version = (int(matlab_version[:4]), matlab_version[4])
        self.matlab_binary_path = matlab_binary_path
        self.process = None
        self.command_end_string = '___MATLAB_PIPE_COMMAND_ENDED___'
        self.expected_output_end = '%s\n>> ' % self.command_end_string
        self.stdout_to_read = ''

    def open(self, print_matlab_welcome=True):
        """ Opens the matlab process.
        """
        if self.process and not self.process.returncode:
            raise MatlabConnectionError(
                'Matlab(TM) process is still active. Use close to '
                'close it')

        self.process = subprocess.Popen(
            [self.matlab_binary_path, '-nojvm', '-nodesktop'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        flags = fcntl.fcntl(self.process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        if print_matlab_welcome:
            self._sync_output()

        else:
            self._sync_output(None)

    def close(self):
        """ Closes the matlab process.
        """
        self._check_open()
        self.process.stdin.close()

    def eval(self,
             expression,
             identify_errors=True,
             print_expression=True,
             on_new_output=sys.stdout.write):
        """ Evaluates a matlab expression synchronously.

        If identify_erros is true, and the last output line after evaluating the
        expressions begins with '???' and excpetion is thrown with the matlab error
        following the '???'.
        If on_new_output is not None, it will be called whenever a new output is
        encountered. The default value prints the new output to the screen.
        The return value of the function is the matlab output following the call.
        """

        self._check_open()
        if print_expression:
            print expression

        self.process.stdin.write(expression)
        self.process.stdin.write('\n')
        ret = self._sync_output(on_new_output)

        # TODO(dani): Use stderr to identify errors.
        if identify_errors and ret.rfind('???') != -1:
            begin = ret.rfind('???') + 4
            end = ret.find('\n', begin)
            raise MatlabError(ret[begin:end])

        return ret

    def put(self, name_to_val, oned_as='row', on_new_output=None):
        """ Loads a dictionary of variable names into the matlab shell.

        :param name_to_val: dict with keys the variable names and values the
            corresponding values. All of these will be passed to the matlab
            instance.

        :param oned_as: same as in :meth:`scipy.io.matlab.savemat`
            oned_as : {'column', 'row'}, optional
            If 'column', write 1-D numpy arrays as column vectors.
            If 'row', write 1D numpy arrays as row vectors.
        """

        self._check_open()
        # We can't give stdin to mlabio.savemat because it needs random access :(
        temp = StringIO()

        # documentation here:
        # http://docs.scipy.org/doc/scipy/reference/generated/scipy.io.savemat.html
        # cpbotha has set format to 4 so that e.g. integers are converted to
        # doubles. We need to do this, as the save() method we call from matlab
        # always defaults to v4 when we write to stdio.
        # scipy 0.12 support v7, but unfortunately we can't use this due to
        # matlab (at least 2011b) defaulting to v4 on stdio, even when we
        # explicitly tell it to use -v7.
        mlabio.savemat(temp, name_to_val, oned_as=oned_as, format='4')

        temp.seek(0)
        temp_str = temp.read()
        temp.close()
        self.process.stdin.write('load stdio;\n')
        self._read_until('ack load stdio\n', on_new_output=on_new_output)
        self.process.stdin.write(temp_str)
        #print 'sent %d kb' % (len(temp_str) / 1024)
        self._read_until('ack load finished\n', on_new_output=on_new_output)
        self._sync_output(on_new_output=on_new_output)

    def get(self,
            names_to_get,
            extract_numpy_scalars=True,
            on_new_output=None):
        """ Loads the requested variables from the matlab shell.

        names_to_get can be either a variable name, a list of variable names, or
        None.
        If it is a variable name, the values is returned.
        If it is a list, a dictionary of variable_name -> value is returned.
        If it is None, adictionary with all variables is returned.

        If extract_numpy_scalars is true, the method will convert numpy scalars
        (0-dimension arrays) to a regular python variable.
        """
        self._check_open()
        single_itme = isinstance(names_to_get, (unicode, str))

        if single_itme:
            names_to_get = [names_to_get]

        if names_to_get is None:
            self.process.stdin.write('save stdio;\n')

        else:
            # Make sure that we throw an exception if the names are not defined.
            for name in names_to_get:
                self.eval('%s' % name, print_expression=False,
                          on_new_output=on_new_output)

            # cpbotha: just tested with matlab 2011b
            # I can save int64 arrays to file with -v7
            # however, as soon as 'stdio' is the file, it defaults to -v4 and
            # can't save int64
            ml_save_cmd = \
                "save('stdio', '%s', '-v7');\n" % '\', \''.join(names_to_get)

            self.process.stdin.write(ml_save_cmd)

        # We have to read to a temp buffer because mlabio.loadmat needs
        # random access :(
        self._read_until('start_binary\n', on_new_output=on_new_output)
        #print 'got start_binary'
        temp_str = self._sync_output(on_new_output=on_new_output)
        #print 'got all outout'
        # Remove expected output and "\n>>"
        # TODO(dani): Get rid of the unecessary copy.
        # MATLAB 2010a adds an extra >> so we need to remove more spaces.
        if self.matlab_version == (2010, 'a'):
            temp_str = temp_str[:-len(self.expected_output_end) - 6]

        else:
            # the binary message has ">> self.expected_output_end" appended,
            # that's why we have the extra -3
            temp_str = temp_str[:-len(self.expected_output_end) - 3]

        temp = StringIO(temp_str)
        #print ('____')
        #print len(temp_str)
        #print ('____')

        # cpbotha: with scipy 0.12 this does not always return numpy arrays
        # behaviour of the function has changed to quite an extent
        # problem 1: put({'X': 'string'}) and then get({'X': 'string'} actually
        # returns {'X': 'string'}
        # I think this might be due to the changed default of struct_as_record
        # http://docs.scipy.org/doc/scipy/reference/generated/scipy.io.loadmat.html
        ret = mlabio.loadmat(temp, chars_as_strings=True, squeeze_me=True)

        #print '******'
        #print ret
        #print '******'
        temp.close()

        for key in ret.iterkeys():
            # address problem 1: only do WTF if the returned value is an ndarray
            if isinstance(ret[key], np.ndarray):
                # err WTF?! cpbotha is not sure what exactly is happening here.
                while ret[key].shape and ret[key].shape[-1] == 1:
                    ret[key] = ret[key][0]

            if extract_numpy_scalars:
                if isinstance(ret[key], np.ndarray) and not ret[key].shape:
                    ret[key] = ret[key].tolist()

        #print 'done'
        if single_itme:
            return ret.values()[0]

        return ret

    def _check_open(self):
        if not self.process or self.process.returncode:
            raise MatlabConnectionError('Matlab(TM) process is not active.')

    def _read_until(self, wait_for_str, on_new_output=sys.stdout.write):
        all_output = StringIO()
        output_tail = self.stdout_to_read

        while not wait_for_str in output_tail:
            tail_to_remove = output_tail[:-len(output_tail)]
            output_tail = output_tail[-len(output_tail):]
            if on_new_output: on_new_output(tail_to_remove)
            all_output.write(tail_to_remove)
            if not select.select([self.process.stdout], [], [], 10)[0]:
                raise MatlabConnectionError('timeout')
            new_output = self.process.stdout.read(65536)
            output_tail += new_output

        chunk_to_take, chunk_to_keep = output_tail.split(wait_for_str, 1)

        # output chunk_to_take before wait_for_str (MATLAB_PIPE_COMMAND_ENDED)
        # is added back on.
        if on_new_output:
            on_new_output(chunk_to_take)

        chunk_to_take += wait_for_str
        self.stdout_to_read = chunk_to_keep

        all_output.write(chunk_to_take)
        all_output.seek(0)
        return all_output.read()


    """
    def _wait_for(self, wait_for_str, on_new_output=sys.stdout.write):
      all_output = StringIO()
      output_tail = self.stdout_to_read
      byte_count = 0
      while not wait_for_str in output_tail:
        output_tail = output_tail[:-len(wait_for_str)
        #print 'before read'
        #print output_tail == wait_for_str
        #print repr(output_tail)
        #print repr(wait_for_str)
        #new_output = self.process.stdout.read(1)
        new_output = ''
        conn = self.process.stdout
        flags = fcntl.fcntl(conn, fcntl.F_GETFL)
        if not conn.closed:
          fcntl.fcntl(conn, fcntl.F_SETFL, flags| os.O_NONBLOCK)
        try:
          if not select.select([conn], [], [], 10)[0]:
            raise Exception('timeout')
          new_output = conn.read(65536)
          #try:
          #new_output = os.read(self.process.stdout.fileno(), 65536)
          #new_output = self.process..readad(65536)
        finally:
          if not conn.closed:
            fcntl.fcntl(conn, fcntl.F_SETFL, flags)

        #print 'after read'
        if on_new_output:
          on_new_output(new_output)
        byte_count += len(new_output)
        output_tail += new_output
        output_tail = output_tail[-len(wait_for_str):]
        all_output.write(new_output)
        #if byte_count and byte_count % (2 ** 15) == 0:
        #print '%d kb' % (byte_count / 1024)
      all_output.seek(0)
      print 'recv %d kb' % (byte_count / 1024)
      return all_output.read()
  """

    def _sync_output(self, on_new_output=sys.stdout.write):
        self.process.stdin.write('disp(\'%s\');\n' % self.command_end_string)
        return self._read_until(self.expected_output_end, on_new_output)


if __name__ == '__main__':
    import unittest

    class TestMatlabPipe(unittest.TestCase):
        def setUp(self):
            self.matlab = MatlabPipe()
            self.matlab.open()

        def tearDown(self):
            self.matlab.close()

        def test_eval(self):
            for i in xrange(100):
                ret = self.matlab.eval('disp \'hiush world%s\';' % ('b' * i))
                self.assertTrue('hiush world' in ret)

        def test_put(self):
            self.matlab.put({'A': [1, 2, 3]})
            ret = self.matlab.eval('A')
            self.assertTrue('A =' in ret)

        def test_1_element(self):
            self.matlab.put({'X': 'string'})
            ret = self.matlab.get('X')
            self.assertEquals(ret, 'string')

        def test_get(self):
            self.matlab.eval('A = [1 2 3];')
            ret = self.matlab.get('A')
            self.assertEquals(ret[0], 1)
            self.assertEquals(ret[1], 2)
            self.assertEquals(ret[2], 3)

        def test_error(self):
            self.assertRaises(MatlabError,
                              self.matlab.eval,
                              'no_such_function')

    unittest.main()
