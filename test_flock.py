#!/usr/bin/env python

"""
Unittests for adept module

Dependencies:
    - python-2.7
    - python-unittest2
    - python-mock
    - pylint
    - python-jenkins
    - test_adept
"""

import sys
import unittest2 as unittest
# ref: http://www.voidspace.org.uk/python/mock/index.html
#from mock import Mock
#from mock import mock_open
#from mock import patch
import test_adept


# For test discovery all test modules must be importable from the top level
# directory of the project.  No clean way to do this that doesn't depend on
# knowledge of the repo directory structure somewhere/somehow.
UUT_REL_PATH = 'kommandir/bin/'
sys.path.insert(0, UUT_REL_PATH)


# pylint doesn't count __init__ as a public method for ABCs
test_adept.TestPylint.DISABLE += ",R0903"

# main shouldn't be subject to only upper-case variable names
test_adept.TestPylint.DISABLE += ",C0103"

class TestCaseBase(test_adept.TestCaseBase):
    """Reuses essental/basic unittest plumbing from adepts unittests"""

    UUT = 'flock'

    def setUp(self):
        super(TestCaseBase, self).setUp()
        self.uut = __import__(self.UUT)


class TestPylint(test_adept.TestPylint):
    """Reuses essental pylint-plumbing from adepts unittests, for this module"""

    UUT = TestCaseBase.UUT

    def test_unittest_pylint(self):
        "Run pylint on the unittest module itself"
        self._pylintrun(__file__)

    def test_uut_pylint(self):
        "Run pylint on the unit under test"
        self._pylintrun(self.uut.__file__)

# TODO: Actually write some tests

if __name__ == '__main__':
    unittest.main(failfast=True, catchbreak=True, verbosity=2)
