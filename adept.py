#!/usr/bin/env python

"""
Context aware ADEPT playbook shim for arbitrary clouds

Depends on: python-2.7 and PyYAML-3.10
"""

import os
import os.path
import sys
import subprocess
import re
import shlex
from copy import deepcopy
from socket import gethostname
from select import (poll, POLLPRI, POLLIN)
from collections import namedtuple, Sequence
from yaml import load_all

# Prefer LibYAML instead of (slower) python version
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


# Boiler plate where/who am I helper
def file_path_name_dir(module):
    """
    Returns module's relative path, full/abs path, file name, and base dir.
    """
    mod_file = sys.modules[module.__name__].__file__
    mod_path = os.path.abspath(os.path.realpath(mod_file))
    mod_name = os.path.basename(mod_path)
    mod_dir = os.path.basename(os.path.dirname(mod_path))
    return (mod_file, mod_path, mod_name, mod_dir)

(MYFILE, MYPATH,
 MYNAME, MYDIR) = file_path_name_dir(sys.modules[__name__])

MYHOSTNAME = gethostname()

def highlight_normal(color_code=32):  # Green
    """
    If TERM env. var is not dumb or serial, return two color codes
    """
    term = os.environ.get('TERM', 'some_default')
    if 'dumb' not in term and 'serial' not in term:
        highlight = '%c[1;%dm' % (27, color_code)  # dec 27 is escape character
        normal = '%c[0;39m' % 27
    else:
        highlight = ''
        normal = ''
    return (highlight, normal)

def prefix_divider(ending):
    """
    Return ending, prefixed by the system's hostname and a hash-line
    """
    red, _ = highlight_normal(31)
    green, normal = highlight_normal()
    return "%s%s %s%s\n%s%s\n" % (red, MYHOSTNAME,
                                  green, '#' * (50-len(MYHOSTNAME)),
                                  normal, ending)

def pretty_output(heading, keyvals):
    """
    Format heading:, then indented key = val, wrap by prefix_divider()

    :param str heading: The heading line contents
    :param dict keyvals: Mapping of lhs to rhs strings
    :returns: Formatted message
    :rval: str
    """
    cyan, _ = highlight_normal(36)
    blue, normal = highlight_normal(94)
    lines = ["%s:" % str(heading)]
    for key, val in keyvals.iteritems():
        lines.append("    %s%s%s = '%s%s%s'" % (blue, str(key), normal,
                                                cyan, str(val), normal))
    return prefix_divider("\n".join(lines))


# Makes changing/referencing names easier and structured
ParametersDataBase = namedtuple('ParametersData',
                                ['context',    # Arbitrary string
                                 'workspace',  # Store state here
                                 'yaml',       # Path to yaml file
                                 'optional'])  # Extra optional args (greedy)


class ParametersData(ParametersDataBase):

    """
    Fixed representational storage w/ named transforms for Parameters
    """

    asdict = ParametersDataBase._asdict
    fields = ParametersDataBase._fields
    xforms = {'context': 'verifystr',
              'workspace': 'verifydir',
              'yaml': 'verifyfile'}


