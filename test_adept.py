#!/usr/bin/env python

"""
Unittests for adept module

Dependencies:
    - python-2.7
    - python-unittest2
    - python-mock
    - pylint
"""

import sys
import os
import os.path
from collections import namedtuple
from itertools import cycle, product
from binascii import crc32
from pdb import Pdb
# ref: https://docs.python.org/dev/library/unittest.html
import unittest2 as unittest
# ref: http://www.voidspace.org.uk/python/mock/index.html
from mock import Mock, NonCallableMock, patch, MagicMock, DEFAULT
from mock import mock_open
from pylint import epylint as lint

# Prefer to keep number of extra files/modules low
# pylint: disable=C0302

class FakeOsPath(object):

    """
    Static testable os.path calls that don't rely on external state
    """

    user_map = {'~': '/home/user1',
                '~user': '/home/user2'}

    env_map = {'$HOME': '/home/user3',
               '${HOME}': '/home/user4'}

    time_map = {'atime': 0,
                'mtime': 1,
                'ctime': 2}

    same_test = cmp

    class FakeOsPathException(ValueError, os.error):
        """Exception raised when fixed data is not available for return"""
        pass

    @staticmethod
    def abspath(path):
        """Return path prefixed with the string '/abs'"""
        return FakeOsPath._pfxpath(path, '/abs')

    @staticmethod
    def exists(path):
        """Return True if the string 'yes' is in path"""
        return "yes" in path

    lexists = exists

    @staticmethod
    def expanduser(path):
        """
        Substitute values in path with keys from FakeOsPath.user_map
        """
        for key, val in FakeOsPath.user_map.items():
            if key in path:
                path = path.replace(key, val)
        return path

    @staticmethod
    def expandvars(path):
        """
        Substitute values in path with keys from FakeOsPath.env_map
        """
        for key, val in FakeOsPath.env_map.items():
            if key in path:
                path = path.replace(key, val)
        return path

    @staticmethod
    def _gettime(path, key):
        try:
            return FakeOsPath.time_map[key]
        except KeyError:
            raise FakeOsPath.FakeOsPathException(path)

    @staticmethod
    def getatime(path):
        """
        Return integer from FakeOsPath.time_map with atime key
        """
        return FakeOsPath._gettime(path, 'atime')

    @staticmethod
    def getmtime(path):
        """
        Return integer from FakeOsPath.time_map with mtime key
        """
        return FakeOsPath._gettime(path, 'mtime')

    @staticmethod
    def getctime(path):
        """
        Return integer from FakeOsPath.time_map with ctime key
        """
        return FakeOsPath._gettime(path, 'ctime')

    @staticmethod
    def getsize(path):
        """
        Return the 32-bit checksum of path
        """
        return crc32(path)

    @staticmethod
    def isfile(path):
        """Return true if the string 'file' is in path"""
        return 'file' in path

    @staticmethod
    def isdir(path):
        """Return true if the string 'dir' is in path"""
        return 'dir' in path

    @staticmethod
    def islink(path):
        """Return true if the string 'link' is in path"""
        return 'link' in path

    @staticmethod
    def ismount(path):
        """Return true if the string 'mount' is in path"""
        return 'mount' in path

    @staticmethod
    def _pfxpath(path, prefix):
        return os.path.join(prefix, path)

    @staticmethod
    def normpath(path):
        """Return path with '/norm' prefixed on the beginning"""
        return FakeOsPath._pfxpath(path, '/norm')

    @staticmethod
    def realpath(path):
        """Return path with '/real' prefixed on the beginning"""
        return FakeOsPath._pfxpath(path, '/real')

    @staticmethod
    def relpath(path):
        """Return path with '/real' prefixed on the beginning"""
        return FakeOsPath._pfxpath(path, '/real')

    @staticmethod
    def samefile(path1, path2):
        """Return result of calling FakeOsPath.same_test on the paths"""
        return FakeOsPath.same_test(path1, path2)

    sameopenfile = samefile
    samestat = samefile


class TestSweet(unittest.TestSuite):

    """
    Returns a iterator over TestCases, sorting items with pylint in name, first
    """

    def __iter__(self):
        first = []
        second = []
        for testcase in super(TestSweet, self).__iter__():
            if 'pylint' in str(testcase).lower():
                first.append(testcase)
            else:
                second.append(testcase)
        first.extend(second)
        return (item for item in first)

# Cause loader to use class above instead of default
unittest.TestLoader.suiteClass = TestSweet


