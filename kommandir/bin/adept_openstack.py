#!/usr/bin/env python2

"""
ADEPT VM provisioning / cleanup script for the openstack ansible group.

Assumed to be running under an exclusive lock to prevent TOCTOU race
and/or clashes with existing named VMs.

Requires:
*  RHEL/CentOS host w/ RPMs:
    * Python 2.7+
    * redhat-rpm-config (base repo)
    * gcc
    * glibc-devel
    * python-virtualenv or python2-virtualenv (EPEL repo)
* Openstack credentials as per:
    https://docs.openstack.org/developer/os-client-config/
"""

import sys
import os
import os.path
import logging
import random
import re
from importlib import import_module
from imp import find_module
import time
import datetime
import argparse
import subprocess
from base64 import b64encode
import shutil
import virtualenv
from flock import Flock

# Operation is discovered by symlink name used to execute script,
# e.g. 'openstack_exclusive_create'
OPERATIONS = ('exclusive_create', 'discover_create', 'destroy', 'reap')

# Stringified form: list of the valid names for invoking this script.
ALLOWED_NAMES = ', '.join(['"openstack_{}"'.format(_) for _ in OPERATIONS])

DESCRIPTION = ('Low dependency script called by ADEPT playbooks'
               ' to manage OpenStack VMs.')

EPILOG = ('Required:  The WORKSPACE environment variable must exist and point to a'
          ' writable directory.  The script must be invoked by link (or symlink)'
          ' named %s'
          ' If named "openstack_%s", VM creation will'
          ' fail if another with the same name already exist.'
          % (ALLOWED_NAMES, OPERATIONS[0]))

# Needed for unittesting so argparse doesn't call system.exit()
ENABLE_HELP = True

# Placeholder, will be set by unittests or under if __name__ == '__main__'
os_client_config = ValueError  # pylint: disable=C0103

# Lock-down versions of os-client-config and all dependencies for stability
# and hashes to assure uncompromised contents
PIP_REQUIREMENTS = """appdirs==1.4.3 --hash=sha256:d8b24664561d0d34ddfaec54636d502d7cea6e29c3eaf68f3df6180863e2166e
Babel==2.4.0 --hash=sha256:e86ca5a3a6bb64b9bbb62b9dac37225ec0ab5dfaae3c2492ebd648266468042f
cliff==2.5.0 --hash=sha256:69be930f40402582a1807d76790cb2e578af7dc70651e0f9fcc600088ecbf99a
cmd2==0.7.0 --hash=sha256:5ab76a1f07dd5fd1cc3c15ba4080265f33b80c7fd748d71bd69a51d60b30f51a
debtcollector==1.13.0 --hash=sha256:a2dc44307da6f17432c63eb947b3bce0c43a9b3f4291fd62e9e6a3969f3c6645
deprecation==1.0 --hash=sha256:36d2a2356ca89fb73f72bfb866a2f28e183535a7f131a3b34036bc48590165b6
funcsigs==1.0.2 --hash=sha256:330cc27ccbf7f1e992e69fef78261dc7c6569012cf397db8d3de0234e6c937ca
functools32==3.2.3.post2 --hash=sha256:89d824aa6c358c421a234d7f9ee0bd75933a67c29588ce50aaa3acdf4d403fa0 --hash=sha256:f6253dfbe0538ad2e387bd8fdfd9293c925d63553f5813c4e587745416501e6d
iso8601==0.1.11 --hash=sha256:c68dbd1b6ecc0c13c1d94116aec79d5d5c3bc7444f99159b968f12d83cbc7fa6
jsonpatch==1.15 --hash=sha256:58ae029a97322a576d8ede954387e84fbdc4dde648a9f84222fdf8c0738ab44c
jsonpointer==1.10 --hash=sha256:24073101a4ade32dd65fba6ba42d0dd4098b4e7628e34cdddfa8176c452b19cc
jsonschema==2.6.0 --hash=sha256:000e68abd33c972a5248544925a0cae7d1125f9bf6c58280d37546b946769a08
keystoneauth1==2.19.0 --hash=sha256:65f326456bcb0bb6bde03a23bb29f85fdb2df10a3e6b65f88a6536829983175d
monotonic==1.3 --hash=sha256:a8c7690953546c6bc8a4f05d347718db50de1225b29f4b9f346c0c6f19bdc286
msgpack-python==0.4.7 --hash=sha256:cc38b1e90b9f5ddc0ffee573bb686268ed95f68bca0e8cc953e32fdda98993bd
netaddr==0.7.19 --hash=sha256:56b3558bd71f3f6999e4c52e349f38660e54a7a8a9943335f73dfc96883e08ca
netifaces==0.10.5 --hash=sha256:59d8ad52dd3116fcb6635e175751b250dc783fb011adba539558bd764e5d628b
openstacksdk==0.9.14 --hash=sha256:7d1a1fcf5586c6b16b409270d5b861d0969ac0a14a1a5ddfdf95df5be5daab89
os-client-config==1.26.0 --hash=sha256:f9a14755f9e498eb5eef553b8b502a08a033fe3993c7152ce077696b1d37c4f4
osc-lib==1.3.0 --hash=sha256:4817d2d7e3332809d822046297650fec70eceff628be419046ebd66577d16b03
oslo.config==3.24.0 --hash=sha256:d79ece78ff3ff5dd075b50c2e69e4359a86546f9e9333bafe5220929549d5f5c
oslo.i18n==3.15.0 --hash=sha256:4d01410167af8b874f44af8515218c3b18171be9796abc9f3d0cf4257b4cbcd4
oslo.serialization==2.18.0 --hash=sha256:1fe5fba373f338402e14266c91d092a73297753ce306d3f1905c1079891fac33
oslo.utils==3.25.0 --hash=sha256:714ee981dfd81c94f9bc16e54788a34d9f427152b082811d118e78b19a9d00c1
packaging==16.8 --hash=sha256:99276dc6e3a7851f32027a68f1095cd3f77c148091b092ea867a351811cfe388
pbr==2.0.0 --hash=sha256:d9b69a26a5cb4e3898eb3c5cea54d2ab3332382167f04e30db5e1f54e1945e45
pip==9.0.1 --hash=sha256:690b762c0a8460c303c089d5d0be034fb15a5ea2b75bdf565f40421f542fefb0
positional==1.1.1 --hash=sha256:ef845fa46ee5a11564750aaa09dd7db059aaf39c44c901b37181e5ffa67034b0
prettytable==0.7.2 --hash=sha256:a53da3b43d7a5c229b5e3ca2892ef982c46b7923b51e98f0db49956531211c4f --hash=sha256:853c116513625c738dc3ce1aee148b5b5757a86727e67eff6502c7ca59d43c36
pyparsing==2.2.0 --hash=sha256:fee43f17a9c4087e7ed1605bd6df994c6173c1e977d7ade7b651292fab2bd010
python-cinderclient==2.0.1 --hash=sha256:aa6c3614514d28bd13006a2220a559f10088ceb54b7506888131f95942c158bc
python-glanceclient==2.6.0 --hash=sha256:e77e63de240f4e183a0960c83eb434774746156571c9ea7e7ef4421365b1a762
python-keystoneclient==3.10.0 --hash=sha256:f30dd06d03f1f85af0cfa18c270e23d2ffd9e776c11c1b534f6ea503e4f31d80
python-novaclient==7.1.0 --hash=sha256:ff46aabc20c39a9fad9ca7aa8f15fd5145852d7385a47e111df7bfd7cd106a65
python-openstackclient==3.9.0 --hash=sha256:3c48e9bbdff8a7679f04fe6a03d609c75e597975f9f43de7ec001719ec554ad9
pytz==2017.2 --hash=sha256:d1d6729c85acea5423671382868627129432fba9a89ecbb248d8d1c7a9f01c67
PyYAML==3.12 --hash=sha256:592766c6303207a20efc445587778322d7f73b161bd994f227adaa341ba212ab
requests==2.13.0 --hash=sha256:1a720e8862a41aa22e339373b526f508ef0c8988baf48b84d3fc891a8e237efb
requestsexceptions==1.2.0 --hash=sha256:f4b43338e69bb7038d2a4ad8cce6b9240e2d272aaf437bd18a2dc9eba25a735c
rfc3986==0.4.1 --hash=sha256:6823e63264be3da1d42b3ec0e393dc8e6d03fd5e28d4291b797c76cf33759061
simplejson==3.10.0 --hash=sha256:953be622e88323c6f43fad61ffd05bebe73b9fd9863a46d68b052d2aa7d71ce2
six==1.10.0 --hash=sha256:0ff78c403d9bccf5a425a6d31a12aa6b47f1c21ca4dc2573a7e2f32a97335eb1
stevedore==1.21.0 --hash=sha256:a015fb150871247e385153e98cc03c373a857157628b4746bfdf8501e82e9a3d
unicodecsv==0.14.1 --hash=sha256:018c08037d48649a0412063ff4eda26eaa81eff1546dbffa51fa5293276ff7fc
warlock==1.3.0 --hash=sha256:d7403f728fce67ee2f22f3d7fa09c9de0bc95c3e7bcf6005b9c1962b77976a06
wrapt==1.10.10 --hash=sha256:42160c91b77f1bc64a955890038e02f2f72986c01d462d53cb6cb039b995cdd9
"""
PIP_REQUIREMENTS = PIP_REQUIREMENTS.strip().splitlines()