class Parameters(Sequence):

    """
    Represents structured/massaged command-line parameters

    :param tuple source: Values for parameters, first one is discarded,
                         first-instance's always used.
    """

    # No point in parsing more than once
    _singleton = None
    _initialized = False
    # Default to use when source argument is None
    default_source = sys.argv
    # Makes unitesting easier
    STORAGE_CLASS = ParametersData
    # Saves some typing + required interface of STORAGE_CLASS anyway
    FIELDS = STORAGE_CLASS.fields
    USAGE = ("Usage: %s %s\n"
             "Where the first is a string, second is a directory, "
             "third is an adept yaml file,\n"
             "and any remaining arguments are optional"
             % (MYNAME, " ".join(FIELDS[:-1]))) # last one is greedy

    def __new__(cls, source=None):
        if cls._singleton is not None:
            cls._initialized = True
            return cls._singleton
        else:
            if source is None:
                source = cls.default_source
            cls._singleton = super(Parameters, cls).__new__(cls, source=source)
            return cls._singleton

    def __init__(self, source=None):
        if self._initialized:
            return
        if source is None:
            source = self.default_source
        # Don't count first source value or beyond last (greedy) field
        if len(source) < len(self.FIELDS):
            self.showusage("Not enough arguments")
        # Temporary storage for integration - last field is greedy
        self._data = dict(zip(self.FIELDS[:-1], source[1:len(self.FIELDS)]))
        for key in self._data:
            self._xform(key)  # Modifies inline
        # greedy = gathers up all remaining non-empty options
        remaining = [_.strip() for _ in source[len(self.FIELDS):] if _.strip()]
        self._data[self.FIELDS[-1]] = " ".join(remaining)
        self._xform(self.FIELDS[-1])
        # Make it imutable
        self._data = self.STORAGE_CLASS(**self._data)

    def _xform(self, key):
        sentinel = 'd03sNoTeX157'
        name = self.STORAGE_CLASS.xforms.get(key, sentinel)
        xform_meth = getattr(self, name, sentinel)
        if xform_meth is not sentinel and callable(xform_meth):
            self._data[key] = xform_meth(key, self._data[key])

    def __repr__(self):
        # More compact than __str__
        return str(super(Parameters, self))

    def __str__(self):
        purple, normal = highlight_normal(95)
        return pretty_output("%s%s%s"
                             % (purple, self.__class__.__name__, normal),
                             dict(zip(self.FIELDS,
                                      [self[_] for _ in self.FIELDS])))

    def __len__(self):
        return len(self._data)

    def __getitem__(self, keyidx):
        if isinstance(keyidx, basestring):
            return getattr(self._data, keyidx)
        else:
            return self._data[keyidx]

    def __getattr__(self, key):
        if key in self.FIELDS:
            return self[key]
        else:
            return getattr(super(Parameters, self), key)

    @property
    def asdict(self):
        """
        Returns dictionary-like mapping of parameter fields:values
        """
        return self._data.asdict()

    def next(self):
        """
        Returns next value during iteration
        """
        return (item for item in self._data)

    def showusage(self, errmsg=''):
        """Raise RuntimeError with usage information"""
        raise RuntimeError("%s\n%s" % (errmsg, self.USAGE))

    def mangle_verify(self, name, checkfn, somepath, msgfmt):
        """
        Return somepath if checkfn(absolute/normalized somepath) is True

        :param str name: Name of the parameter being checked (for debugging)
        :param callable checkfn: Returns bool when called with a
                                 absolute/normalized path
        :param str somepath: Relative/absolute path to a file/dir
        :param str msgfmt: Message w/ two str subs. for 'name' and 'somepath'
                           to include in usage message if checkfn() == False
        :returns: Absolute/normalized somepath
        :rtype: str
        """
        if not checkfn(somepath):
            self.showusage(msgfmt % (name, somepath))
        return os.path.abspath(os.path.normpath(os.path.realpath(somepath)))

    def verifyexist(self, name, thingpath,
                    msgfmt="%s Error: %s does not exist"):
        """
        Show usage if thingpath does not exist in the filesystem

        :param str name: Name of the parameter being checked
        :param str thingpath: Relative/Absolute path to a filesystem object
        :param str msgfmt: Non-default error message to display
        :returns: mangle_verify() of thingpath
        :rtype: str
        """
        return self.mangle_verify(name, os.path.exists, thingpath, msgfmt)

    def verifydir(self, name, dirpath,
                  msgfmt="%s Error: %s is not a directory"):
        """
        Similar to verifyexist, but for a directory
        """
        return self.mangle_verify(name, os.path.exists, dirpath, msgfmt)

    def verifyfile(self, name, filepath,
                   msgfmt="%s Error: %s is not a file"):
        """
        Similar to verifyexist, but for a file (including "-": stdin)
        """
        if filepath == '-':
            return '-'
        else:
            return self.mangle_verify(name, os.path.exists, filepath, msgfmt)

    def verifystr(self, name, one_word,
                  msgfmt="%s Error: Unacceptable string: '%s'"):
        """
        Verify one_word is a string containing only a single word

        :param str name: Name of the parameter being checked
        :param str one_word: Sequence containing alpha-numerics, -, or _
        :param str msgfmt: Non-default error message to display
        :returns: one_word
        :rtype: basestring
        """
        # Easier than complicating the conditional
        test_str = one_word.replace('_', '').replace('-', '')
        if isinstance(one_word, basestring) and test_str.isalnum():
            return one_word
        else:
            self.showusage(msgfmt % (name, one_word))