class TestCaseBase(unittest.TestCase):

    """Base class for all other test classes to use"""

    # List of module globs not to enter
    PDBSKIP = ['sys*', 'os', 'unittest2', 'mock', 'pdb']
    # Three letters are faster to type than five
    UUT = 'adept'

    def setUp(self):
        # Keep Debugger close at hand
        self.pdb = Pdb()
        # Keep the unit-under-test contained in this namespace
        self.uut = __import__(self.UUT)

    def tearDown(self):
        # Keep namespace clean (just in case)
        del self.uut
        if self.UUT in sys.modules:
            del sys.modules[self.UUT]

    def trace(self):
        """Enter the pdb debugger, 'n' will step back to self.trace() caller"""
        return self.pdb.set_trace()

    def create_patch(self, name, side_effect):
        """
        Creating a patche on name w/ side_effect; Cleans up _after_ test method!
        """
        patcher = patch(name, side_effect=side_effect)
        thing = patcher.start()
        self.addCleanup(patcher.stop)
        return thing

    def patch_os_path(self, where, call_effects=None):
        """
        Helper for customizing patches to os.path functions

        :param str where: name of module/package to patch in
        :param dict call_effects: Maps function/classes to return mocks
        :return: mapping of call_effects names to return mocks
        :rtype: dict
        """
        if call_effects is not None and not isinstance(call_effects, dict):
            raise TypeError()
        if call_effects is None:
            os_path_names = ['%s.os.path.%s' % (where, name)
                             for name in dir(os.path)
                             if not name.startswith('_')]
            all_nones = [None
                         for _ in xrange(len(os_path_names))]
            call_effects = dict(zip(os_path_names, all_nones))
            # default, everything just returns it's first argument
            for kall in call_effects:
                def _identity(what, *args):
                    del args  # keep pylint happy
                    return what
                call_effects[kall] = _identity
        result = {}
        for kall, returnf in call_effects.iteritems():
            mocked_call = Mock(side_effect=returnf)
            self.create_patch(kall, mocked_call)
            result[kall] = mocked_call

    @staticmethod
    def create_module(path, name, kind=NonCallableMock):
        """
        Helper for create a simple mock-module instance

        :param str name: Fully-qualified module name
        :param Mock kind: Class to use for mocked module
        :return: An instance of kind representing module
        :rtype: kind
        """
        return kind(spec_set=['__file__', '__name__'],
                    name=name,  # for __str__/__repr__
                    __file__="%s.py" % os.path.join(path, name),
                    __name__=name)

    def subtests(self, items):
        """
        Return each item's value inside an active context manager

        :param tuple items: Tuple or list of items to create contexts for
        :returns: Each item's value inside an active context manager
        :rtype: type(item)
        """
        for item in items:
            ctxmgr = self.subTest(item=item)
            with ctxmgr:
                yield item


class TestPylint(TestCaseBase):
    "Run pylint on unittests first, then on UUT"

    # Additional arguments for pylint
    PYLINT = (' --reports=n'
              # --msg-template doesn't work
              #' --msg-template="{msg_id}:{line:3d},{column}: {obj}: {msg}"'
              ' --rcfile="/dev/null"'
              ' --max-args=6'
              ' --min-public-methods=2'
              ' --no-docstring-rgx="(__.*__)|(_.*)|(__init__)|(__new__)"'
              '')
    DISABLE = ("I0011,R0801,R0904,R0921,R0922,C0301,W0511,"
               "C0302,W0212,W0201,W0142")
    # Sensitive to --msg-template if used
    BADWORDS = ('warning', 'error', 'convention')

    @staticmethod
    def _printlint(out, err, skip_first=False):
        sys.stderr.write('\n')
        for line in err:
            sys.stderr.write('%s' % line)
        if skip_first:
            out.readline()
        # buffer for later text  examination
        lines = []
        for line in out:
            sys.stdout.write('%s' % line)
            lines.append(line)
        return lines

    def _pylintrun(self, filepath):
        # todos/fixmes only at first
        out, err = lint.py_run("%s --disable=all --enable=W0511 %s"
                               % (filepath, self.PYLINT),
                               return_std=True)
        self._printlint(out, err)
        # Everything else
        out, err = lint.py_run("%s --disable=%s %s"
                               % (filepath, self.DISABLE, self.PYLINT),
                               return_std=True)
        # todos/fixmes are non-fatal, but actual warnings are
        for line in self._printlint(out, err, True):
            for word in self.BADWORDS:
                # No need for extra assertNotIn details
                if word in line:
                    # Not treated specially by unittest2
                    raise AssertionError("Please fix pylint item(s) above")

    def test_unittest_pylint(self):
        "Run pylint on the unittest module itself"
        self._pylintrun(os.path.basename(__file__))

    def test_uut_pylint(self):
        "Run pylint on the unit under test"
        self._pylintrun(os.path.basename(self.uut.__file__))


# re: to-few-public-methods: This is a context-manager - dunder methods
class PatchedParameters(object):  # pylint: disable=R0903

    """
    Context manager to mocking Parameters class for testing

    :param module uut: Module containing classes to patch
    :param tuple fields: Replacement field names for ParametersData
    :param tuple xforms: Replacement for ParametersData.xforms values
    :param str usage: Replacement usage message for Parameters
    :param bool mock_xforms: Also mock referenced Parameters xform methods
    :returns: context manager instance
    :rtype: Context Manager
    """

    xform_mocks = None
    xform_rval = "!Mocked!"

    def __init__(self, uut, fields=None, xforms=None,
                 usage=None, mock_xforms=False):
        self.mock_xforms = mock_xforms
        self.uut = uut
        self._patchers = []
        if fields is None:
            fields = self.uut.ParametersData.fields
        self.fields = fields
        if usage is None:
            usage = self.uut.Parameters.USAGE
        self.usage = usage
        if xforms is None:
            xforms = ['None' for _ in fields]
        self.xforms = dict(zip(fields, xforms))

    def __enter__(self):
        ppd = namedtuple('ppd', self.fields)
        # Interface requirements
        ppd.fields = ppd._fields
        ppd.asdict = ppd._asdict
        ppd.xforms = self.xforms
        self.patch_n_start(patch('%s.ParametersData' % self.uut.__name__,
                                 ppd))
        # Just in case they're accessed
        self.patch_n_start(patch.object(self.uut.ParametersData, 'fields',
                                        ppd.fields))
        self.patch_n_start(patch.object(self.uut.ParametersData, 'xforms',
                                        ppd.xforms))
        self.patch_n_start(patch.object(self.uut.Parameters, 'STORAGE_CLASS',
                                        ppd))
        self.patch_n_start(patch.object(self.uut.Parameters, 'FIELDS',
                                        ppd.fields))
        self.patch_n_start(patch.object(self.uut.Parameters, 'USAGE',
                                        self.usage))
        if self.mock_xforms:
            # referenced default methods
            patched = dict([(xform, DEFAULT)
                            for xform in self.xforms.values()
                            if xform != 'None'])
            # reference implied by API doc
            patched['mangle_verify'] = DEFAULT
            target = "%s.Parameters" % self.uut.__name__
            # True == {stuff} also!
            self.xform_mocks = self.patch_n_start(patch.multiple(target,
                                                                 autospec=True,
                                                                 **patched))
            for _mock in self.xform_mocks.values():
                _mock.return_value = self.xform_rval
        return self  # allow access mocks

    def __exit__(self, *args, **dargs):
        # Not used here, implimented to maintain signature
        del args
        del dargs
        # Later items may have earlier dependent references
        self._patchers.reverse()
        for patcher in self._patchers:
            patcher.stop()
        return False  # re-raise any exceptions

    def patch_n_start(self, the_patch):
        "Append the_patch to patchers, then start it"
        self._patchers.append(the_patch)
        return self._patchers[-1].start()

    # For convenience
    start = __enter__
    stop = __exit__