# No C/C++ compiler is available in this virtualenv
PIP_ONLY_BINARY = [':all:']
# These must be compiled, but don't require C/C++
PIP_NO_BINARY = ['wrapt', 'PyYAML', 'positional', 'warlock',
                 'PrettyTable', 'cmd2', 'unicodecsv', 'simplejson',
                 'netifaces', 'deprecation', 'functools32']

# Directory path relative to virt. env. dir for signaling completion
PIP_CHECKPATH = 'lib/python2.7/site-packages/os_client_config'

# Exit code to return when --help output is displayed (for unittesting)
HELP_EXIT_CODE = 127

DEFAULT_TIMEOUT = 300

DEFAULT_PRESERVE = 3

# Must use format dictionary w/ keys: name, ip_addr, and uuid
OUTPUT_FORMAT = """---
ansible_host: {ip_addr}
ansible_ssh_host: {ip_addr}
host_uuid: {uuid}
host_name: {name}
ansible_user: root
ansible_ssh_user: root
ansible_connection: ssh
"""

WORKSPACE_LOCKFILE_PREFIX = '.adept_job_workspace'
GLOBAL_LOCKFILE_PREFIX = '.adept_global_floatingip'

def clog(msg):
    """
    Write a message to sys.stderr and flush it
    """
    sys.stderr.write('{0}{1}\n'.format("clog:root:", msg))
    sys.stderr.flush()

class Singleton(object):
    """
    Base class for singletons, every instantiated class is the same object

    :param args: Positional arguments to pass to subclass ``__new__`` and ``__init__``
    :param drgs: Keyword arguments to pass to subclass ``__new__`` and ``__init__``
    """

    # Singleton instance is stored here
    _singleton = None

    def __new__(cls, *args, **dargs):
        if cls._singleton is None:
            cls._singleton = super(Singleton, cls).__new__(cls, *args, **dargs)
            cls._singleton.__new__init__(*args, **dargs)
        return cls._singleton  # instance's ``__init__()`` runs next

    def __new__init__(self, *args, **dargs):
        """
        Creation-time abstraction for singleton, only happens once, ever.

        :param args: Positional arguments to pass to subclass ``__new__`` and ``__init__``
        :param drgs: Keyword arguments to pass to subclass ``__new__`` and ``__init__``
        """
        raise NotImplementedError

    @classmethod
    def __clobber__(cls):
        """
        Provides a way to un-singleton the class, mostly just useful for unittesting.
        """
        cls._singleton = None


class OpenstackLock(Singleton, Flock):
    """
    Singleton security around critical (otherwise) non-atomic Openstack operations
    """

    # Only initialize singleton once
    # pylint: disable=W0231
    def __init__(self, lockfilepath=None):
        del lockfilepath

    def __new__init__(self, lockfilepath=None):
        super(OpenstackLock, self).__init__(lockfilepath)