class ActionBase(object):

    """
    ABC for all yaml-based action definitions, abstract method: action()

    :param int index: Index number for this yaml map - aids in debugging
    :param str filepath: Relative/Absolute path to file for this action
    :param dict dargs: key/values from the yaml node for the specific action
    """

    # Must always be used to inst. Parameters class
    parameters_source = None
    # In exceptions, this makes finding the offending section easier
    index = None
    # Verified copy of filepath argument to __init__
    filepath = None

    def __init__(self, index, filepath, **dargs):
        # These help with debugging yaml
        self.index = index

        new_env = self.make_env()
        try:
            filepath = self.sub_env(new_env, filepath)
            self.filepath = self.parameters.verifyfile(self.parameters.context,
                                                       filepath)
        except RuntimeError, xcept:
            self.yamlerr("initializing", xcept.message)

        # Pass-through whatever else was in the yaml node
        self.init(**dargs)

    def __call__(self):
        sys.stderr.write('%s\n' % self)
        return self.action()

    def __str__(self, additional=None):
        """
        Return string formated representation of instance

        :param dict additional: Extra key/val dict to include (optional)
        """
        keyvals = {'yaml node': '%d' % self.index,
                   'filepath': '%s' % self.filepath}
        if additional:
            keyvals.update(additional)
        return pretty_output(self.__class__.__name__, keyvals)

    @property
    def parameters(self):
        """
        Convenience attribute, represents a Parameters() instance to caller
        """
        return Parameters(self.parameters_source)

    def make_env(self):
        """
        Return updated environment dict with WORKSPACEW & ADEPT_PATH
        """
        env = os.environ.copy()
        env.update({'WORKSPACE': self.parameters.workspace,
                    'ADEPT_PATH': os.path.dirname(MYPATH),
                    'HOSTNAME': MYHOSTNAME})
        return env

    @staticmethod
    def sub_env(from_env, in_string):
        """
        Return result of shell-like substitution in_string from_env
        """
        if in_string:
            for key, value in from_env.iteritems():
                regex = r'(\${%s\})|(\$%s)' % (key, key)
                in_string = re.sub(regex, value, str(in_string))
        return in_string

    def yamlerr(self, doing, happened):
        """
        Raises a ValueError with message including doing and happened
        """
        parameters = Parameters(self.parameters_source)
        raise ValueError("Error: While %s for %s action item #%d "
                         "in %s with context %s: %s" %
                         (doing, self.__class__.__name__,
                          self.index, parameters.yaml,
                          parameters.context, happened))

    def init(self, **dargs):
        """
        Called at end of __init__(), setup action-specific state.

        :param dict dargs:  key/values from the yaml node for the specific action
        """
        raise NotImplementedError(str(dargs))

    def action(self):
        """
        Abstract method, stands in for __call__, takes no arguments

        :returns: Optional output string from the action
        :rtype: str
        """
        raise NotImplementedError()


