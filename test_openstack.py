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
from urlparse import urlparse
from urlparse import urlunparse
import json as simplejson
import unittest2 as unittest
# ref: http://www.voidspace.org.uk/python/mock/index.html
from mock import Mock
from mock import mock_open
from mock import patch
import test_adept


# For test discovery all test modules must be importable from the top level
# directory of the project.  No clean way to do this that doesn't depend on
# knowledge of the repo directory structure somewhere/somehow.
UUT_REL_PATH = 'kommandir/bin/'
sys.path.insert(0, UUT_REL_PATH)


# There's no other way to append E0012 so older pylint
# ignores the E0704 (only in newer pylint). Monkey-patch
# is needed to disable E0704.  E0704 disabled to allow
# re-raising exception after additional API debugging details.
test_adept.TestPylint.DISABLE += ",E0012,E0704"

# pylint can't count properly when *args, **dargs are in use.
# Disable here, otherwise need to do it on every subclass.
test_adept.TestPylint.DISABLE += ",W0221"

# Especially during delete/remove operations, need to catch
# general exceptions, then deal with them appropriatly.
test_adept.TestPylint.DISABLE += ",W0703"

# pylint doesn't count __init__ as a public method for ABCs
test_adept.TestPylint.DISABLE += ",R0903"

# main shouldn't be subject to only upper-case variable names
test_adept.TestPylint.DISABLE += ",C0103"

class TestCaseBase(test_adept.TestCaseBase):
    """Reuses essental/basic unittest plumbing from adepts unittests"""

    UUT = 'adept_openstack'

    def setUp(self):
        super(TestCaseBase, self).setUp()
        self.uut = __import__(self.UUT)
        # Locking is tested elsewhere
        suf = Mock(spec=self.uut.Flock)
        self.create_patch('%s.Flock' % self.UUT, suf)


class TestPylint(test_adept.TestPylint):
    """Reuses essental pyline-plumbing from adepts unittests, for this module"""

    UUT = TestCaseBase.UUT

    def test_unittest_pylint(self):
        "Run pylint on the unittest module itself"
        self._pylintrun(__file__)

    def test_uut_pylint(self):
        "Run pylint on the unit under test"
        self._pylintrun(self.uut.__file__)


# For internal unittest use, don't care about too-few-public methods
# pylint: disable=R0903
class FakeSession(object):
    """
    Standin for a rest API session that responds with predetermined data
    """

    # List of Mock response objects containing requests with uri and method
    resp_mocks = None

    # List of Mock response objects that were returned successfully
    found_mocks = None

    @staticmethod
    def _xform_uri(uri):
        """
        Enforce uniform test URIs by rewriting method and netloc components
        """
        (_, _, path,
         parameters, query, fragment) = urlparse(uri)
        # Always modified for testing purposes
        return urlunparse(('http', '1.2.3.4', path,
                           parameters, query, fragment))

    def __init__(self, resp_filename=''):
        """
        Setup instance to respond with mocks based on ``api_debug_dump()`` output
        """
        self.resp_filename = resp_filename
        self.resp_mocks = []
        self.found_mocks = []
        if not resp_filename:
            return
        with open(self.resp_filename, 'rb') as resp_file:
            for resp_obj in simplejson.load(resp_file):
                resp = Mock()
                resp.json = Mock(return_value=resp_obj.pop('response', None))
                resp.status_code = resp_obj.pop('status_code', 200)
                resp.sequence_number = resp_obj.pop('sequence_number', -1)
                resp.request = Mock()  # as openstack session api does it
                # Remaining key is method, value is uri
                assert len(resp_obj) == 1  # bad file format
                resp.request.method = str(resp_obj.keys()[0])
                resp.request.uri = self._xform_uri(resp_obj.pop(resp.request.method))
                self.resp_mocks.append(resp)

    def find_mock(self, method, uri, json=None):
        """
        Return mock object cooresponding to a request for uri with method
        """
        del json  # not used
        uri = self._xform_uri(uri)
        for index, response in enumerate(self.resp_mocks):
            if method.lower() != response.request.method.lower():
                continue
            if uri != response.request.uri:
                continue
            # List is ordered, record, remove and return first match
            self.found_mocks.append(self.resp_mocks.pop(index))
            return self.found_mocks[-1]
        if not self.found_mocks:
            seq_no = None
        else:
            seq_no = self.found_mocks[-1].sequence_number
        msg = ("No response found for %s request of %s in %s after sequence number %s"
               % (method, uri, self.resp_filename, seq_no))
        raise KeyError(msg)

    get = lambda self, uri: self.find_mock('GET', uri)
    post = lambda self, uri, json: self.find_mock('POST', uri, json)
    delete = lambda self, uri: self.find_mock('DELETE', uri)