class OpenstackREST(Singleton):
    """
    State-full centralized cache of Openstack REST API interactions.

    :docs: https://developer.openstack.org/#api
    :param service_sessions: Map of service names to service instances
                             (from os-client-config cloud instance)
    """

    # Cache of current and previous response instances and json() return.
    response_json = None
    response_obj = None
    response_code = None
    # Useful for debugging purposes
    previous_responses = None

    float_ip_selector = staticmethod(random.choice)

    # Current session object
    service_sessions = None

    def __new__init__(self, service_sessions=None):
        if service_sessions is None and self.service_sessions is None:
            raise ValueError("service_sessions must be passed on first instantiation")
        self.service_sessions = service_sessions

    def __init__(self, service_sessions=None):
        del service_sessions
        if self.previous_responses is None:
            self.previous_responses = []

    def raise_if(self, true_condition, xception, msg):
        """
        If true_condition, throw xception with additional msg.
        """
        if not true_condition:
            return None

        if self.previous_responses:
            responses = self.previous_responses + [self.response_obj]
        elif self.response_obj:
            responses = [self.response_obj]
        else:
            responses = []

        logging.debug("Response History:")
        for response in responses:
            logging.debug('  (%s) %s:', response.request.method, response.request.url)
            try:
                logging.debug('    %s', response.json())
            except ValueError:
                pass
            logging.debug('')

        if callable(xception):  # Exception not previously raised
            xcept_class = xception
            xcept_value = xception(msg)
            xcept_traceback = None   # A stack trace would be nice here
            raise xcept_class, xcept_value, xcept_traceback
        else:  # Exception previously raised, re-raise it.
            raise

    def service_request(self, service, uri, unwrap=None, method='get', post_json=None):
        """
        Make a REST API call to uri, return optionally unwrapped json instance.

        :param service: Name of service to request uri from
        :param uri: service URI for get, post, delete operation
        :param unwrap: Optional, unwrap object name from response
        :param method: Optional, http method to use, 'get', 'post', 'delete'.
        :param post_json: Optional, json instance to send with post method
        :raise ValueError: If request was unsuccessful
        :raise KeyError: If unwrap key does not exist in response_json
        :returns: json instance
        """
        session = self.service_sessions[service]
        if self.response_obj is not None:
            self.previous_responses.append(self.response_obj)
        if method == 'get':
            self.response_obj = session.get(uri)
        elif method == 'post':
            self.response_obj = session.post(uri, json=post_json)
        elif method == 'delete':
            self.response_obj = session.delete(uri)
        else:
            self.raise_if(True,
                          ValueError,
                          "Unknown method %s" % method)

        self.response_code = int(self.response_obj.status_code)
        self.raise_if(self.response_code not in [200, 201, 202, 204],
                      ValueError, "Failed: %s request to %s: %s" % (method, uri,
                                                                    self.response_code))

        try:
            self.response_json = self.response_obj.json()
        except ValueError:  # Not every request has a JSON response
            self.response_json = None

        # All responses encode the object under it's name.
        if unwrap:
            self.raise_if(unwrap not in self.response_json,
                          KeyError, "No %s in json: %s"
                          % (unwrap, self.response_json))
            self.response_json = self.response_json[unwrap]
            return self.response_json
        return self.response_json

    def compute_request(self, uri, unwrap=None, method='get', post_json=None):
        """
        Short-hand for ``service_request('compute', uri, unwrap, method, post_json)``
        """
        return self.service_request('compute', uri, unwrap, method, post_json)

    def volume_request(self, uri, unwrap=None, method='get', post_json=None):
        """
        Short-hand for ``service_request('volume', uri, unwrap, method, post_json)``
        """
        return self.service_request('volume', uri, unwrap, method, post_json)

    def child_search(self, key, value=None, alt_list=None):
        """
        Search cached, or alt_list for object with key, or key set to value.

        :param key: String, the key to search for, return list of values.
        :param value: Optional, required value for key, first matching item.
        :param alt_list: Optional, search this instance instead of cache
        :raises TypeError: If self.response_json or alt_json are None
        :raises ValueError: If self.response_json or alt_json are empty
        :raises IndexError: If no item has key with value
        """
        if alt_list is not None:
            search_list = alt_list
        else:
            search_list = self.response_json

        self.raise_if(search_list is None,
                      TypeError, "No requests have been made/cached")

        if value:
            found = [child for child in search_list
                     if child.get(key) == value]
            self.raise_if(not found,
                          IndexError,
                          'Could not find key %s with value %s in %s'
                          % (key, value, search_list))
            return found[0]
        found = [child[key] for child in search_list
                 if key in child]
        return found

    def server_list(self, key='name'):
        """
        Cache list of servers and return list of values for key

        :param key: key to list values for (e.g. 'id')
        :returns: List of values for key
        """
        self.compute_request('/servers', 'servers')
        try:
            return self.child_search(key)
        except IndexError:
            return []

    def server(self, name=None, uuid=None):
        """
        Cache and return details about server name or uuid

        :param name: Optional, exclusive of uuid, name of server
        :param uuid: Optional, exclusive of name, ID of server
        :returns: dictionary of server details
        """
        self.raise_if(not name and not uuid,
                      ValueError,
                      "Must provide either name or uuid")
        if name:
            self.compute_request('/servers', 'servers')
            server_details = self.child_search(key='name', value=name)
            uri = '/servers/%s' % server_details['id']
        elif uuid:
            uri = '/servers/%s' % uuid
        return self.compute_request(uri, unwrap='server')

    def server_ip(self, name=None, uuid=None, net_name=None, net_type='floating'):
        """
        Cache details about server, return ip address of server

        :param name: Optional, exclusive of uuid, name of server
        :param uuid: Optional, exclusive of name, ID of server
        :param net_name: Optional, name of network or None for first-found
        :param net_type: Type of interface to return (e.g. 'fixed')
        :returns: IPv4 address for server or None if none are assigned
        :raises RuntimeError: Server does not exist
        """
        try:
            server_details = self.server(name=name, uuid=uuid)
        except (ValueError, IndexError, KeyError), xcept:  # Very bad, should never happen
            # Assume caller is not catching RuntimeError, so this gets noticed
            self.raise_if(True, RuntimeError,
                          "Server %s/%s disappeared while checking for assigned IP: %s"
                          % (name, uuid, xcept))
        if net_name is None:  # first-found
            net_names = server_details['addresses'].keys()
            net_name = net_names[0]
        iface = self.child_search('OS-EXT-IPS:type', net_type,
                                  server_details['addresses'][net_name])
        return iface['addr']

    def server_expires_at(self, uuid):
        """Cache details about server, return UTC datetime when it should be reaped"""
        try:
            server_details = self.server(name=None, uuid=uuid)
        except (ValueError, IndexError, KeyError):
            logging.debug("Retrieving details about server %s failed. Returning"
                          " infinite lifetime.", uuid)
            return None  # server disappeared, this is okay in a reaper-context
        metadata = server_details.get('metadata', dict(preserve=DEFAULT_PRESERVE))

        try:
            preserve_hours = int(metadata.get('preserve'))
        except (TypeError, ValueError):
            preserve_hours = DEFAULT_PRESERVE

        if preserve_hours < 0:
            return -1  # checking disabled for this server

        iso18601fmt = "%Y-%m-%dT%H:%M:%S.%f"  # e.g. 2017-08-18T20:04:26.000000
        launched_at = server_details.get('OS-SRV-USG:launched_at')
        try:
            launch_stamp = datetime.datetime.strptime(launched_at,
                                                      iso18601fmt).replace(microsecond=0)  # don't care
        except (TypeError, ValueError):
            logging.warning("Invalid server '%s' launched_at stamp '%s',"
                            " perhaps it's being created/destroyed?",
                            server_details.get('name', uuid), launched_at)
            return None

        try:
            lifetime = datetime.timedelta(hours=preserve_hours + 1)  # one hour always "free"
        except OverflowError:
            return None

        return launch_stamp + lifetime

    def server_delete(self, uuid):
        """
        Cache list of servers, try to delete server by uuid.

        :param uuid: Unique ID of server to delete
        :returns: Listing of server IDs (may include uuid)
        """
        try:
            self.compute_request('/servers/%s' % uuid, method='delete')
        # This can fail for any number of reasons, let caller deal with them
        except Exception, xcept:
            logging.warning("server_delete(%s) raised %s", uuid, xcept)
        return self.server_list(key='id')

    def floating_ip(self):
        """
        Cache list of floating IPs, return random un-assigned or None

        :returns: IP address string or None
        """
        self.service_request('network', '/v2.0/floatingips', 'floatingips')
        try:
            # child_search() always/only returns first, match.  Use float_ip_selector() instead.
            search_list = self.response_json
            self.raise_if(search_list is None,
                          TypeError, "No requests have been made/cached")
            found = [child for child in search_list if child.get('status') == 'DOWN']
            self.raise_if(not found, IndexError, 'Could not find available floating IP')
            return self.float_ip_selector(found).get('floating_ip_address')
        except (KeyError, IndexError):
            return None

    def create_floating_ip(self, net_id):
        """
        Create, and cache details about a new floating ip routed to net_id"""
        floatingip = dict(floating_network_id=net_id)
        self.service_request('network', '/v2.0/floatingips',
                             "floatingip", method='post',
                             post_json=dict(floatingip=floatingip))
        return self.response_json['floating_ip_address']

    def attachments(self, name=None, uuid=None):
        """
        Cache details about server, return list of attached volume IDs

        :param name: Optional, exclusive of uuid, name of server
        :param uuid: Optional, exclusive of name, ID of server
        :returns: List of volume IDs currently attached
        """
        long_key = 'os-extended-volumes:volumes_attached'
        return self.child_search('id', alt_list=self.server(name, uuid)[long_key])

    def volume_list(self):
        """
        Cache list of volumes, return list of volume ID's
        """
        self.volume_request('/volumes', 'volumes')
        return self.child_search('id')

    def volume(self, uuid):
        """
        Cache and return details about specific volume uuid

        :param uuid: ID of volume to retrieve details about
        """
        return self.volume_request('/volumes/%s' % uuid, 'volume')