class Command(ActionBase):

    """
    Handler class for command action-type yaml item

    :param str arguments: Shell-string of command-line arguments.
    :param str stdoutfile: Filename to send data, None for stdout.
    :param str stderrfile: Filename to send data, None for stderr.
    :param str exitfile: Filename to write exit code, None to return it.
    """

    # defaults
    popen_dargs = {'bufsize': 1,   # line buffered for swirly
                   'close_fds': False,  # Allow stdio passthrough
                   'shell': False}

    # Output file objects or special subprocess tokens
    stdoutfile = None
    stderrfile = None
    exitfile = None

    def __init__(self, index, filepath, **dargs):
        # Don't share dict reference across instances
        self.popen_dargs = deepcopy(self.popen_dargs)
        super(Command, self).__init__(index, filepath, **dargs)

    def __str__(self, additional=None):
        mine = {'cmd': " ".join(self.popen_dargs['args'])}
        if additional:
            mine.update(additional)
        for fname in ('stdout', 'stderr', 'exit'):
            fname = '%sfile' % fname
            thing = getattr(self, fname)
            if self._notspecial(thing):
                mine[fname] = thing
        return super(Command, self).__str__(mine)

    def make_env(self):
        env = super(Command, self).make_env()
        ctx, opt = (self.parameters.context.strip(),
                    self.parameters.optional.strip())
        env['ADEPT_CONTEXT'] = ctx
        env['ADEPT_OPTIONAL'] = opt
        return env

    @staticmethod
    def strip_env(env):
        """Undo, make_env() sets ADEPT_* empty for substitution"""
        for key in ('ADEPT_CONTEXT', 'ADEPT_OPTIONAL'):
            if key in env:
                if env[key].strip() == '':
                    del env[key]
        return env

    @staticmethod
    def _notspecial(fileitem):
        # Not perfect, but gets the job done
        special = (0, False, True, '', '-', None,
                   subprocess.PIPE, subprocess.STDOUT)
        if fileitem and fileitem not in special:
            return True
        else:
            return False

    def _norm_open(self, new_env, fileitem):
        if self._notspecial(fileitem):
            fileitem = self.sub_env(new_env, fileitem)
            fileitem = os.path.abspath(
                os.path.normpath(os.path.realpath(fileitem)))
            # N/B Truncates file if exists
            return open(fileitem, "wb")
        else:
            return fileitem

    def init_stdfiles(self, new_env, **dargs):
        """
        Opens files for stdoutfile, stderrfile, & exitfile

        :param dict new_env: Possibly modified environment variables
        :param dict **dargs: Leftover/unparsed from init() call
        :raises ValueError: by yamlerr() on any additional darg keys
        """
        self.popen_dargs['cwd'] = self.parameters.workspace
        # Also used to translate meaning of '-' values
        defaults = {'stdout': None,
                    'stderr': subprocess.STDOUT,
                    'exit': None}
        # All but 'exit' have the same things done to them
        for name in ('stdout', 'stderr', 'exit'):
            namefile = '%sfile' % name
            # Only attempt env. var sub on filename strings
            setattr(self, namefile,
                    self._norm_open(new_env,
                                    dargs.pop(namefile, defaults[name])))
        for name in ('stdout', 'stderr'):
            namefile = '%sfile' % name
            thing = getattr(self, namefile)
            if isinstance(thing, file):
                self.popen_dargs[name] = thing
            elif thing == '-':
                self.popen_dargs[name] = defaults[name]

        # Any leftovers are unsupported
        extras = dargs.keys()
        if extras:
            self.yamlerr('parsing %s node' % self.__class__.__name__,
                         'received unknown/unsupported key(s): %s'
                         % str(extras))  # pop removed known keys

    def init(self, arguments=None, **dargs):
        """
        Initializes Command instance to be called

        :param str arguments: Additional items to pass when executing filepath
        :param dict dargs: May contain paths stdoutfile, stderrfile, & exitfile
        """
        # popen() functions take large number of keyword arguments
        self.popen_dargs['executable'] = self.filepath  # from base-class
        self.popen_dargs['cwd'] = self.parameters.workspace
        self.popen_dargs['env'] = new_env = self.make_env()
        self.popen_dargs['args'] = args = [self.filepath]  # from base-class
        self.arguments = arguments
        if self.arguments:
            self.arguments = self.sub_env(new_env, self.arguments)
            self.arguments = shlex.split(self.arguments, True)
            # This properly handles comments, nested quoting and escapes
            args.extend(self.arguments)
        # Playbook class does the same thing
        self.init_stdfiles(new_env, **dargs)
        # Empty strings needed for substitution purposes only
        self.strip_env(new_env)

    def swirly(self, child_proc):
        """
        If stdout/stderr of child are pipes or files, buffers need flushing
        """
        rod = poll()  # har har
        read_write_flush = {}
        # These are None if NOT a pipe - in that case, flushing is automatic
        for _file in [_ for _ in (child_proc.stderr, child_proc.stdout) if _]:
            rod.register(_file)
            if _file == child_proc.stderr:
                writer = sys.stderr.write
                flusher = sys.stderr.flush
            elif _file == child_proc.stdout:
                writer = sys.stdout.write
                flusher = sys.stdout.flush
            else:
                self.yamlerr('preparing command output files',
                             'encountered unknown file %s'
                             % _file)
            # This makes operating on the poll events easier
            read_write_flush[_file.fileno()] = (_file.read, writer, flusher)
        # Until the child process is done
        while child_proc.poll() is None:
            for _fd, event in rod.poll(100):  # miliseconds
                # Only care if reading won't block
                if event & (POLLIN | POLLPRI):
                    reader, writer, flusher = read_write_flush[_fd]
                    writer(reader(1))  # minimum required for event
                    flusher()
        return child_proc.returncode

    def action(self):
        """
        Execute filepath with arguments and handle any output/exit

        N/B: Uses subprocess.Popen()
        """
        cwd_default = self.popen_dargs.get('cwd', self.parameters.workspace)
        self.popen_dargs['cwd'] = cwd_default
        child_proc = subprocess.Popen(**self.popen_dargs)
        # No need to display them if they're headed to a file
        if child_proc.stderr or child_proc.stdout:
            sys.stderr.write('stdout/stderr =\n')
            self.swirly(child_proc)
        # Process won't exit unless output pipes are clear
        (out, err) = child_proc.communicate()
        returncode = child_proc.returncode
        if err and child_proc.stderr:  # must be a pipe if non-None
            sys.stderr.write(err)
            sys.stderr.flush()
        if out and child_proc.stdout:
            sys.stdout.write(out)
            sys.stderr.flush()
        # Assume caller is dealing with any/all exit codes
        if self.exitfile is not None:
            self.exitfile.write(str(returncode))
            sys.stderr.flush()
            return 0
        else:
            # Assume exits delt with here (exit with it!)
            return returncode


