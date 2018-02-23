"""
A simple script to test the behaviour of our refactoring suite.
"""

from __future__ import print_function
from c4d_prototype_converter import refactor

f = refactor.FixUserDataAccess()
refactor.refactor_string([f], 'op[c4d.ID_USERDATA, 9]')