class TestNonClasses(TestCaseBase):
    "Set of tests for itmes not contained in UUT defined classes"

    def test_file_path_name_dir(self):
        "Verify file_path_name_dir() only reads from sys.modules"
        # Positive access checked on this
        mock_mod = self.create_module('/path/to', 'mock_mod')
        # Negative access checked on this
        cantouchthis = self.create_module('/dev/null', 'cantouchthis')

        # Don't mess with the real thing
        sys_mods_content = {'mock_mod': mock_mod,
                            'cantouchthis': cantouchthis}
        # Access to the dictionary will also be verified
        _msm_get = lambda key: sys_mods_content[key]
        # Fail the test on any write attempts
        _msm_set = AssertionError("Attempt made to change sys.modules")

        # Act like a regular dictionary
        mock_sys_mod = MagicMock(spec_set=dict)()
        # Allows checking __?etitem__.call_args_list
        mock_sys_mod.__getitem__.side_effect = _msm_get
        mock_sys_mod.__setitem__.side_effect = _msm_set
        with patch.object(sys, 'modules', mock_sys_mod):
            # os.path patches interfear with patching sys.modules
            self.patch_os_path(self.UUT)
            result = self.uut.file_path_name_dir(mock_mod)
            self.assertEqual(len(result), 4)
            self.assertIn('/path/to/mock_mod.py', result)
            self.assertEqual(result.count('/path/to/mock_mod.py'), 4)
            self.assertFalse(mock_sys_mod.called)
            self.assertTrue(mock_sys_mod.__getitem__.called)
            self.assertFalse(mock_sys_mod.__setitem__.called)
            # Verify cantouchthis was not
            mock_sys_mod.__getitem__.assert_called_once_with('mock_mod')

    def test_action_class(self):
        "Verify action_class() API, exceptions, and arguments"
        where = '%s.ActionBase.%%s' % self.UUT
        mocks = {'source': Mock(),
                 'ACTIONMAP': {'foobar': 'baz'}}
        for patcher in (patch('%s.Parameters' % self.UUT),
                        patch(where % 'parameters_source', mocks['source']),
                        patch.dict('%s.ACTIONMAP' % self.UUT,
                                   mocks['ACTIONMAP'], clear=True)):
            try:
                mocks[patcher.attribute] = patcher.start()
                self.addCleanup(patcher.stop)
            except AttributeError, xcept:
                if 'dict' in str(xcept):
                    pass  # patch.dict didn't create a mock (above)
                else:
                    raise
        self.assertEqual(self.uut.ACTIONMAP, mocks['ACTIONMAP'])
        result = self.uut.action_class(Mock(), 'foobar')
        self.assertEqual(result, mocks['ACTIONMAP']['foobar'])
        self.assertRaisesRegex(ValueError, 'bad',
                               self.uut.action_class, 123, 'bad')
        self.assertRaisesRegex(ValueError, '123',
                               self.uut.action_class, 123, 'bad')

    def test_sub_env(self):
        "Verify shell-like substitution from env. vars"
        tests = {'The $foobar jumps $SNA over ${foobar} the $None$${foobar}':
                 'The baz jumps $foobar over baz the $None$baz',

                 ("How many ${SNA}'s can a $foobar$bad if a $baz could "
                  "$bad${bad}"):
                 ("How many $foobar's can a baz$foobar$ if a $baz could "
                  "$foobar$$foobar$"),
                }
        test_env = {'foobar': 'baz', 'SNA': '$foobar', 'bad': '$SNA$'}
        for test_str, expected in tests.iteritems():
            self.assertEqual(self.uut.ActionBase.sub_env(test_env, test_str),
                             expected)