class TimeoutAction(object):
    """
    ABC callable, raises an exception on timeout, or returns non-None value of done()
    """

    sleep = 1  # Sleep time per iteration, avoids busy-waiting.
    # N/B: timeout value referenced outside of class (I know I'm lazy)
    timeout = DEFAULT_TIMEOUT  # (seconds)
    time_out_at = None  # absolute
    timeout_exception = RuntimeError

    def __init__(self, *args, **dargs):
        """
        Initialize instance, perform initial actions, timeout checking on call.

        :param *args: (Optional) list of positional arguments to pass to am_done()
        :param **dargs: (Optional) dictionary of keyword arguments to pass to am_done()
        """
        self._args = args
        self._dargs = dargs

    def __str__(self):
        return ("%s(*%s, **%s) after %0.2f"
                % (self.__class__.__name__, self._args, self._dargs, self.timeout))

    def __call__(self):
        """
        Repeatedly call ``am_done()`` until timeout or non-None return
        """
        result = None
        start = time.time()
        if self.time_out_at is None:
            self.time_out_at = start + self.timeout
        while result is None:
            if time.time() >= self.time_out_at:
                raise self.timeout_exception(str(self))
            time.sleep(self.sleep)
            result = self.am_done(*self._args, **self._dargs)
        return result

    def timeout_remaining(self):
        """Return the amount of time in seconds remaining before timeout"""
        if self.time_out_at is None:
            raise ValueError("%s() gas not been called" % self.__class__.__name__)
        return float(self.time_out_at - time.time())

    def am_done(self, *args, **dargs):
        """
        Abstract method, must return non-None to stop iterating
        """
        raise NotImplementedError


class TimeoutDelete(TimeoutAction):
    """
    Helper class to ensure server is deleted within timeout window

    :param server_id: uuid of server to delete
    :raises ValueError: If more than one server with name is found
    """

    sleep = 2  # Deleting takes a while

    def __init__(self, server_id):
        self.os_rest = OpenstackREST()
        self.os_rest.server_delete(uuid=server_id)
        super(TimeoutDelete, self).__init__(server_id)

    def am_done(self, server_id):
        """Return remaining ids when server_id not found, None if still present."""
        server_ids = self.os_rest.server_list(key='id')
        if server_id in server_ids:
            logging.info("Deleting %s", server_id)
            return None
        clog("Confirmed VM %s does not exist" % server_id)
        return server_ids


class TimeoutCreate(TimeoutAction):
    """Helper class to ensure server creation and state within timeout window"""

    sleep = 2  # Creating takes a while

    POWERSTATES = {
        0: 'NOSTATE',
        1: 'RUNNING',
        3: 'PAUSED',
        4: 'SHUTDOWN',
        6: 'CRASHED',
        7: 'SUSPENDED'}

    # TODO: maybe just pass in a dictionary full of parameters?
    # pylint: disable=E1121
    def __init__(self, name, auth_key_lines, image, flavor,
                 userdata_filepath=None, preserve=None):
        """
        Callable instance to create VM or timeout by raising RuntimeError exception

        :param name: VM Name to create (may already exist - not checked)
        :param auth_key_lines: public key file contents for authorized_keys
        :param image: Name of te image to use for VM
        :param flavor: Name of the flavor to use for VM
        :param userdata_filepath: Optional, path to file containing alternate cloud-config
                                  userdata.  The token '{auth_key_lines}' will be
                                  substituted with the ``auth_key_lines`` JSON list.
        :param preserve: Optional, the number of hours (less one) the VM should be protected from
                         deletion.  Only makes sense when a periodic 'reaper' run is configured.
        """
        self.os_rest = OpenstackREST()

        self.os_rest.compute_request('/flavors', 'flavors')
        flavor_details = self.os_rest.child_search('name', flavor)
        logging.debug("Flavor %s is id %s", flavor, flavor_details['id'])

        # Faster for the server to search for this
        image_details = self.os_rest.service_request('image',
                                                     '/v2/images?name=%s&status=active'
                                                     % image, 'images')
        if len(image_details) > 1:
            logging.warning("Found more than one image named %s", image)
        image_details = image_details[0]
        logging.debug("Image %s is id %s", image, image_details['id'])

        if userdata_filepath:
            with open(userdata_filepath, "rb") as userdata_file:
                # Will throw exception if token is not found
                userdata = userdata_file.read().format(auth_key_lines=str(auth_key_lines))
        else:
            userdata = ("#cloud-config\n"
                        # Because I'm self-centered
                        "timezone: US/Eastern\n"
                        # We will configure our own filesystems/partitioning
                        "growpart:\n"
                        "    mode: off\n"
                        # Don't add silly 'please login as' to .ssh/authorized_keys
                        "disable_root: false\n"
                        # Allow password auth in case it's needed
                        "ssh_pwauth: True\n"
                        # Import all ssh_authorized_keys (below) into these users
                        "ssh_import_id: [root]\n"
                        # public keys to import to users (above)
                        "ssh_authorized_keys: %s\n"
                        # Prevent creating the default, generic user
                        "users:\n"
                        "   - name: root\n"
                        "     primary-group: root\n"
                        "     homedir: /root\n"
                        "     system: true\n" % str(auth_key_lines))
        logging.debug("\nUserdata: %s", userdata)

        server_json = dict(
            name=name,
            flavorRef=flavor_details['id'],
            imageRef=image_details['id'],
            user_data=b64encode(userdata),
        )

        if preserve > -1:
            server_json['metadata'] = dict(preserve=str(preserve))  # hours - 1
        else:
            server_json['metadata'] = dict(preserve="-1")  # forever

        # Immediatly bail out if somehow another server exists with name
        if self.os_rest.server_list().count(name) > 1:
            raise RuntimeError("More than one server %s found during creation", name)

        logging.info("Submitting creation request for %s", name)
        self.os_rest.compute_request('/servers', 'server',
                                     'post', post_json=dict(server=server_json))
        server_id = self.os_rest.response_json['id']
        super(TimeoutCreate, self).__init__(name, server_id)

    def am_done(self, name, server_id):
        """Return server_id if active and powered up, None otherwise"""
        # Immediatly bail out if somehow another server exists with name
        if self.os_rest.server_list().count(name) > 1:
            raise RuntimeError("More than one server %s found during creation", name)
        try:
            server_details = self.os_rest.server(uuid=server_id)
        except ValueError:   # Doesn't exist yet
            return None
        vm_state = server_details['OS-EXT-STS:vm_state']
        power_state = self.POWERSTATES.get(server_details['OS-EXT-STS:power_state'],
                                           'UNKNOWN')
        clog("    id: %s: %s, power %s" % (server_id, vm_state, power_state))
        self.os_rest.raise_if(power_state == 'UNKNOWN',
                              RuntimeError,
                              "Got unknown power-state '%s' from response JSON"
                              % server_details['OS-EXT-STS:power_state'])
        if power_state == 'RUNNING' and vm_state == 'active':
            return server_details['id']
        return None


