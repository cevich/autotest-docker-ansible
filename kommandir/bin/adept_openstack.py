#!/usr/bin/env python2

"""
ADEPT VM provisioning / cleanup script for the openstack ansible group.

Assumed to be running under an exclusive lock to prevent TOCTOU race
and/or clashes with existing named VMs.

Requires:
*  RHEL/CentOS/Fedora host w/ RPMs:
    * redhat-rpm-config (base)
    * python-virtualenv or python2-virtualenv (EPEL)
* Openstack credentials as per:
    https://docs.openstack.org/developer/os-client-config/
* Execution under adept.py exekutir.xn transition file or unittests
"""

import sys
import os
import os.path
import logging
import subprocess
import time
from base64 import b64encode

# Placeholder, will be set by unittests or under if __name__ == '__main__'
os_client_config = ValueError  # pylint: disable=C0103

# Lock-down versions of os-client-config and all dependencies for stability
PIP_REQUIREMENTS = [
    'os-client-config==1.21.1',
    'appdirs==1.4.2',
    'iso8601==0.1.11',
    'keystoneauth1==2.18.0',
    'os-client-config==1.21.1',
    'pbr==1.10.0',
    'positional==1.1.1',
    'PyYAML==3.12',
    'requests==2.13.0',
    'requestsexceptions==1.1.3',
    'six==1.10.0',
    'stevedore==1.20.0',
    'wrapt==1.10.8']
# No C/C++ compiler is available in this virtualenv
PIP_ONLY_BINARY = [':all:']
# These must be compiled, but don't require C/C++
PIP_NO_BINARY = ['wrapt', 'PyYAML', 'positional']

IMAGE = 'CentOS-Cloud-7'
FLAVOR = 'm1.medium'

# Exit code to return when --help output is displayed (for unitesting)
HELP_EXIT_CODE = 127

# Operation is discovered by symlink name used to execute script
DISCOVER_CREATE_NAME = 'openstack_discover_create.py'
DESTROY_NAME = 'openstack_destroy.py'

OUTPUT_FORMAT = """---
inventory_hostname: {name}
ansible_host: {floating_ip}
ansible_ssh_host: {{{{ ansible_host }}}}
"""

class OpenstackREST(object):
    """
    State full cache of Openstack REST API interactions.

    :docs: https://developer.openstack.org/#api
    """

    # The singleton
    _self = None

    # Cache of current and previous response instances and json() return.
    response_json = None
    response_obj = None
    # Useful for debugging purposes
    previous_responses = None

    # Current session object
    service_sessions = None

    def __new__(cls, service_sessions=None):
        if cls._self is None:  # Initialize singleton
            if service_sessions is None:
                raise ValueError("service_sessions must be passed the first time")
            cls._self = super(OpenstackREST, cls).__new__(cls)
            cls.service_sessions = service_sessions
            cls.previous_responses = []
        return cls._self  # return singleton

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

        code = int(self.response_obj.status_code)
        self.raise_if(code not in [200, 201, 202, 204],
                      ValueError, "Failed: %s request to %s: %s" % (method, uri, code))

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
        else:  # return it as-is
            return self.response_json

    def compute_request(self, uri, unwrap=None, method='get', post_json=None):
        """
        Short-hand for ``service_request('compute', uri, unwrap, method, post_json)``
        """
        return self.service_request('compute', uri, unwrap, method, post_json)

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
            try:
                return found[0]
            except IndexError, xcept:
                self.raise_if(True,
                              xcept,
                              'Could not find key %s with value %s in %s'
                              % (key, value, search_list))
        else:
            found = [child[key] for child in search_list
                     if key in child]
            self.raise_if(not found,
                          IndexError,
                          'Could not find key %s in %s'
                          % (key, search_list))
            return found

    def server_list(self):
        """
        Cache and return list of server names or empty list

        :returns: list of strings
        """
        self.compute_request('/servers', 'servers')
        try:
            return self.child_search('name')
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


    def server_ip(self, name=None, uuid=None):
        """
        Cache details about server, return floating ip address of server

        :param name: Optional, name of server to retrieve IP from
        :param uuid: Optional, ID of server to retrieve IP from
        :returns: IPv4 address for server or None if none are assigned
        """
        self.server(name=name, uuid=uuid)
        networks = self.response_json['addresses'].keys()
        self.raise_if(len(networks) > 1,
                      ValueError,
                      "Found %s to be on more than one network" % name)
        self.raise_if(len(networks) == 0,
                      ValueError,
                      "Found %s to be on no networks" % name)
        try:
            ifaces = self.response_json['addresses'][networks[0]]
            floating_iface = self.child_search('OS-EXT-IPS:type', 'floating',
                                               alt_list=ifaces)
            return floating_iface['addr']
        except (KeyError, IndexError), xcept:
            self.raise_if(True,
                          xcept,
                          "Found %s to be on a network"
                          " without a floating IP address" % name)

    def server_delete(self, name=None, uuid=None):
        """
        Cache list of servers, try to delete server by name or uuid

        :param name: Optional, name of server to retrieve IP from
        :param uuid: Optional, ID of server to retrieve IP from
        :returns: any exception that was raised, or None
        """
        self.raise_if(not name and not uuid,
                      ValueError,
                      "Must provide either name or uuid")
        if not uuid:
            try:
                server_details = self.server(name=name)
            except IndexError, xcept:
                return xcept # Server doesn't exist
            uuid = server_details['id']

        try:
            self.compute_request('/servers/%s' % uuid, method='delete')
            return None  # Good result
        # This can fail for any number of reasons, can't list them all
        # pylint: disable=W0703
        except Exception, xcept:
            return xcept


    def floating_ip(self):
        """
        Cache list of floating IPs, return first un-assigned or None

        :returns: IP address string or None
        """
        self.service_request('network', '/v2.0/floatingips', 'floatingips')
        try:
            return self.child_search('status', value='DOWN')["floating_ip_address"]
        except (KeyError, IndexError):
            return None