# For internal unittest use, don't care about too-few-public methods
# pylint: disable=R0903
class FakeServiceSessions(object):
    """Standin for service_sessions dictionary, ignores the service nmae"""

    def __init__(self, fake_session):
        self.fake_session = fake_session

    def __getitem__(self, key):
        del key
        return self.fake_session

    def __contains__(self, key):
        del key
        return True


class TestParsedArgs(TestCaseBase):
    """Tests of parse_args function"""

    def setUp(self):
        super(TestParsedArgs, self).setUp()
        self.uut.ENABLE_HELP = False
        self.exit = Mock()
        self.error = Mock()
        self.create_patch('%s.argparse.ArgumentParser.exit' % self.UUT, self.exit)
        self.create_patch('%s.argparse.ArgumentParser.error' % self.UUT, self.error)


    def test_operations(self):
        """Check expected minimum arguments parse in predictable way"""
        # input
        op_argv = dict(destroy=['binary', 'foo',],
                       create=['binary', 'foo', 'bar', 'baz'],
                       discover=['binary', 'baz', 'baz', 'bar'])

        # output
        destroy = dict(name='foo')
        create = dict(name='foo', image='CentOS-Cloud-7',
                      flavor='m1.medium', private=False)
        discover = dict(name='baz', image='CentOS-Cloud-7',
                        flavor='m1.medium', private=False)
        op_expected = dict(destroy=destroy, create=create, discover=discover)

        for operation in ('destroy', 'create', 'discover'):
            parsed_args = self.uut.parse_args(op_argv[operation], operation)
            with self.subTest(operation=operation, expected=op_expected[operation],
                              parsed_args=parsed_args):
                self.assertDictContainsSubset(op_expected[operation], parsed_args)


class TestMain(TestCaseBase):
    """Test main function"""

    def setUp(self):
        super(TestMain, self).setUp()
        self.exit = Mock()
        self.discover = Mock(spec=self.uut.discover)
        self.create = Mock(spec=self.uut.create)
        self.destroy = Mock(spec=self.uut.destroy)
        self.service_sessions = FakeServiceSessions(FakeSession())
        self.create_patch('%s.discover' % self.UUT, self.discover)
        self.create_patch('%s.create' % self.UUT, self.create)
        self.create_patch('%s.destroy' % self.UUT, self.destroy)
        self.create_patch('%s.sys.stderr' % self.UUT, None)
        self.create_patch('%s.sys.exit' % self.UUT, self.exit)

    def test_discover(self):
        """Test main calls discover function"""
        self.uut.main([self.uut.DISCOVER_CREATE_NAME, 'foobar', 'snafu'],
                      dict(operation='discover', name='foobar'),
                      self.service_sessions)
        self.assertFalse(self.destroy.called)
        self.assertFalse(self.create.called)
        self.assertTrue(self.discover.called)

    def test_create(self):
        """Test main calls discover then create functions"""
        # When discovery fails, create is called.
        self.discover.side_effect = IndexError("Unittest error message")
        with self.assertLogs(level='WARNING') as context:
            self.uut.main([self.uut.DISCOVER_CREATE_NAME,
                           'foobar', 'snafu'],
                          dict(operation='create', name='foobar'),
                          self.service_sessions)
        self.assertRegex(' '.join(context.output),
                         r'.*existing.*%s' % 'foobar')
        self.assertFalse(self.destroy.called)
        self.assertTrue(self.create.called)

    def test_create_exception(self):
        """Test main calls discover and raises important exceptions"""
        args = ([self.uut.DISCOVER_CREATE_NAME,
                 'foobar', 'snafu'],
                dict(operation='discover', name='foobar'),
                self.service_sessions)
        msg = "Unittest error message"
        for xcept in (RuntimeError(msg), ValueError(msg), KeyError(msg)):
            with self.subTest(exception=xcept):
                self.discover.side_effect = xcept
                self.assertRaisesRegex(xcept.__class__, msg, self.uut.main, *args)

    def test_create_exclusive(self):
        """Test main does not create when discover successful"""
        with self.assertLogs(level='ERROR') as context:
            # discover will NOT raise, main should exit
            self.uut.main([self.uut.ONLY_CREATE_NAME,
                           'snafu', 'foobar'],
                          dict(operation='exclusive', name='foobar'),
                          self.service_sessions)
        self.assertRegex(' '.join(context.output),
                         r'.*existing.*%s' % 'foobar')
        self.assertFalse(self.destroy.called)
        self.assertTrue(self.discover.called)
        self.assertFalse(self.create.called)
        self.assertTrue(self.exit.called)

    def test_destroy(self):
        """Test main calls destroy function"""
        self.uut.main([self.uut.DESTROY_NAME, 'snafu'],
                      dict(operation='destroy', name='foobar'),
                      self.service_sessions)
        self.assertFalse(self.create.called)
        self.assertFalse(self.discover.called)
        self.assertTrue(self.destroy.called)