class TestParameters(TestCaseBase):
    "Tests that verify Parameters class instance API"

    def setUp(self):
        super(TestParameters, self).setUp()
        # Convenience for simple cases
        fields = ('one', 'two', 'three', 'four')
        self.simple_pp_dargs = {'uut': self.uut,
                                'fields': fields,
                                'usage': "Test Usage Message"}
        self.simple_source = ('/path/to/script', # automatic
                              '1', '2', '3', '4', '5')
        self.simple_expected = dict(zip(fields,
                                        self.simple_source[1:len(fields)]))
        # Could be done automaticaly, but the line is too long
        self.simple_expected[fields[-1]] = "4 5"

    def test_parameters_source(self):
        "Verify Patched Parameters.STORAGE_CLASS API"
        with PatchedParameters(**self.simple_pp_dargs) as mocked:
            test_params = self.uut.Parameters(source=self.simple_source)
            for ref in (self.uut.Parameters.STORAGE_CLASS,
                        test_params.STORAGE_CLASS,
                        self.uut.ParametersData):
                # Path is ignored, last value would be included in 4th
                test_inst = ref(*self.simple_source[1:-1])
                self.assertTrue(hasattr(test_inst, 'fields'))
                self.assertEqual(test_inst.fields, mocked.fields)
                self.assertTrue(hasattr(test_inst, 'xforms'))
                self.assertEqual(test_inst.xforms, mocked.xforms)
                self.assertEqual(self.uut.Parameters.USAGE,
                                 mocked.usage)

    def test_inst_attributes(self):
        "Verify expected access and content of instance attributes"
        with PatchedParameters(**self.simple_pp_dargs) as mocked:
            test_params = self.uut.Parameters(self.simple_source)
            self.assertEqual(self.uut.Parameters.FIELDS, mocked.fields)
            self.assertEqual(self.uut.Parameters.USAGE, mocked.usage)
            self.assertEqual(len(test_params), len(mocked.fields))
            # Also checks iterator API (last field is greedy)
            for idx, item in enumerate(test_params[:-1]):
                self.assertEqual(item, self.simple_source[idx + 1])
            # Accessing by field-name should also work
            for name in mocked.fields[:-1]:
                self.assertIn(getattr(test_params, name, 'BAD!'),
                              self.simple_source[1:])

    def test_single_source(self):
        "Verify single (first) source used and count/index work"
        patcher = patch('%s.Parameters.default_source' % self.UUT,
                        self.simple_source)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('%s.sys.argv' % self.UUT,
                        self.simple_source)
        patcher.start()
        self.addCleanup(patcher.stop)
        with PatchedParameters(**self.simple_pp_dargs) as mocked:
            test_params1 = self.uut.Parameters()  # Also check this form
            nother_source = ('foo', 'bar', 'baz')
            test_params2 = self.uut.Parameters(nother_source)
            for idx, item in enumerate(test_params1):
                self.assertEqual(item, test_params2[idx])
            for name in mocked.fields:
                self.assertEqual(getattr(test_params1, name, 'BAD!'),
                                 getattr(test_params2, name, '!DAB'))
            # Neither contains values from nother_source
            for bad_val in nother_source:
                for testp in (test_params1, test_params2):
                    self.assertEqual(testp.count(bad_val), 0)
                    self.assertRaises(ValueError, testp.index, bad_val)
                    self.assertRaises(AttributeError, getattr, testp, bad_val)
                    self.assertEqual(testp.USAGE, mocked.usage)
            # first ignored, last is greedy
            expected = tuple(self.simple_source[1:len(mocked.fields)])
            actual = tuple(test_params1.asdict.values()[:-1])
            self.assertEqual(actual, expected)
            actual = tuple(test_params2.asdict.values()[:-1])
            self.assertEqual(actual, expected)

    def test_greedy_last(self):
        "Verify values beyond the second-to-last are gobbled by last field"
        dargs = {'uut': self.uut,
                 'fields': ('one', 'two'),
                 'usage': "Test Usage Message"}
        source = ('/path/to/script', '1', '2', '3', '4', '5')
        with PatchedParameters(**dargs) as mocked:
            test_params = self.uut.Parameters(source)
            self.assertEqual(test_params.two, '2 3 4 5')
            self.assertEqual(test_params.USAGE, mocked.usage)

    def test_asdict(self):
        "Verify asdict method"
        result = {}
        with PatchedParameters(**self.simple_pp_dargs):
            test_params = self.uut.Parameters(self.simple_source)
            result.update(test_params.asdict)
        self.assertEqual(result, self.simple_expected)


    def test_default_xforms(self):
        "Verify default xform methods exist and are used"
        # Many variables are necessary for developer sanity
        # pylint: disable=R0914
        supd = self.uut.ParametersData
        dargs = {'uut': self.uut,
                 'fields': supd.fields,
                 'xforms': tuple([supd.xforms[key] for key in supd.xforms]),
                 'mock_xforms': True}

        # Stub in str(field number) as values for each field
        source = ['/path/to/script']
        source.extend([str(num) for num in xrange(len(supd.fields))])

        # extend scope for verification
        mocks = {}
        result = {}

        with PatchedParameters(**dargs) as patched:
            self.assertTrue(patched.mock_xforms, "No mocks were created")
            mocks.update(patched.xform_mocks)
            test_params = self.uut.Parameters(source)
            result.update(test_params.asdict)

        for field in supd.fields[:-1]:  # last one is greedy
            self.assertEqual(result[field], PatchedParameters.xform_rval)
        # Must be tested separately
        self.assertFalse(mocks['mangle_verify'].called)
        del mocks['mangle_verify']

        # Last greedy field irrelevant, source is exact in number
        expected_values = dict(zip(supd.fields, source[1:]))
        expected_values[supd.fields[-1]] = " ".join(source[len(supd.fields) - 1])

        # Assert actual calls & parameters
        for _mock in mocks.values():
            self.assertTrue(_mock.call_count)
            for name, args, dargs in _mock.mock_calls:
                self.assertEqual(name, '')
                self.assertEqual(dargs, {})
                del args

    def test_mangle_verify(self):
        """
        Verify API/return of mangle_verify method

        Return somepath if checkfn(absolute/normalized somepath) is True

        :param str name: Name of the parameter being checked (for debugging)
        :param callable checkfn: Returns bool when called with a
                                 absolute/normalized path
        :param str somepath: Relative/absolute path to a file/dir
        :param str msgfmt: Message w/ one substitution to include in
                           usage message
        :returns: Absolute/normalized somepath
        :rtype: str

        """
        with PatchedParameters(**self.simple_pp_dargs):
            self.patch_os_path(self.UUT)
            test_params = self.uut.Parameters(self.simple_source)

            _name = 'testing'
            checkfn = Mock()
            checkfn.side_effect = lambda path: path.startswith("foo")
            _somepath = 'foobar'
            _msgfmt = 'msg %s fmt %s'
            result = test_params.mangle_verify(name=_name,
                                               checkfn=checkfn,
                                               somepath=_somepath,
                                               msgfmt=_msgfmt)
            checkfn.assert_called_with('foobar')
            self.assertEqual(result, 'foobar')

            for _re in ('msg testing fmt snafu', self.simple_pp_dargs['usage']):
                self.assertRaisesRegex(RuntimeError, _re,
                                       test_params.mangle_verify, _name,
                                       checkfn, 'snafu', _msgfmt)