class TimeoutAssignFloatingIP(TimeoutAction):
    """Helper class to ensure floating IP assigned to server within timeout window"""

    timeout = 120  # Allow provisioning MANY VMs at the same time

    def __init__(self, server_id, router_name=None):
        self.os_rest = OpenstackREST()
        self.os_rest.service_request('network', '/v2.0/routers', "routers")
        if router_name:
            router_details = self.os_rest.child_search('name', router_name)
        else:
            router_details = self.os_rest.response_json[0]
        net_name = router_details['name']
        gw_info = router_details['external_gateway_info']
        net_id = gw_info['network_id']
        logging.debug("Router %s maps to network id %s", net_name, net_id)
        super(TimeoutAssignFloatingIP, self).__init__(server_id, net_name, net_id)

    def _am_done(self, server_id, net_name, net_id):
        # Assigned IPs can be stolen if two processes issue the assign-action
        # for the same IP at close to the same time.  This is only
        # only partly mitigated by locking between processes of this job.
        # For complete protection, all provisioners, across all jobs should use
        # a global file-lock, provided for here by --lockdir.  If unspecified
        # only a job-local lock is used.
        try:
            with OpenstackLock().timeout_acquire_read(self.timeout_remaining()) as osl:
                ip_addr = self.os_rest.server_ip(uuid=server_id, net_name=net_name)
                logging.info("    IP %s assigned", ip_addr)
                return ip_addr
        except (ValueError, IndexError, KeyError):
            with OpenstackLock().timeout_acquire_write(self.timeout_remaining()) as osl:
                if osl is None:
                    raise self.timeout_exception("Timeout acquiring lock")
                floating_ip = self.os_rest.floating_ip()  # Get dis-used IP
                if not floating_ip:  # Didn't get one, must create new
                    logging.debug("    creating new floating IP to %s", net_name)
                    floating_ip = self.os_rest.create_floating_ip(net_id)
                logging.info("    Assigning %s to server id %s",
                             floating_ip, server_id)
                addfloatingip = dict(address=floating_ip)
                try:
                    self.os_rest.compute_request('/servers/%s/action' % server_id,
                                                 unwrap=None, method='post',
                                                 post_json=dict(addFloatingIp=addfloatingip))
                except ValueError:
                    logging.warning("    Assignment failed")
                return None  # Check if ip successfully assigned

    def am_done(self, server_id, net_name, net_id):
        """Return assigned floating IP for server or None if unassigned"""
        # Do this twice to try and catch race where multiple POSTs to
        # '/servers/blah/action' happen at the same time (person or machine)
        if self._am_done(server_id, net_name, net_id):
            return self._am_done(server_id, net_name, net_id)
        # else return None amd try again

class TimeoutAttachVolume(TimeoutAction):
    """
    Helper class to create and attach a volume to a server

    :param server_name: Used only for volume's description
    :param server_id: Name of new volume and host proximity hint
    :param size: Size in gigabytes for new volume
    """

    timeout = 120
    attach_requested = False

    def __init__(self, server_name, server_id, size):
        self.os_rest = OpenstackREST()
        volume = dict(size=size, name=server_id, multiattach=False,
                      description='Created for %s (%s)' % (server_name, server_id))
        # Try to allocate storage on same host as server
        scheduler_hints = dict(same_host=[server_id])
        logging.info("Creating %sGB volume for VM %s", size, server_name)
        post_json = {'volume': volume,
                     'OS-SCH-HNT:scheduler_hints': scheduler_hints}
        self.os_rest.volume_request('/volumes', 'volume',
                                    method='post', post_json=post_json)
        volume_id = self.os_rest.response_json['id']
        super(TimeoutAttachVolume, self).__init__(server_id, volume_id)


    def am_done(self, server_id, volume_id):
        """
        Return volume_id if attachment complete or None if not
        """
        try:
            volume_details = self.os_rest.volume(volume_id)
            status = volume_details['status']
        except (ValueError, IndexError, KeyError):
            return None  # Volume doesn't exist or data is bad
        attachments = self.os_rest.attachments(uuid=server_id)
        attached_to_server = volume_id in attachments
        clog("    %s(%s): attached: %s)" %
             (volume_id, status, attached_to_server))
        if not self.attach_requested and status.lower() != 'available':
            return None
        if not attached_to_server and not self.attach_requested:
            volumeattachment = dict(volumeId=volume_id)
            self.os_rest.compute_request('/servers/%s/os-volume_attachments' % server_id,
                                         'volumeAttachment', method='post',
                                         post_json=dict(volumeAttachment=volumeattachment))
            self.attach_requested = True
            return None
        elif attached_to_server:
            return volume_id
        return None


class TimeoutDeleteVolume(TimeoutAction):
    """Helper class to detach and delete a volume"""

    detach_requests = None

    def __init__(self, volume_id):
        self.os_rest = OpenstackREST()
        self.detach_requests = set()
        self.sentinel = object()  # Needed to detect colliding removal requests
        super(TimeoutDeleteVolume, self).__init__(volume_id)

    def _safe_query(self, volume_id):
        try:  # Prevent TOCTOU: id in list, then vanishes before query
            return self.os_rest.volume(volume_id)
        except Exception:
            volume_ids = self.os_rest.volume_list()
            if volume_id not in volume_ids:
                # Gone now, whew! This is okay, removal was the goal.
                # Satisfy all callers with expected dict() + sentinel
                return dict(id=volume_id, attachments=[], sentinel=self.sentinel)
            raise  # Removal request collision w/o removal, can't handle this.

    def am_done(self, volume_id):
        """
        Return former volume details (or equivalent) if deleted, or None if not
        """
        volume_details = self._safe_query(volume_id)
        if volume_details.get('sentinel', None) == self.sentinel:
            del volume_details['sentinel']
            return volume_details  # removal was the goal
        attachments = self.os_rest.child_search('id',
                                                alt_list=volume_details['attachments'])
        # Server always deleted first, before volume, so...
        if attachments:  # can't handle, was it multi-attach?
            logging.warning("    Found VMs still attached,"
                            "IGNORING volume '%s' and attached VMs '%s'",
                            volume_details.get('name', volume_id),
                            attachments)
            return volume_details  # bail out!
        clog("    Deleting volume %s: status %s" %
             (volume_id, volume_details['status']))
        try:  # Prevent TOCTOU: id vanishes before query
            self.os_rest.volume_request('/volumes/%s' % volume_id,
                                        unwrap=None, method='delete')
        except Exception:
            return volume_details  # Removal was the goal
        clog("     Deleted volume %s" % volume_id)
        return None  # try again