class TestVirtEnvPlaceholders(TestCaseBase):
    """Test expected virtualenv module placeholders"""

    def test_os_client_config(self):
        """Verify os_client_config set to placeholder value"""
        self.assertIs(ValueError, self.uut.os_client_config)


class TestOpenstackREST(TestCaseBase):
    """Test OpenstackREST class"""

    def setUp(self):
        super(TestOpenstackREST, self).setUp()
        self.service_sessions = FakeServiceSessions(FakeSession())

    def test_init(self):
        """Test init, singleton, and attributes"""
        first = self.uut.OpenstackREST(self.service_sessions)
        second = self.uut.OpenstackREST(Mock())
        for inst in (first, second):
            self.assertEqual(inst.service_sessions, self.service_sessions)
            self.assertIsNone(inst.response_json)
            self.assertIsNone(inst.response_obj)
            self.assertEqual(inst.previous_responses, [])
            self.assertIsNotNone(inst.service_sessions)

    def test_child_search(self):
        """Test expected exceptions/output from child_search)"""
        whipping_boy = self.uut.OpenstackREST(self.service_sessions)
        self.assertRaises(TypeError, whipping_boy.child_search, 'foo', 'bar')
        self.assertRaises(TypeError, whipping_boy.child_search, 'foo', 'bar', None)
        test_json = [dict(id="foo", data="bar"),
                     dict(id="sna", data="foo"),
                     dict(non="conforming")]
        for whipping_boy.response_json in (None, test_json, 'special'):
            if whipping_boy.response_json == 'special':
                whipping_boy.response_json = test_json
                alt_list = None
            else:
                alt_list = test_json
            self.assertEqual(whipping_boy.child_search('id', alt_list=alt_list),
                             ['foo', 'sna'])
            self.assertEqual(whipping_boy.child_search('data', alt_list=alt_list),
                             ['bar', 'foo'])
            self.assertEqual(whipping_boy.child_search('non', alt_list=alt_list),
                             ['conforming'])
            self.assertEqual(whipping_boy.child_search('id', 'sna', alt_list=alt_list),
                             test_json[1])


class TestDiscoverCreateDestroyBase(TestCaseBase):
    """Base class for discover, create, and delete testing fixtures"""

    # When non-None, filename prefix + self._testMethodNameto to setup FakeSession()
    resp_filename_prefix = None

    def setUp(self):
        super(TestDiscoverCreateDestroyBase, self).setUp()
        open_stdout = mock_open()
        self.create_patch('%s.sys.stdout' % self.UUT, [open_stdout('stdout', 'wb')])
        self.create_patch('%s.sys.stderr' % self.UUT, [open_stdout('stderr', 'wb')])
        self.stdout = self.uut.sys.stdout
        self.stderr = self.uut.sys.stderr
        # Don't actually sleep
        self.create_patch('%s.time.sleep' % self.UUT, lambda x: None)
        # Pretend that time is passing
        self.fake_time_value = 123456
        self.create_patch('%s.time.time' % self.UUT, self.fake_time)
        self.create_patch('%s.time.sleep' % self.UUT, self.fake_time)
        if self.resp_filename_prefix:
            self.filename = '%s%s.json' % (self.resp_filename_prefix, self._testMethodName)
            self.fake_session = FakeSession(self.filename)
            # Un-singleton the singleton
            self.uut.OpenstackREST._self = None
            # Initialize singleton with fake sessions
            self.uut.OpenstackREST(FakeServiceSessions(self.fake_session))

    def fake_time(self, sleep=1):
        """Return fake_time_value after incrementing it by 1"""
        # Minimum increment is one prevents infinite loop
        self.fake_time_value += max(int(sleep), 1)
        return self.fake_time_value

    def certify_stdout(self, name, ip_address):
        """Helper for checking stdout contents contains what playbooks expect"""
        write_calls = self.uut.sys.stdout.write.call_args_list
        written = None
        for write_call in write_calls:
            if len(write_call) and len(write_call[0]) and name in write_call[0][0]:
                written = write_call[0][0]
                break
        self.assertIsNotNone(written)
        for token in ('---', 'host_name', 'ansible_ssh_host', 'ansible_ssh_user', 'ansible_become', 'ansible_connection'):
            self.assertIn(token, written)
        for value in (name, ip_address):
            self.assertIn(value, written)
        self.assertEqual(written[-1], '\n')

    def leftovers(self):
        """Return string to help with checking requests == responses"""
        return ("Disused mock request sequence_numbers in %s: %s"
                % (self.filename,
                   [m.sequence_number for m in self.fake_session.resp_mocks]))


