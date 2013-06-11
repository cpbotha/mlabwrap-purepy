#!/usr/bin/env python

""" A quick and extremely dirty hack to wrap matlabpipe/matlabcom as if they
were mlabraw.

Author: Dani Valevski <daniva@gmail.com>
License: MIT
"""
import sys

is_win = sys.platform == 'win32'
if is_win:
    from matlabcom import MatlabCom as MatlabConnection
    from matlabcom import MatlabError as error
else:
    from matlabpipe import MatlabPipe as MatlabConnection
    from matlabpipe import MatlabError as error


def open(matlab_binary_path):

    if is_win:
        ret = MatlabConnection()
        ret.open()

    else:
        ret = MatlabConnection(matlab_binary_path)
        ret.open()

    return ret


def close(matlab):
    matlab.close()


def eval(matlab, exp, log=False):
    if log or is_win:
        matlab.eval(exp)
    else:
        matlab.eval(exp, print_expression=False, on_new_output=None)
    return ''


def get(matlab, var_name):
    return matlab.get(var_name)


def put(matlab, var_name, val):
    matlab.put({var_name: val})