class Playbook(Command):

    """Handler class for playbook action-type yaml item"""

    # Full path to ansible-playbook command
    ansible_cmd = '/usr/bin/ansible-playbook'

    # defaults
    popen_dargs = {'bufsize': 1,   # line buffered for speed
                   'close_fds': False,
                   'shell': False,
                   'args': [ansible_cmd],
                   'executable': ansible_cmd,
                   'stdout': None,
                   'stderr': subprocess.STDOUT,
                   'universal_newlines': True}

    # Variables that only apply to this class
    limit = None
    varsfile = None
    inventory = None

    def __str__(self, additional=None):
        if additional:
            mine = additional
        else:
            mine = {}
        for name in ('varsfile', 'limit'):
            thing = getattr(self, name)
            if thing:
                mine[name] = thing
        return super(Playbook, self).__str__(mine)

    def make_env(self):
        env = super(Playbook, self).make_env()
        ctx, opt = (self.parameters.context.strip(),
                    self.parameters.optional.strip())
        # Always available in environment if non-empty
        if len(ctx):
            env['ADEPT_CONTEXT'] = ctx
        if len(opt):
            env['ADEPT_OPTIONAL'] = opt
        return env

    def init(self, varsfile=None, limit=None, inventory=None,
             config=None, **dargs):
        # The only difference with parent class
        if 'arguments' in dargs:
            self.yamlerr('initializing',
                         'encountered unsupported "arguments" key')

        self.popen_dargs['env'] = new_env = self.make_env()

        args = self.popen_dargs['args']

        if limit:
            limit = self.sub_env(new_env,
                                 limit.strip())
            self.limit = limit
            args.extend(['--limit', self.limit])

        for name, value in {'varsfile': varsfile, 'inventory': inventory,
                            'config': config,
                            'context': self.parameters.context}.items():
            if value:
                value = value.strip()
            if not value:
                continue
            value = self.sub_env(new_env, value)
            msg_fmt = 'You found a %s processing bug %%s:%%s' % name
            if name in ('varsfile', 'inventory'):
                spmv = self.parameters.mangle_verify
                value = spmv(self.parameters.context,
                             # other layers check existence
                             lambda x: True,
                             value, msg_fmt)
            if name is 'varsfile':
                args.extend(['--extra-vars', '@%s' % value])
            elif name is 'inventory':
                args.extend(['--inventory', value])
            elif name is 'context':
                args.extend(['--extra-vars', "adept_context='%s'" % value])
            else:  # name is 'config'
                new_env['ANSIBLE_CONFIG'] = value

        # Optionals get jammed onto the end of the command-line
        spos = self.parameters.optional.strip()
        if spos:
            # Respect shell-style quoting, linewraps, etc.
            args.extend(shlex.split(spos, True))

        # TODO: Don't hard-code private-key name/location?
        args.append('--private-key')
        args.append(self.sub_env(new_env, '$WORKSPACE/ssh_private_key'))
        # Last goes the playbook for debugging clarity
        args.append(self.filepath)
        # Handles all the common dargs keys
        super(Playbook, self).init_stdfiles(new_env, **dargs)
        self.strip_env(new_env)