class TestActionBaseBase(TestCaseBase):
    "Some common methods used by child-classes"

    def setUp(self):
        super(TestActionBaseBase, self).setUp()
        self.mock_source = Mock()
        self.patchers = []
        self.mocks = {}

    def start_patchers(self, mock_source=None):
        """
        Setup and start all patchers, set self.patchers and self.mocks

        :param mock_source: Stand-in for sys.argv, mock instance if None
        :returns: Mapping of patcher attribute name to created mock
        :rtype: dict
        """
        if mock_source is None:
            mock_source = self.mock_source
        where = '%s.ActionBase.%%s' % self.UUT
        self.mocks['sub_proc'] = Mock()
        from subprocess import Popen
        patchers = (patch('%s.subprocess.Popen' % self.UUT, autospec=Popen,
                          return_value=self.mocks['sub_proc']),
                    patch('%s.Parameters' % self.UUT),
                    patch(where % 'parameters_source', mock_source),
                    patch('%s.ActionBase.init' % self.UUT, autospec=True),
                    patch('%s.ActionBase.action' % self.UUT, autospec=True),
                    patch('%s.ActionBase.__str__' % self.UUT,
                          autospec=True, return_value="ok"))
        self.patchers.extend(patchers)
        for patcher in self.patchers:
            self.mocks[patcher.attribute] = patcher.start()
            self.addCleanup(patcher.stop)
        return self.mocks


class TestActionBase(TestActionBaseBase):
    "Tests that exercize the ActionBase ABC"

    def test_attributes(self):
        "Verify expected access and content of instance attributes"
        self.start_patchers()
        sentinel = '1---nNNn0o0OOOO0!'  # getattr() None is default
        for key, value in {'parameters_source': self.mocks['parameters_source'],
                           'index': None}.iteritems():
            self.assertEqual(getattr(self.uut.ActionBase, key, sentinel),
                             value)

    def test_init_no_action(self):
        "Verify constructor API and initial"
        self.start_patchers()
        # No args
        self.assertRaises(TypeError, self.uut.ActionBase)

        special = {'foo': 'bar',
                   'baz': 'snafu'}
        test_ab = self.uut.ActionBase(123, **special)

        for falsy in (test_ab.parameters_source.called,
                      self.mocks['action'].called):
            self.assertFalse(falsy)
        self.assertEqual(test_ab.index, 123)
        self.assertEqual(test_ab.parameters, self.mocks['Parameters']())
        self.mocks['init'].assert_called_once_with(test_ab,
                                                   foo='bar',
                                                   baz='snafu')

    def test_action_call(self):
        "Verify action method called when instance called"
        self.start_patchers()
        sentinel = Mock()
        self.mocks['action'].return_value = sentinel
        self.assertFalse(self.mocks['action'].called)
        test_ab = self.uut.ActionBase(123)
        self.assertFalse(self.mocks['action'].called)
        result = test_ab()
        self.mocks['action'].assert_called_once_with(test_ab)
        self.assertEqual(result, sentinel)

    def test_make_env(self):
        "Verify make_env API"
        self.start_patchers()
        mock_env = {'cantouchthis': "hammertime", 'SHELL': '/bin/noway'}
        self.uut.SAFE_ENV_VARS = self.uut.SAFE_ENV_VARS + ('cantouchthis',)
        with patch.dict('%s.os.environ' % self.UUT,
                        mock_env, clear=True):
            self.patch_os_path(self.UUT)
            test_ab = self.uut.ActionBase(123)
            result = test_ab.make_env()
            for key in ('cantouchthis', 'WORKSPACE', 'ADEPT_PATH', 'SHELL'):
                self.assertIn(key, result)

    def test_yamlerr(self):
        "Verify yamlerr raises a ValueError"
        self.start_patchers()
        test_ab = self.uut.ActionBase(123)
        strs = ('one_string', 'two_string')
        self.assertRaisesRegex(ValueError, r'(%s)|(%s)' % strs,
                               test_ab.yamlerr, *strs)