def discover(name=None, uuid=None, router_name=None, private=False, **dargs):
    """
    Write ansible host_vars to stdout if a VM name exists with a floating IP.

    :param name: Name of the VM to search for
    :param uuid: Optional, search by uuid instead of name
    :param router_name: Name of router for address lookup (if more than one)
    :param dargs: Completely ignored
    :raise RuntimeError: Severe conditions which must result in script exit
    :raise IndexError: No server found with name
    """
    del dargs
    os_rest = OpenstackREST()

    # Prefer to operate on ID's because they can never race/clash
    if uuid:
        thing = uuid
    elif name:
        thing = name
    else:
        raise RuntimeError("Must pass name and/or uuid to discover()")

    clog("Trying to discover server %s" % thing)

    nr_found = os_rest.server_list().count(name)
    if nr_found == 1:
        if private:
            net_type = 'fixed'
        else:
            net_type = 'floating'

        # Throws exception if neither name or uuid are set
        ip_addr = os_rest.server_ip(name=name, uuid=uuid,
                                    net_name=router_name, net_type=net_type)
        if name is None:
            name = os_rest.response_json['name']  # Cached by server_ip()
        if uuid is None:
            uuid = os_rest.response_json['id']
        sys.stdout.write(OUTPUT_FORMAT.format(name=name, uuid=uuid, ip_addr=ip_addr))
    elif nr_found > 1:
        raise RuntimeError("More than one server %s found", name)
    else:
        raise IndexError("No server %s found", thing)

def _destroy_volumes(volume_ids, server_id):
    os_rest = OpenstackREST()
    # It's possible volume wasn't attached yet
    try:
        volumes = os_rest.volume_list()
        logging.info("Searching for orphan volumes.")
        for volume in volumes:
            if volume in volume_ids:
                continue
            try:
                details = os_rest.volume(volume)
                if details["name"] == server_id:
                    volume_ids.append(volume)
            except (ValueError, IndexError):
                continue
    except (ValueError, IndexError):
        pass  # Volume named with server_id doesn't exist
    if volume_ids:
        clog("Deleting volumes:")
        for volume_id in volume_ids:
            TimeoutDeleteVolume(volume_id)()

def destroy(name=None, uuid=None, **dargs):
    """
    Destroy VM name (or uuid) and any volumes currently attached to it

    :param name: Name of the VM to destroy
    :param uuid: Optional, search by uuid instead of name
    :param dargs: Ignored
    """
    del dargs
    os_rest = OpenstackREST()

    # Prefer to operate on ID's because they can never race/clash
    if name:
        if os_rest.server_list().count(name) > 1:
            raise RuntimeError("More than one server %s found", name)
    elif uuid is None:
        raise ValueError("Must pass name and/or uuid to destroy()")

    server_id = None
    volume_ids = []
    try:
        volume_ids = os_rest.attachments(name, uuid)  # Caches server details
        server_id = os_rest.response_json.get('id')  # None if not found
    except IndexError:  # Attachments and server not found
        pass

    if not server_id:
        return

    TimeoutDelete(server_id)()
    _destroy_volumes(volume_ids, server_id)


def reap(**dargs):
    """
    Destroy running VMs older than their preserve value plus one (hours)
    """
    dry_run = False
    if dargs.get('dry_run', False):  # argparse converts dry-run -> dry_run
        clog("Reaper operating in dry-run mode, no actions will be taken")
        dry_run = True
    os_rest = OpenstackREST()
    for server_id in os_rest.server_list(key='id'):
        expires_at = os_rest.server_expires_at(server_id)
        server_name = os_rest.response_json["name"]
        now = datetime.datetime.utcnow()
        try:
            if expires_at > now:
                logging.info("Server %s has %s remaining", server_name, expires_at - now)
                continue
            if dry_run:
                clog("Would have destroyed %s" % server_name)
            else:
                clog("Destroying %s" % server_name)
                destroy(uuid=server_id)
        except Exception:
            logging.info("Server %s has indefinite lifetime", server_name)


# Arguments come from argparse, listing them all for clarity of intent
def create(name, pub_key_files, image, flavor,  # pylint: disable=R0913
           private=False, router_name=None, size=None,
           userdata_filepath=None, **dargs):
    """
    Create a new VM with name and authorized_keys containing pub_key_files.

    :param name: Name of the VM to create
    :param pub_key_files: List of ssh public key files to read
    :param image: Name of the openstack image to use
    :param flavor: Name of the openstack VM flavor to use
    :param private: When False, assign a floating IP to VM.
    :param router_name: When private==False, router name to use, or None for first-found.
    :param size: Optional size (gigabytes) volume to attach to VM
    :param userdata_filepath: Optional full path to YAML file containing userdata and,
                              optional ``{auth_key_lines}`` token (JSON).
    :param dargs: Additional parsed arguments, possibly not relevant.
    """
    preserve = dargs.get('preserve', None)
    del dargs  # not otherwise used
    pubkeys = []
    for pub_key_file in pub_key_files:
        logging.info("Loading public key file: %s", pub_key_file)
        with open(pub_key_file, 'rb') as key_file:
            pubkeys.append(key_file.read().strip())
            if 'PRIVATE KEY' in pubkeys[-1]:
                raise ValueError("File %s appears to be a private, not a public, key"
                                 % pub_key_file)

    # Needed in case of exception
    server_id = None
    try:
        # TODO: maybe just pass in a dictionary full of parameters?
        # pylint: disable=E1121
        server_id = TimeoutCreate(name, pubkeys, image, flavor, userdata_filepath, preserve)()
        logging.info("Creation successful, VM %s id %s", name, server_id)

        if size:
            clog("Creating and attaching %sGB volume" % size)
            # name is added to volume description
            TimeoutAttachVolume(name, server_id, int(size))()

        if not private:
            clog("Attempting to assign floating ip on network %s" % router_name)
            TimeoutAssignFloatingIP(server_id, router_name)()
        discover(name=name, uuid=server_id, router_name=router_name, private=private)

    # Must not leak servers or volumes, original exception will be re-raised
    except Exception, xcept:
        logging.error("Create threw %s, attempting to destroy VM.", xcept)
        try:
            destroy(name, server_id)
        finally:
            raise