# TODO: Add import class
# TODO: Add playbook-variable class

# Associate node name from yaml to class object for action_class()
ACTIONMAP = {'command': Command,
             'playbook': Playbook}


def action_class(index, node_name, parameters_source=None):

    """
    Returns a class appropriate for handling node_name, found at index.

    :param str node_name: The name of the yaml node to retrieve class for
    :param int index: Index where node_name appears in yaml (for debugging)
    :returns: A value from ACTIONMAP matching node_name
    :rtype: ActionBase subclass
    :raises ValueError: When no handler for node_name exists
    """

    try:
        return ACTIONMAP[node_name]
    except KeyError:
        if parameters_source is None:
            parameters_source = sys.argv
        # don't override outer-scope's name (at the very bottom)
        params = Parameters(parameters_source)
        raise ValueError("Error: While processing %s, "
                         "in context %s, encountered "
                         "unsupported action type %s "
                         "item #%d" % (params.yaml,
                                       params.context,
                                       node_name,
                                       index))


def action_items(yaml_document, parameters_source=None):
    """
    Process items from all documents in json_document through action_class()
    """
    errpfx = "Error: While processing %s, in context %s, index #%d, "
    errfmt = errpfx + "encountered unsupported 'contexts' value: '%s'"
    if parameters_source is None:
        parameters_source = sys.argv
    params = Parameters(parameters_source)
    index = 0
    for document in yaml_document:
        if document:
            for sequence in document:
                if sequence:
                    for node_name, dargs in sequence.iteritems():
                        # Implies first item == 1
                        index += 1
                        # Find parsing/syntax errors for all items
                        klass = action_class(index, node_name)
                        applies_to = dargs.pop('contexts', [])
                        if not isinstance(applies_to, (list, tuple)):
                            raise ValueError(errfmt % (params.yaml,
                                                       params.context,
                                                       index, applies_to))
                        # Empty list applies to everything
                        if applies_to and params.context not in applies_to:
                            continue
                        try:
                            yield klass(index, **dargs)
                        except TypeError:
                            fmt = errpfx + ("%s node is missing required "
                                            "values, see documentation")
                            raise ValueError(fmt % (params.yaml, params.context,
                                                    index, klass.__name__))


def main(parameters_source=None):
    """Process command-line parameters, perform actions based on yaml input"""
    try:
        parameters = Parameters(parameters_source)
    except RuntimeError, xcept:
        sys.stderr.write(prefix_divider(xcept.message))
        sys.exit(1)
    sys.stderr.write("%s\n" % parameters)

    yaml_document = None
    if parameters.yaml == '-':
        yaml_document = load_all(sys.stdin, Loader=Loader)
    else:
        yamlfile = open(parameters.yaml, 'rb')
        yaml_document = load_all(yamlfile, Loader=Loader)
    exit_code = 0
    for action_item in action_items(yaml_document, parameters_source):
        exit_code = action_item()  # executes it!
        if exit_code:
            sys.stderr.write("    exit = %d\n" % exit_code)
            break
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