class TimeoutAction(object):
    """
    ABC callable, raises an exception on timeout, or returns non-None value of done()
    """

    sleep = 0.1  # Sleep time per iteration, avoids busy-waiting.
    timeout = 300.0  # (seconds)
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

    def am_done(self, *args, **dargs):
        """
        Abstract method, must return non-None to stop iterating
        """
        raise NotImplementedError


class TimeoutDeleted(TimeoutAction):
    """Helper class to ensure server is deleted within timeout window"""

    timeout = 60
    delete_result = None

    def __init__(self, name):
        super(TimeoutDeleted, self).__init__(name)
        self.os_rest = OpenstackREST()
        self.os_rest.server_delete(name)

    def am_done(self, name):
        """Return Non-None if server does not appear in server list"""
        if name not in self.os_rest.server_list():
            return name
        else:
            return None


class TimeoutCreate(TimeoutAction):
    """Helper class to ensure server creation and state within timeout window"""

    timeout = 120

    POWERSTATES = {
        0: 'NOSTATE',
        1: 'RUNNING',
        3: 'PAUSED',
        4: 'SHUTDOWN',
        6: 'CRASHED',
        7: 'SUSPENDED'}

    def __init__(self, name, auth_key_lines):
        super(TimeoutCreate, self).__init__(name, auth_key_lines)
        self.os_rest = OpenstackREST()

        self.os_rest.compute_request('/flavors', 'flavors')
        flavor = self.os_rest.child_search('name', FLAVOR)
        logging.debug("Flavor %s is id %s", FLAVOR, flavor['id'])

        # Faster for the server to search for this
        image = self.os_rest.service_request('image',
                                             '/v2/images?name=%s&status=active' % IMAGE,
                                             'images')
        # Validates only one image was found, not really searching
        image = self.os_rest.child_search('name', IMAGE)
        logging.debug("Image %s is id %s", IMAGE, image['id'])

        user_data = ("#cloud-config\n"
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
                     "     homdir: /root\n"
                     "     system: true\n" % auth_key_lines)
        logging.debug("Userdata: %s", user_data)

        server_json = dict(
            name=name,
            flavorRef=flavor['id'],
            imageRef=image['id'],
            user_data=b64encode(user_data)
        )
        logging.info("Submitting creation request")
        self.os_rest.compute_request('/servers', 'server',
                                     'post', post_json=dict(server=server_json))
        self.server_id = self.os_rest.response_json['id']

    def am_done(self, name, auth_key_lines):
        """Return VM's UUID if is active and powered up, None otherwise"""
        del auth_key_lines  # Not needed here
        server_details = self.os_rest.server(uuid=self.server_id)
        vm_state = server_details['OS-EXT-STS:vm_state']
        power_state = self.POWERSTATES.get(server_details['OS-EXT-STS:power_state'],
                                           'UNKNOWN')
        logging.info("     %s: %s, power %s", name, vm_state, power_state)
        if power_state == 'RUNNING' and vm_state == 'active':
            return self.server_id
        elif power_state == 'UNKNOWN':
            raise RuntimeError("Got unknown power-state '%s' from response JSON",
                               % server_details['OS-EXT-STS:power_state'])
        else:
            return None


