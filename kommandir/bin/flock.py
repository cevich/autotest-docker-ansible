#!/usr/bin/env python

"""
Module of locking-related classes and functions not available in the standard library
"""

import sys
import os
import os.path
import logging
import random
from time import time, sleep
from fcntl import flock, LOCK_UN, LOCK_SH, LOCK_EX, LOCK_NB
from errno import EACCES, EAGAIN
from contextlib import contextmanager


random.seed(os.urandom(64))


class Flock(object):
    """
    A reader/writer lock object, with locking tightly bound to instance scope.

    :Note: This implementation gives reader-lock requests priority over writers.
    :Ref: https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock#Priority_policies

    :param name: Optional path/filename of lock file.  Safely generated if None.
    """

    # Internal, do not use
    _lockfile = None

    #: Function to call for locking, must present same API as fcntl.lockf()
    lock_f = flock

    #: Function to call for unlocking, must present same API as fcntl.lockf()
    unlock_f = flock

    #: This is set True whenever this process holdes a read lock, None otherwise
    is_read = None

    #: When no lock file name is specified, use this directory
    def_path = '/tmp'

    #: When no lock file name is specified, use this prefix
    def_prefix = os.path.basename(sys.argv[0]) + '_'

    #: When no lock file name is specified, use this suffix
    def_suffix = '.lock'

    def __init__(self, lockfilepath=None):
        if lockfilepath is None:
            lockfilepath = os.path.join(self.def_path, self.def_prefix + self.def_suffix)
        self._lockfile = open(lockfilepath, 'a+b', 0)  # No truncate existing
        logging.debug("Prepared lock file %s", self._lockfile.name)
        self._lockfile.close()  # when open, is_locked() == True

    def __del__(self):
        self.unlock()  # N/B: Exceptions are ignored!

    def __str__(self):
        if self.is_locked:
            return "Locked (%s)" % self._lockfile.name
        return "Unlocked (%s)" % self._lockfile.name

    def __repr__(self):
        return 'Flock(%s)' % self._lockfile.name

    def lock(self, op):
        """
        Execute locking operation.

        :param op: Bitwise OR of LOCK_SH, LOCK_EX, LOCK_NB
        :returns: File-like object representing data under lock
        """
        # Allow double-locking by _this_ process only
        if self._lockfile.closed:
            # File must remain open for process to continue holding lock
            self._lockfile = open(self._lockfile.name, 'wb', 0)
        self.lock_f(self._lockfile, op)
        self.is_read = bool(op & LOCK_SH)
        return self._lockfile

    def lock_timeout(self, timeout, op):
        """
        Execute locking operation, return True when successful.

        :param timeout: Integer or float, timeout in seconds to wait for operation.
        :param op: Bitwise OR of fcntl.LOCK_UN, LOCK_SH, LOCK_EX, LOCK_NB.
        :returns: File-like object if lock was acquired, None if not.
        """
        timeout = float(timeout)
        logging.debug("(Timeing after %0.4f seconds)", timeout)
        timedout = time() + timeout
        while time() < timedout:
            try:
                lockfile = self.lock(op | LOCK_NB)
                timedout = 0
                break
            except IOError, xcept:
                if xcept.errno not in [EACCES, EAGAIN]:
                    raise
            # Don't busy wait for fixed times (avoids clashes)
            sleep(0.01 + (random.randrange(0, 100) / 100))
        if bool(timedout):
            logging.debug("(Timed out)")
            return None
        return lockfile

    def unlock(self):
        """
        Execure unlocking operation, may call more than once.

        :returns: True if lock was held (and released) from current scope
        """
        if self._lockfile.closed:
            return  False  # Lock was not held by this process
        self.unlock_f(self._lockfile, LOCK_UN)
        self._lockfile.close()
        self.is_read = None
        return True  # Lock was held by this process, and released

    @property
    def is_locked(self):
        """
        Return True/False if any lock is currently held by this or another process.
        """
        if self.is_read is None:  # maintained by lock()/unlock()
            return True  # Lock is held by this process
        # If non-blocking lock can be acquired, lock is not held by any process
        locked = False
        try:
            logging.debug("Test-acquiring to check locked state...")
            self.lock(LOCK_EX | LOCK_NB)
            locked = False
        except IOError, xcept:
            if xcept.errno not in [EACCES, EAGAIN]:
                raise
            locked = True
        finally:  # Always, immediatly unlock
            self.unlock()
            logging.debug("...test-acquire complete.")
        return locked

    @contextmanager
    def _acquire(self, op, name):
        # __enter__
        start = time()
        lockfile = self.lock(op)
        logging.debug("    %d acquired %s lock in %0.4fs",
                      os.getpid(), name, time() - start)
        try:
            yield open(lockfile.name, 'rb')
        finally:
            # __exit__
            self.unlock()
            lockfile.close()
            logging.debug("    %d %s lock released, held for %0.4fs",
                          os.getpid(), name, time() - start)

    def acquire_read(self):
        """
        Context manager wrapping a read-lock.

        :returns: Read-only file-like binary-mode object
        """
        return self._acquire(LOCK_SH, "read")

    def acquire_write(self):
        """
        Context manager wrapping a write-lock

        :returns: Read/Write file-like binary-mode object
        """
        return self._acquire(LOCK_EX, "write")

    @contextmanager
    def _timeout_acquire(self, timeout, op, name):
        # __enter__
        start = time()
        lockfile = self.lock_timeout(timeout, op)
        logging.debug("    %d acquired %s lock before timeout, waited %0.4fs",
                      os.getpid(), name, time() - start)
        if lockfile:
            yield open(lockfile.name, 'rb')
        else:
            logging.error("    %d timedout acquiring %s lock after %0.4fs",
                          os.getpid(), name, time() - start)
            yield None
        # __exit__
        if lockfile:
            self.unlock()
            lockfile.close()
            logging.debug("    %d %s lock released, held for %0.4fs",
                          os.getpid(), name, time() - start)

    def timeout_acquire_read(self, timeout):
        """
        Context manager wrapping a read-lock, within a timeout period.

        :returns: Read-only file-like object if successful, None if not.
        """
        return self._timeout_acquire(timeout, LOCK_SH, "read")

    def timeout_acquire_write(self, timeout):
        """
        Context manager wrapping a write-lock, within a timeout period.

        :returns: Read/Write file-like object if successful, None if not.
        """
        return self._timeout_acquire(timeout, LOCK_EX, "write")


def _umpa_lumpa(n):
    # Don't all try to do locking all at once
    sleep(1 + float(random.randrange(0, 100) / 100))
    _flock = Flock('/tmp/doopitydoo.lock')
    method = random.choice([_flock.acquire_read, _flock.acquire_write])
    with method():
        logging.debug("    %d(%d) is doing some important work", n, os.getpid())
        sleep(1 + float(random.randrange(0, 100) / 100))


def _make_candy():
    import multiprocessing
    procs = [multiprocessing.Process(target=_umpa_lumpa, args=(n,))
             for n in xrange(20)]
    random.shuffle(procs)
    for proc in procs:
        proc.start()
    random.shuffle(procs)
    for proc in procs:
        proc.join()
    logging.debug("MOARRRSUGARRRRR!")


if __name__ == '__main__':
    try:
        LOGGER = logging.getLogger()
        # Lower to DEBUG for massively detailed output
        LOGGER.setLevel(logging.DEBUG)
        logging.debug("Charlie?")
        _make_candy()
    finally:
        os.unlink('/tmp/doopitydoo.lock')