def parse_args(argv, operation='help'):
    """
    Examine command line arguments, show usage info if inappropriate for operation

    :param argv: List of command-line arguments
    :param operation: one of the supported operations (see script), or "help"
    :returns: Dictionary of parsed command-line options
    """
    # Operate on a copy
    argv = list(argv)
    parser = argparse.ArgumentParser(prog=argv.pop(0),
                                     description=DESCRIPTION,
                                     epilog=EPILOG,
                                     add_help=ENABLE_HELP)

    if 'create' in operation:
        parser.add_argument('--image', '-i', default='CentOS-Cloud-7',
                            help=('If creating a VM, use this (existing) image instead'
                                  ' of "CentOS-Cloud-7" (Optional).'))

        parser.add_argument('--flavor', '-f', default='m1.medium',
                            help=('If creating a VM, use this (existing) flavor'
                                  ' instead of "m1.medium" (Optional).'))

        parser.add_argument('--router', '-r', default=None, dest='router_name',
                            help=('If creating a VM, assign a floating IP routed'
                                  ' through gateway assigned to (existing) ROUTER_NAME,'
                                  ' instead of first-found (Optional).'))

        parser.add_argument('--private', '-p', default=False,
                            action='store_true',
                            help='If creating a VM, do not assign a floating IP (Optional).')

        parser.add_argument('--preserve', default=DEFAULT_PRESERVE, type=int,
                            help='The number of hours beyond one, before'
                                 ' running a reaper script would force deletion.'
                                 ' Set to "-1" for indefinite, otherwise defaults to'
                                 ' %s (Optional).  Takes no action in --dry-run'
                                 ' mode.' % DEFAULT_PRESERVE)

        parser.add_argument('--size', '-s', default=None, type=int,
                            help=('If creating a VM, also create and attach'
                                  ' a volume of SIZE'
                                  ' gigabytes as /dev/vdb (Optional).'))

        parser.add_argument('--userdata', '-u', default=None, dest='userdata_filepath',
                            help=('Path to filename containing cloud-config userdata'
                                  ' YAML. The token "{auth_key_lines}" will be replaced'
                                  ' with a JSON list of the ssh public keys (Optional).'))

        parser.add_argument('--lockdir', '-l', default=None, type=str,
                            help=('Absolute path to directory where global lock file'
                                  ' should be created/used.  Required for parallel'
                                  ' executions.'))

    # All operations get these
    parser.add_argument('--verbose', '-v', default=False,
                        action='store_true',
                        help='Increase logging verbosity.')

    parser.add_argument('--debug', '-d', default=False,
                        action='store_true',
                        help='Increase logging verbosity to maximum.')

    parser.add_argument('--timeout', '-t', default=DEFAULT_TIMEOUT, type=int,
                        help=('Major operations timeout (default %s) in seconds'
                              ' (Optional).' % DEFAULT_TIMEOUT))

    if operation != 'reap':
        parser.add_argument('name',
                            help='The VM name to search for, create, or destroy (required)')
    else:
        parser.add_argument('--dry-run', '-n', default=False,
                            action='store_true',
                            help=('Perform no actual cleanup or other actions, simply'
                                  ' display the actions that would have been taken.'))

    # Consumer of remaining arguments must come last
    if 'create' in operation:
        # "pubkey" will be a list, using "pubkeys" causes --help to be wrong
        # (workaround below)
        parser.add_argument('pubkey', nargs='+',
                            help=('One or more paths to ssh public key files'
                                  ' (only required for "create" actions)'))

    if operation == 'help':
        parser.print_help()
        parser.exit()
        return {}  # for unittests

    args = parser.parse_args(argv)
    logging.debug("Parsed arguments: %s", args)

    # Encode as dictionary, makes parameter passing easier to unittest
    dargs = dict([(n, getattr(args, n))
                  for n in args.__dict__.keys()  # no better way to do ths
                  if n[0] != '_'])

    # Workaround: name should be plural
    if 'pubkey' in dargs:
        dargs['pub_key_files'] = dargs['pubkey']  # Can't use dest (above)
        del dargs['pubkey']

    # Add operation for reference
    dargs['operation'] = operation

    logging.debug("Processed arguments: %s", dargs)

    return dargs


def main(argv, dargs, service_sessions):
    """
    Contains all primary calls for script for easier unit-testing

    :param argv: List of command-line arguments, e.g. sys.argv
    :param service_sessions: Mapping of service names
                             to request-like session instances
    :returns: Exit code integer
    """
    random.seed()
    if 'create' in dargs['operation']:
        clog('Attempting to find VM %s.' % dargs['name'])
        # The general exception is re-raised on secondary exception
        try:
            OpenstackREST(service_sessions)
            discover(**dargs)
            if 'exclusive' in dargs['operation']:  # no exception == found VM
                logging.error("Found existing vm %s, refusing to re-create!"
                              "  Exiting non-zero.", dargs['name'])
                sys.exit(1)
        except IndexError, xcept:
            # Different requirements from discover (yes, this is a bad design)
            dargs = parse_args(argv, 'create')
            # Not an error (yet), will try creating VM next
            logging.warning("Failed to find existing VM: %s.", dargs['name'])
            logging.debug("%s: %s", xcept.__class__.__name__, str(xcept))
            try:
                OpenstackREST(service_sessions)
                clog('Creating new VM %s.' % dargs['name'])
                create(**dargs)
            except:
                logging.error("Original discovery-exception,"
                              " creation exception follows:")
                logging.error(xcept)
                logging.error("Creation exception:")
                raise
    elif dargs['operation'] == 'destroy':
        OpenstackREST(service_sessions)
        clog("Destroying VM %s" % dargs['name'])
        destroy(**dargs)
    elif dargs['operation'] == 'reap':
        OpenstackREST(service_sessions)
        clog("Reaping any VMs older than preserve hours + 1")
        reap(**dargs)


def api_debug_dump():
    """Dump out all API request responses into a file in virtualenv dir"""
    lines = []
    os_rest = OpenstackREST()
    seq_num = 0
    for response in os_rest.previous_responses + [os_rest.response_obj]:
        try:
            lines.append({response.request.method: response.request.url})
            lines[-1]['response'] = response.json()
            lines[-1]['status_code'] = response.status_code
            # These are useful for creating unittest data + debugging unittests
            lines[-1]['sequence_number'] = seq_num
            seq_num += 10
        except (ValueError, AttributeError):
            pass
    _basename = os.path.basename(sys.argv[0])
    prefix = _basename.split('.', 1)[0]
    filepath = os.path.join(workspace, '.venv',
                            '%s_api_responses.json' % prefix)
    # Don't fail main operations b/c missing module
    import json as simplejson
    with open(filepath, 'wb') as debugf:
        simplejson.dump(lines, debugf, indent=2, sort_keys=True)
    logging.info("Recorded all response JSONs into: %s", filepath)


def _pip_upgrade_install(venvdir, requirements, onlybin, nobin):
    bindir = os.path.join(venvdir, 'bin')
    # Otherwise, quoting and line-length become a big problem
    reqs_path = os.path.join(venvdir, 'requirements.txt')
    with open(reqs_path, 'wb') as reqs:
        reqs.writelines([req + '\n' for req in requirements])

    # Need a new-ish version that supports --require-hashes
    pargs = [os.path.join(bindir, 'pip'), 'install',]
    logging.debug(subprocess.check_output(pargs + ['pip==9.0.1'],
                                          close_fds=True, env=os.environ,
                                          stderr=subprocess.STDOUT))
    pargs += ['--require-hashes']
    pargs += ['--only-binary', ','.join(onlybin)]
    pargs += ['--no-binary', ','.join(nobin)]
    pargs += ['--requirement', reqs_path]
    # Sometimes there are glitches, retry this a few times
    tries = 0
    for tries in xrange(3):
        logging.info("Installing packages (try %d): %s", tries, ' '.join(pargs))
        try:
            logging.debug(subprocess.check_output(pargs,
                                                  close_fds=True, env=os.environ,
                                                  stderr=subprocess.STDOUT))
        # last exception will be raised after 3 tries
        except:  # pylint: disable=W0702
            continue
        break
    if tries >= 2:
        raise
    _, pathname, _ = find_module('os_client_config')
    if pathname.startswith(venvdir):
        return import_module('os_client_config')
    raise RuntimeError("Unable to import os_client_config %s from virt. env. %s"
                       % (pathname, venvdir))