class TestTimeoutAction(TestDiscoverCreateDestroyBase):
    """Test fixture for TimeoutAction class"""

    def test_timeout_action(self):
        """Test TimeoutAction base-class under mocked time.time"""

        # self.uut.TimeoutAction class loaded during setUp()
        # makes pylint very very mad.
        # pylint: disable=E1003,E1002,E0213,E1101,R0201,E1102,W0232
        class TimeoutActionTest(self.uut.TimeoutAction):
            """docstring"""
            timeout = 5
            sleep = 1
            def am_done(inner_self, one, two=3, three=2):
                """docstring"""
                if one == 1 and two == 2 and three == 3:
                    return one + two + three
                else:
                    return None

        inst = TimeoutActionTest(42)
        self.assertRaises(RuntimeError, inst)

        inst = TimeoutActionTest(1, 2)
        self.assertRaises(RuntimeError, inst)

        self.fake_time_value = 123456
        inst = TimeoutActionTest(1, three=3, two=2)
        self.assertEqual(inst(), 6)
        self.assertEqual(inst.time_out_at, 123456 + TimeoutActionTest.timeout + 1)
        expected = 123456 + 1 + 1 + 1
        self.assertEqual(self.fake_time_value, expected)


class TestDiscoverCreate(TestDiscoverCreateDestroyBase):
    """Test discover function with mocked keystone_session"""

    resp_filename_prefix = '.test_openstack_TestDiscoverCreate.'

    def setUp(self):
        super(TestDiscoverCreate, self).setUp()
        self.mock_open = mock_open(read_data='bibble babble')
        self.patched = patch('%s.open' % self.UUT, self.mock_open, create=True)
        self.create_args = ('foobar', ['list', 'of', 'ssh', 'keys'],
                            'image_name', 'flavor_name')

    def test_missing(self):
        """Verify new creation works with available floating ip"""
        with self.patched:
            self.uut.create(*self.create_args)
        self.certify_stdout('foobar', '4.5.6.7')
        # Verify all requests were consumed; requests == replies
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_floating(self):
        """Verify new creation works including new floating ip"""
        with self.patched:
            self.uut.create(*self.create_args)
        self.certify_stdout('foobar', '4.5.6.7')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_found(self):
        """Verify existing VM details are returned with discover call"""
        with self.patched:
            self.uut.discover('foobar')
        self.certify_stdout('foobar', '6.7.8.9')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_privsize(self):
        """Verify creation of private VM with volume"""
        with self.patched:
            self.uut.create(*self.create_args,
                            private=True, router_name='network_name', size=11000000000)
        self.certify_stdout('foobar', '5.4.3.2')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_clash(self):
        """Verify two VMs with same name result in exception"""
        with self.patched:
            self.assertRaisesRegex(RuntimeError,
                                   'More than one server',
                                   self.uut.discover, 'foobar')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())


class TestDestroy(TestDiscoverCreateDestroyBase):
    """Test destroy function with mocked keystone_session"""

    resp_filename_prefix = '.test_openstack_TestDestroy.'

    def test_missing(self):
        """Verify destroy behavior when VM name not found"""
        self.uut.destroy('does_not_exist')
        # Verify all requests were consumed; requests == replies
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_found(self):
        """Verify destroy behavior when VM name found"""
        self.uut.destroy('deleteme')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_other(self):
        """Verify destroy behavior when other servers deleted/created"""
        self.uut.destroy('does_not_exist')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

    def test_clash(self):
        """Verify destroy when two VMs have same name result in exception"""
        self.assertRaisesRegex(RuntimeError,
                               'More than one server',
                               self.uut.destroy, 'deleteme')
        self.assertEqual(self.fake_session.resp_mocks, [], self.leftovers())

if __name__ == '__main__':
    unittest.main(failfast=True, catchbreak=True, verbosity=2)