class TimeoutAssignFloatingIP(TimeoutAction):
    """Helper class to ensure floating IP assigned to server within timeout window"""

    timeout = 30

    def __init__(self, server_id):
        super(TimeoutAssignFloatingIP, self).__init__(server_id)
        self.os_rest = OpenstackREST()

        routers = self.os_rest.service_request('network', '/v2.0/routers', "routers")
        # Assume the first router is the one to use
        gw_info = routers[0]['external_gateway_info']
        self.floating_network_id = gw_info['network_id']
        logging.debug("Router %s network id %s for server id %s",
                      routers[0]['name'],
                      self.floating_network_id,
                      server_id)

    def am_done(self, server_id):
        """Return assigned floating IP for server or None"""
        floating_ip = self.os_rest.floating_ip()  # Get dis-used IP
        if not floating_ip:
            logging.info("Creating new floating IP address on network %s",
                         self.floating_network_id)
            floatingip = dict(floating_network_id=self.floating_network_id)

            self.os_rest.service_request('network', '/v2.0/floatingips',
                                         "floatingip", method='post',
                                         post_json=dict(floatingip=floatingip))
            floating_ip = self.os_rest.response_json['floating_ip_address']
        else:
            logging.info("Found disused ip %s", floating_ip)

        logging.info("Attempting to assign floating IP %s to server id %s",
                     floating_ip, server_id)
        # Addresses TOCTOU: Another server grabs floating_ip before we do
        try:
            addfloatingip = dict(address=floating_ip)
            self.os_rest.compute_request('/servers/%s/action' % server_id,
                                         unwrap=None, method='post',
                                         post_json=dict(addFloatingIp=addfloatingip))
            self.os_rest.server_ip(uuid=server_id)
            return floating_ip
        except (ValueError, KeyError, IndexError):
            logging.info("Assignment failed, retrying")
            return None


def create(name, pub_key_files):
    """
    Create a new VM with name and authorized_keys containing pub_key_files.

    :param name: Name of the VM to create
    :param pub_key_files: List of ssh public key files to read
    """

    pubkeys = []
    for pub_key_file in pub_key_files:
        logging.debug("Loading public key file: %s", pub_key_file)
        with open(pub_key_file, 'rb') as key_file:
            pubkeys.append(key_file.read().strip())
            if 'PRIVATE KEY' in pubkeys[-1]:
                raise ValueError("File %s appears to be a private, not a public, key"
                                 % pub_key_file)
    logging.info("Deleting any partially created VM %s", name)
    TimeoutDeleted(name)()

    try:
        server_id = TimeoutCreate(name, pubkeys)()
        logging.info("Creation successful, attempting to assign floating ip to VM %s", name)
        floating_ip = TimeoutAssignFloatingIP(server_id)()
        logging.info("Floating IP assignment successful, ip %s", floating_ip)
    except:
        # Fire and forget
        os_rest = OpenstackREST()
        os_rest.server_delete(name)
        raise
    sys.stdout.write(OUTPUT_FORMAT.format(name=name, floating_ip=floating_ip))


def discover(name, pub_key_files=None):
    """
    Write ansible host_vars to stdout if a VM name exists with a floating IP.

    :param name: Name of the VM to search for
    :param pub_key_files: Not used
    """
    # Allows earlier CLI parameter error detection
    del pub_key_files

    os_rest = OpenstackREST()
    # Server is useless if it can't be reached
    floating_ip = os_rest.server_ip(name)

    sys.stdout.write(OUTPUT_FORMAT.format(name=name, floating_ip=floating_ip))


def destroy(name):
    """
    Destroy VM name

    :param name: Name of the VM to destroy
    """
    TimeoutDeleted(name)()


def parse_args(argv, operation):
    """
    Examine command line arguments, show usage info if inappropriate for operation

    :param argv: List of command-line arguments
    :param operation: String of 'discover', 'create', or 'destroy'
    :returns: Dictionary of parsed command-line options
    """
    # N/B argv[0] is path to executed command
    argv = argv[1:]
    try:
        parsed_args = dict(name=argv.pop(0))
    except IndexError:
        raise ValueError("Must pass server name as first parameter")
    if operation in ['create', 'discover']:
        if len(argv) < 1:
            raise ValueError("Must pass server name, and one or more"
                             " paths to public ssh key files as parameters")
        parsed_args['pub_key_files'] = set(argv)
    elif operation == 'help':
        logging.info("FIXME: Some useful --help message")
    elif operation not in ('discover', 'destroy'):
        raise ValueError("Unknown operation operation %s, pass --help for help.",
                         operation)
    return parsed_args