def _install(venvdir):
    sfx = "virtual environment under %s" % venvdir
    try:
        if not os.path.isdir(venvdir):
            logging.debug("Setting up new %s", sfx)
            virtualenv.create_environment(venvdir, site_packages=False)
        else:
            logging.debug("Using existing %s", sfx)
    except:
        shutil.rmtree(venvdir, ignore_errors=True)
        raise


def _activate(namespace, venvdir):
    logging.debug("Activating %s", venvdir)
    old_file = namespace['__file__']  # activate_this checks __file__
    try:
        namespace['__file__'] = os.path.join(venvdir, 'bin', 'activate_this.py')
        execfile(namespace['__file__'], namespace)
    finally:
        namespace['__file__'] = old_file
    # No idea why it doesn't set these
    os.environ['PYTHONHOME'] = os.environ['VIRTUAL_ENV'] = venvdir


def _setup(venvdir, requirements, onlybin, nobin):
    try:
        _, pathname, _ = find_module('os_client_config')
    except ImportError:
        pathname = ''
    if pathname.startswith(venvdir):
        return import_module('os_client_config')
    return _pip_upgrade_install(venvdir, requirements, onlybin, nobin)


def activate_and_setup(namespace, venvdir, requirements, onlybin, nobin):
    """
    Create, activate, and install isolated python virtual environment

    :param namespace: Variable namespace to use, e.g. ``globals()``
    :param venvdir: Directory path to contain virtual environment and packages
    :param requirements: List of pip packages and optionally, version requirements.
    :param onlybin: List of pip packages to only install pre-built binaries or
                    magic item ':all:' wildcard (overridden by ``nobin``)
    :param nobin: List of pip packages to build and install (overrides onlybin)
    """
    fmt = "Timeout acquiring %s lock"
    lockfile = Flock()  # Only need a local-workspace lock
    with lockfile.timeout_acquire_write(TimeoutAction.timeout) as vlock:
        if vlock is None:
            raise RuntimeError(fmt, "write")
        _install(venvdir)
    with lockfile.timeout_acquire_read(TimeoutAction.timeout) as vlock:
        if vlock is None:
            raise RuntimeError(fmt, "read")
        _activate(namespace, venvdir)
    with lockfile.timeout_acquire_read(TimeoutAction.timeout) as vlock:
        if vlock is None:
            raise RuntimeError(fmt, "read")
        try:
            _, pathname, _ = find_module('os_client_config')
        except ImportError:
            pathname = ''
        if pathname.startswith(venvdir):
            return import_module('os_client_config')
        else:
            with lockfile.timeout_acquire_write(TimeoutAction.timeout) as vlock:
                if vlock is None:
                    raise RuntimeError(fmt, "read")
                return _setup(venvdir, requirements, onlybin, nobin)


# N/B: Any/All names used here are in the global scope
if __name__ == '__main__':  # pylint: disable=C0103
    # Parse arguments
    basename = re.sub(r'\.py$', '', os.path.basename(sys.argv[0]))
    op_requested = re.sub('^openstack_', '', basename)
    if op_requested == basename:
        logging.error("Script must be invoked with 'openstack_' prefix")
        parse_args(sys.argv, 'help')  # exits
    if op_requested not in OPERATIONS:
        logging.error("Unknown operation '%s'; script must be invoked with"
                      " one of the following names: %s", op_requested,
                      ALLOWED_NAMES)
        parse_args(sys.argv, 'help')  # exits
    _dargs = parse_args(sys.argv, op_requested)
    del basename  # keep global namespace clean

    workspace = os.environ.get('WORKSPACE')
    if workspace is None:
        logging.error(EPILOG)
        sys.exit(2)
    os.chdir(workspace)
    # Control location of caching
    os.environ['HOME'] = workspace
    # Not a standard dictionary, can be modified in-flight, must iterate on keys
    for _name in os.environ.keys():  # pylint: disable=C0201
        if _name.startswith('XDG'):
            del os.environ[_name]

    # initialize default values for all locks
    TimeoutAction.timeout = _dargs['timeout']  # locks cheat and use this
    Flock.def_path = workspace
    Flock.def_prefix = WORKSPACE_LOCKFILE_PREFIX

    # initialize global lock singleton
    if bool(_dargs.get('lockldir')):
        OpenstackLock(os.path.join(_dargs['lockdir'],
                                   '%s.lock' % WORKSPACE_LOCKFILE_PREFIX))
    else:
        OpenstackLock(os.path.join(workspace,
                                   '%s.lock' % GLOBAL_LOCKFILE_PREFIX))

    # Allow early debugging/verbose mode
    logger = logging.getLogger()
    level = logging.WARNING
    if _dargs['debug']:
        level = logging.DEBUG
    elif _dargs['verbose']:
        level = logging.INFO
    logger.setLevel(level)
    del logger  # keep global namespace clean

    os_client_config = activate_and_setup(globals(),
                                          os.path.join(workspace, '.venv'),
                                          PIP_REQUIREMENTS,
                                          PIP_ONLY_BINARY,
                                          PIP_NO_BINARY)
    logging.debug("Loaded %s", os.path.dirname(os_client_config.__file__))
    # Shut down the most noisy loggers
    for noisy_logger in ('stevedore.extension',
                         'keystoneauth.session',
                         'requests.packages.urllib3.connectionpool'):
        shut_me_up = logging.getLogger(noisy_logger)
        shut_me_up.setLevel(logging.WARNING)

    # OpenStackConfig() obliterates os.environ for security reasons
    original_environ = os.environ.copy()
    osc = os_client_config.OpenStackConfig()
    clouds = osc.get_cloud_names()
    if not clouds:
        clouds = ['default']
    os_cloud_name = original_environ.get('OS_CLOUD', osc.get_cloud_names()[0])
    if os_cloud_name:
        logging.info("Using cloud '%s' from %s", os_cloud_name, osc.config_filename)
    else:
        os_cloud_name = 'default'

    cloud = osc.get_one_cloud(os_cloud_name)
    del os_cloud_name  # keep global namespace clean
    service_names = cloud.get_services()
    logging.debug("Initializing openstack services: %s", service_names)
    sessions = dict([(svc, cloud.get_session_client(svc))
                     for svc in service_names])
    del cloud  # keep global namespace clean
    try:
        main(sys.argv, _dargs, sessions)
    finally:
        if _dargs['debug']:
            api_debug_dump()