class TestCommand(TestActionBaseBase):

    """Exercize Command class"""

    def test_attributes(self):
        "Verify expected access and content of instance attributes"
        self.start_patchers()
        sentinel = '1---nNNn0o0OOOO0!'  # getattr() None is default
        for key, value in {'stdoutfile': None,
                           'stderrfile': None,
                           'exitfile': None}.iteritems():
            self.assertEqual(getattr(self.uut.Command, key, sentinel),
                             value)
        # Not testing any side-effects of init method, only attributes
        init_effect = lambda mockself, **dargs: None
        with patch('%s.Command.init' % self.UUT,
                   autospec=True, side_effect=init_effect) as cmdinit:
            stdoutfile = Mock()
            stderrfile = Mock()
            exitfile = Mock()
            test_cmd = self.uut.Command(index=321,
                                        filepath='whatever',
                                        arguments='foo',
                                        stdoutfile=stdoutfile,
                                        stderrfile=stderrfile,
                                        exitfile=exitfile)
            cmdinit.assert_called_once_with(test_cmd,
                                            filepath='whatever',
                                            stderrfile=stderrfile,
                                            exitfile=exitfile,
                                            stdoutfile=stdoutfile,
                                            arguments='foo')
            self.assertEqual(test_cmd.index, 321)
            self.assertEqual(test_cmd.global_vars, {})
            self.assertEqual(test_cmd.popen_dargs, None)

    def test_init_stdfiles_none(self):
        "Verify method behaves as documented"
        self.start_patchers()
        _mock_open = mock_open()
        # Create required (self.uut.open) to mock where it would be looked up
        # before a builtin
        with patch('%s.open' % self.UUT, _mock_open, create=True):
            self.patch_os_path(self.UUT)
            test_cmd = self.uut.Command(42, filepath='/dev/null')
            self.assertTrue(test_cmd.stdoutfile is None)
            self.assertTrue(test_cmd.stderrfile is not None)
            self.assertEqual(test_cmd.exitfile, None)

    def test_init_stdfiles(self):
        "Verify method behaves as documented"
        self.start_patchers()
        _mock_open = mock_open()
        with patch('%s.open' % self.UUT, _mock_open, create=True):
            self.patch_os_path(self.UUT)
            test_cmd = self.uut.Command(42, filepath='/dev/null',
                                        arguments='--help',
                                        stdoutfile='foo',
                                        stderrfile='bar',
                                        exitfile='baz')
            # Should all be open (mocked) files
            testvals = (test_cmd.stdoutfile, test_cmd.stderrfile,
                        test_cmd.exitfile)
            for item in self.subtests(testvals):
                self.assertIsInstance(item, file)
                # no io happened
                self.assertFalse(item.write.called)
                self.assertFalse(item.read.called)
                self.assertFalse(item.close.called)
                self.assertFalse(item.fileno.called)


    def patch_poll(self, poll_fds):
        "patch select.poll to store/pop fds from poll_fds list"
        from select import POLLIN
        mock_poll = Mock()
        mock_poll.register = Mock(side_effect=poll_fds.append)
        mock_poll.poll = lambda x: [(poll_fds.pop().fileno(), POLLIN)]
        self.patchers.append(patch('%s.poll' % self.UUT, return_value=mock_poll))

    def setup_sppo(self, test_cmd, exitcode=0):
        "Configure subprocess.popen for mocked stdin/stdout"

        child = Mock()
        self.mocks['Popen'].return_value = child
        child.communicate = Mock(side_effect=[('out_leftover',
                                               'err_leftover'),
                                              None])  # fail called > 1 time

        # Allow loops relying on process exiting eventually by poll() call.
        pollcycle = cycle([exitcode, None])  # forever
        def _sppo_poll():
            child.returncode = pollcycle.next()
            return child.returncode
        child.poll = Mock(side_effect=_sppo_poll)

        from subprocess import Popen, PIPE, STDOUT
        # These need to line up with mock_open files (if any)
        special = (None, PIPE, STDOUT)
        if test_cmd.stdoutfile not in special:
            child.stdout = test_cmd.stdoutfile
            child.stdout.fileno = Mock(return_value=1)
        if test_cmd.stderrfile not in special:
            child.stderr = test_cmd.stderrfile
            child.stderr.fileno = Mock(return_value=2)

        return patch('%s.subprocess.Popen' % self.UUT,
                     spec=Popen, return_value=child)

    # Simply many things that need mocking for a single test, refactor if more.
    def test_action_swirly(self):  # pylint: disable=R0914
        "Verify calling instance executes filepath with proper arguments"
        stdoutfiles = ('/standard/out', None)
        stderrfiles = ('/standard/error', None)
        exitfiles = ('/exit/code', None)
        args = '# This is a comment\n"ARG1"\n\t\t\'ARG 2\'  # Another comment\n'

        _mock_open = mock_open()
        self.patchers.append(patch('%s.open' % self.UUT,
                                   _mock_open, create=True))
        poll_fds = []
        self.patch_poll(poll_fds)  # updates self.patchers
        self.start_patchers()  # produces self.mocks

        # Action Base would initialize singleton otherwise
        mock_parameters = self.mocks['Parameters']()
        mock_parameters.verifyfile.side_effect = lambda mock_self, x: str(x)

        self.patch_os_path(self.UUT)
        for out, err, ext in self.subtests(
                product(stdoutfiles, stderrfiles, exitfiles)):
            test_cmd = self.uut.Command(42, filepath='/dev/null',
                                        arguments=args,
                                        stdoutfile=out,
                                        stderrfile=err,
                                        exitfile=ext)
            with self.setup_sppo(test_cmd) as sppo:
                mock_out = _mock_open()
                mock_err = _mock_open()
                with patch('%s.sys.stdout' % self.UUT, mock_out):
                    with patch('%s.sys.stderr' % self.UUT, mock_err):
                        result = test_cmd()
                # stdout/err are needed now :D
                self.assertEqual(sppo.return_value.returncode, 0)
                self.assertEqual(result, 0)  # always
                sppo.return_value.communicate.assert_called_once_with()
                sppo.return_value.poll.assert_called_once_with()
                child = self.mocks['Popen'].return_value
                # N/B same _mock_open used for all, so all output
                # calls go to same open instance, specific checks below
                # are just for clarity until all _mock_open()'s are
                # separated fully. see test_action_nze_file() below
                for location, smock in {'out':mock_out,
                                        'err': mock_err}.items():
                    _file = getattr(child, 'std%s' % location)
                    if _file is not None:  # was a pipe
                        smock.write.assert_any_call('%s_leftover' % location)
                    else:  # was a regular file
                        namefile = 'std%sfile' % location
                        test_cmd_file = getattr(test_cmd, namefile)
                        test_cmd_file.write.assert_any_call('out_leftover')
                        self.assertEqual(test_cmd.popen_dargs[namefile],
                                         test_cmd_file)
                # Written from action() not swirly()
                if test_cmd.exitfile:
                    # pollcycle defined exit code as 0
                    test_cmd.exitfile.write.assert_any_call('0')
                    mock_err.write.assert_any_call('err_leftover')
                # else: return == 0 already tested above

    # Simply many things that need mocking for a single test, refactor if more.
    def test_action_nze_file(self):  # pylint: disable=R0914
        "Verify calling instance executes filepath with proper arguments"
        self.patchers.append(patch('%s.open' % self.UUT,
                                   mock_open(), create=True))
        self.patch_poll([])  # updates self.patchers
        self.start_patchers()  # produces self.mocks

        # Action Base would initialize singleton otherwise
        mock_parameters = self.mocks['Parameters']()
        mock_parameters.verifyfile.side_effect = lambda mock_self, x: str(x)

        self.patch_os_path(self.UUT)

        test_cmd = self.uut.Command(42, filepath='/path/to/file', arguments='',
                                    exitfile='/some/exit/file')
        with self.setup_sppo(test_cmd, exitcode=42):
            # Distinguish stdio from test_cmd.exitfile
            different_open = mock_open()
            with patch('%s.sys.stdout' % self.UUT, different_open()):
                with patch('%s.sys.stderr' % self.UUT, different_open()):
                    result = test_cmd()
            self.assertEqual(result, 0)  # exitfile used
            child = self.mocks['Popen'].return_value
            self.assertEqual(child.returncode, 42)
            exitfile = self.mocks['open']
            exitfile.assert_called_once_with('/some/exit/file', 'wb')
            exitfile().write.assert_called_once_with('42')