def pip_opt_arg(option, arg_list, delim=','):
    """
    If arg_list is non-empty, return option string with args separated by delim.
    """
    if arg_list:
        if option:
            return '%s %s' % (option, delim.join(arg_list))
        else:
            return '%s' % delim.join(arg_list)
    else:
        return ''


def activate_virtualenv():
    """
    Setup and use a virtualenv from $WORKSPACE with required dependencies
    """
    shell = lambda cmd: subprocess.check_call(cmd, close_fds=True, shell=True,
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT)
    venvdir = os.path.join(os.environ['WORKSPACE'], '.virtualenv')
    logging.info("Setting up python virtual environment under %s", venvdir)
    if not os.path.isdir(venvdir):
        shell('virtualenv -p /usr/bin/python2.7 %s' % venvdir)
    # Setup dependencies in venvdir to keep host dependencies low
    activate_this = os.path.join(venvdir, 'bin', 'activate_this.py')
    logging.debug("Activating python virtual environment")
    execfile(activate_this, dict(__file__=activate_this))
    logging.info("Upgrading pip (inside virtual environment)")
    shell('pip install --upgrade pip')
    logging.info("Installing dependencies (inside virtual environment)")
    shell('pip install %s %s %s'
          % (pip_opt_arg('--only-binary', PIP_ONLY_BINARY),
             pip_opt_arg('--no-binary', PIP_NO_BINARY),
             pip_opt_arg('', PIP_REQUIREMENTS, ' ')))
    logging.info("Reactivating python virtual environment")
    execfile(activate_this, dict(__file__=activate_this))


def main(argv, service_sessions):
    """
    Contains all primary calls for script for easier unit-testing

    :param argv: List of command-line arguments, e.g. sys.argv
    :param service_sessions: Mapping of service names
                             to request-like session instances
    :returns: Exit code integer
    """
    _ = OpenstackREST(service_sessions)
    basename = os.path.basename(argv[0])
    if basename == DISCOVER_CREATE_NAME:
        dargs = parse_args(argv, 'discover')
        logging.info('Attempting to find VM %s.', dargs['name'])
        # The general exception is re-raised on secondary exception
        # pylint: disable=W0703
        try:
            discover(**dargs)
        except Exception, xcept:
            # Not an error (yet), will try creating VM next
            logging.warning("Failed to find existing VM: %s.", dargs['name'])
            try:
                dargs = parse_args(argv, 'create')
                logging.info('Attempting to create new VM %s.', dargs['name'])
                create(**dargs)
            except:
                logging.error("Original discovery-exception,"
                              " creation exception follows:")
                logging.error(xcept)
                logging.error("Creation exception:")
                raise
    elif basename == DESTROY_NAME:
        dargs = parse_args(argv, 'destroy')
        logging.info("Destroying VM %s", dargs['name'])
        destroy(**dargs)
    else:
        parse_args(argv, 'help')


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
            # These are useful for creating unitest data + debugging unittests
            lines[-1]['sequence_number'] = seq_num
            seq_num += 10
        except ValueError:
            pass
    basename = os.path.basename(sys.argv[0])
    prefix = basename.split('.', 1)[0]
    filepath = os.path.join(os.environ['WORKSPACE'], '.virtualenv',
                            '%s_api_responses.json' % prefix)
    logging.info("Recording all response JSONs into: %s", filepath)
    # Don't fail main operations b/c missing module
    import simplejson
    with open(filepath, 'wb') as debugf:
        simplejson.dump(lines, debugf, indent=2, sort_keys=True)


if __name__ == '__main__':
    LOGGER = logging.getLogger()
    # Lower default to INFO level and higher
    if [arg for arg in sys.argv if arg == '-v']:
        sys.argv.remove('-v')
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)
    del LOGGER  # no longer needed
    # N/B: Any/All names used here are in the global scope
    # pylint: disable=C0103
    if 'WORKSPACE' not in os.environ:
        raise RuntimeError("Environment variable WORKSPACE is not set,"
                           " it must be a temporary, writeable directory.")

    activate_virtualenv()
    # Import module from w/in virtual environment into global namespace
    os_client_config = __import__('os_client_config', globals(), locals())

    config = os_client_config.get_config()
    sessions = dict([(svc, os_client_config.make_rest_client(svc))
                     for svc in config.get_services()])
    main(sys.argv, sessions)

    try:
        api_debug_dump()
    # This is just for debugging, ignore all errors
    # pylint: disable=W0702
    except:
        pass