class TestPlaybook(TestActionBaseBase):

    """Exercize Playbook class differences from Command class"""

    def test_attributes(self):
        "Verify expected access and content of instance attributes"
        self.start_patchers()
        sentinel = '1---nNNn0o0OOOO0!'  # getattr() None is default
        for key, value in {'limit': None,
                           'varsfile': None}.iteritems():
            self.assertEqual(getattr(self.uut.Playbook, key, sentinel),
                             value)
        self.assertIsInstance(self.uut.Playbook.ansible_cmd, basestring)
        # Not testing any side-effects of real init method
        init_effect = lambda mockself, **dargs: mockself.__dict__.update(dargs)
        with patch('%s.Playbook.init' % self.UUT,
                   autospec=True, side_effect=init_effect) as paraminit:
            test_pb = self.uut.Playbook(index=123,
                                        filepath='whatever',
                                        varsfile='/foo/bar/baz',
                                        limit=True)
            paraminit.assert_called_once_with(test_pb,
                                              filepath='whatever',
                                              varsfile='/foo/bar/baz',
                                              limit=True)
            self.assertIsInstance(test_pb.global_vars, dict)
            self.assertEqual(test_pb.index, 123)
            self.assertEqual(test_pb.filepath, 'whatever')
            self.assertEqual(test_pb.limit, True)
            self.assertEqual(test_pb.varsfile, '/foo/bar/baz')

    def test_init_bad(self):
        "Verify differences in init method from Command class"""
        env = {'ADEPT_PATH':'/foobar',
               'ADEPT_OPTIONAL': '--verbose --sudo'}
        # This was already tested above, and otherwise gets in the way here
        self.patchers.append(patch('%s.Command.make_env' % self.UUT,
                                   lambda mock_self: env))
        self.patchers.append(patch('%s.shlex.split' % self.UUT,
                                   lambda x, _: x.split()))
        self.patchers.append(patch('%s.os.path.isfile' % self.UUT,
                                   lambda x: isinstance(x, MagicMock)))
        self.start_patchers()
        self.mocks['Parameters'].optional = ''
        for dargs in self.subtests(({'index': 42,},
                                    {'filepath': 'hmmmm'},
                                    {'args': (42, '/path/to/file'),
                                     'arguments': 'foo bar baz'},
                                    {'args': (42, ''),
                                     'Beelzebub': 666},
                                    {'args': (42, '/yes/sir'),
                                     'Beelzebub': 666})):
            self.assertRaisesRegex((ValueError, TypeError),
                                   r'(.*init.*takes at least 2 arguments)|'
                                   r'(.*new.*takes exactly 2 arguments)|'
                                   r'(Playbook.+#42)|',
                                   self.uut.Playbook,
                                   *dargs.pop('args', tuple()),
                                   **dargs)
    def test_init_popen(self):
        "Verify multiple instance have distinct popen_"
        # Re-use exact same setup
        self.test_init_bad()
        one = self.uut.Playbook(1, filepath='/path/to/one/file',
                                varsfile='one_varsfile', limit='one',
                                inventory='foo', config='bar')
        self.assertEqual(one.popen_dargs['shell'], False)
        one.popen_dargs['shell'] = True

        two = self.uut.Playbook(1, filepath='/path/to/two/file',
                                varsfile='two_varsfile', limit='two',
                                inventory='bar', config='foo')
        self.assertEqual(two.popen_dargs['executable'],
                         self.uut.Playbook.ansible_cmd)
        two.popen_dargs['executable'] = 'bathroom'

        self.assertFalse(one == two)
        self.assertEqual(one.ansible_cmd, two.ansible_cmd)
        self.assertEqual(one.limit, 'one')
        self.assertEqual(two.limit, 'two')

        self.assertEqual(two.popen_dargs['shell'], False)
        self.assertFalse(one.popen_dargs['shell'] == two.popen_dargs['shell'])

        self.assertEqual(two.popen_dargs['executable'], 'bathroom')
        self.assertFalse(
            one.popen_dargs['executable'] == two.popen_dargs['executable'])
        self.assertNotIn('one', two.popen_dargs.values())
        self.assertNotIn('two', one.popen_dargs.values())


    def test_init_parameters(self):
        "Verify init sets up ansible command correctly"
        # Create required (self.uut.open) to mock where it would be looked up
        # before a builtin
        with PatchedParameters(self.uut):
            self.patch_os_path(self.UUT)
            values = ('/path/to/script',
                      'test_context', 'test_workspace', 'test_yaml', '      ')
            self.uut.ActionBase.parameters_source = values
            test_play = self.uut.Playbook(0, filepath='/dev/null')
            self.assertEqual(test_play.parameters.context, 'test_context')
            self.assertEqual(test_play.parameters.workspace, 'test_workspace')
            self.assertEqual(getattr(test_play.parameters, self.uut.XTN),
                             'test_yaml')
            self.assertEqual(test_play.parameters.optional, '')
            podargs = test_play.popen_dargs
            for word in ('ADEPT_CONTEXT', 'WORKSPACE',
                         'ADEPT_PATH', 'HOSTNAME'):
                self.assertIn(word.upper(), podargs['env'])
                self.assertNotIn(word.lower(), podargs['env'])
            # Excluded when empty
            self.assertNotIn('ADEPT_OPTIONAL', podargs['env'])
            self.assertNotIn('adept_optional', podargs['env'])
            self.assertIn("adept_context='test_context'", podargs['args'])
            # Empty string should be excluded
            self.assertNotIn('adept_optional', podargs['args'])
            self.assertIn('/dev/null', podargs['args'])
            self.assertNotIn('', podargs['args'])
            self.assertNotIn('      ', podargs['args'])  # matches values (above)


class TestVariable(TestCaseBase):

    """Exercize for Variable class"""

    def setUp(self):
        super(TestVariable, self).setUp()
        sup = self.uut.Parameters = MagicMock(spec=list)
        sup.return_value = sup
        supf = self.uut.ParametersData.fields
        sup.__len__ = len(supf)
        argv = [str(_) for _ in xrange(len(supf))]
        sup.__iter__ = dict(zip(supf, argv))
        sup.__contains__ = lambda mockself, key: key in supf
        sup.__getitem__ = supf.__getitem__
        for argidx, key in enumerate(supf):
            setattr(sup, key, argv[argidx])
        self.mockparams = sup
        self.uut.Variable.parameters_source = argv
        self.uut.Variable.__str__ = lambda mockself: ""
        self.env = dict(zip(self.uut.SAFE_ENV_VARS,
                            [str(_) for _ in xrange(len(self.uut.SAFE_ENV_VARS))]))
        self.osenv = patch.dict(self.uut.os.environ, self.env)
        self.osenv.start()
        self.uut.Variable.make_env = Mock(return_value=self.env)

    def tearDown(self):
        if self.osenv:
            self.osenv.stop()
        super(TestVariable, self).tearDown()

    def test_init_simple(self):
        """Verify init(self, name, value=None, from_env=None, from_file=None)"""
        # missing index argument
        self.assertRaises(TypeError, self.uut.Variable, 123)
        # missing name argument
        self.assertRaises(TypeError, self.uut.Variable)
        test_var = self.uut.Variable(123, name='foo')
        self.assertIsInstance(test_var.global_vars, dict)
        self.assertEqual(id(self.uut.ActionBase.global_vars),
                         id(test_var.global_vars))
        self.assertEqual(test_var.name, 'foo')
        self.assertEqual(test_var.index, 123)

    def test_init_api_negative(self):
        """Verify negative documented behavior of init()"""
        with patch.object(self.uut.Variable, 'global_vars', None):
            self.assertRaises(ValueError, self.uut.Variable, 123, name='foo')
            self.assertRaises(ValueError, self.uut.Variable, 123, name='foo',
                              value='this', from_env='will', from_file='fail')
            self.assertRaises(ValueError, self.uut.Variable, 123, name='foo',
                              value='this', from_file='too')
            self.assertRaises(ValueError, self.uut.Variable, 123, name='foo',
                              from_env='and', from_file='this')

    def test_init_api_positive(self):
        """Verify positive documented behavior of init()"""
        for param, value in {'value': 'foo', 'from_env': 'bar',
                             'from_file': "/some/file/to/read"}.items():
            test_var = self.uut.Variable(123, name='foo', **{param: value})
            self.assertEqual(test_var.global_vars, self.uut.Command.global_vars)
            self.assertEqual(self.uut.Command.global_vars, {})
            self.assertEqual(test_var.name, 'foo')

    def test_action(self):
        """Verify action behaves as documented"""
        # Prevent __call__ from printing out a bunch of crap
        mock_call = lambda mockself: mockself.action()
        with patch.object(self.uut.ActionBase, '__call__', mock_call):
            self.uut.ActionBase.global_vars = {}
            for safe in self.uut.SAFE_ENV_VARS:
                test_var = self.uut.Variable(123, name="foo", from_env=safe)
                self.assertEqual(test_var(), 0)  # side effects!!!!
                if test_var.global_vars['foo'] != self.env[safe]:
                    self.trace()
                self.assertEqual(test_var.global_vars['foo'], self.env[safe])

            self.uut.ActionBase.global_vars = {}
            for value in ('foo', 'bar', 'baz'):
                test_var = self.uut.Variable(123, name=value.upper(),
                                             value=value)
                self.assertEqual(test_var(), 0)  # side effects!!!!
            self.assertEqual(self.uut.ActionBase.global_vars,
                             {'BAZ': 'baz', 'FOO': 'foo', 'BAR': 'bar'})



if __name__ == '__main__':
    unittest.main(failfast=True, catchbreak=True, verbosity=2)
