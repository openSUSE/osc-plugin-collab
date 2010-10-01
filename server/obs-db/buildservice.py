# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2008-2009, Novell, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#  * Neither the name of the <ORGANIZATION> nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#
# (Licensed under the simplified BSD license)
#
# Authors: Vincent Untz <vuntz@opensuse.org>
#

import os
import sys

import bisect
import errno
import hashlib
import optparse
import shutil
import socket
import tempfile
import time
import urllib
import urllib2

import Queue
import threading

try:
    from lxml import etree as ET
except ImportError:
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

import osc_copy
import util

# Timeout for sockets
SOCKET_TIMEOUT = 30

# Debug output?
USE_DEBUG = False
DEBUG_DIR = 'debug'


#######################################################################


def debug_thread(context, state, indent = '', use_remaining = False):
    global USE_DEBUG
    global DEBUG_DIR

    if not USE_DEBUG:
        return

    # compatibility with old versions of python (< 2.6)
    if hasattr(threading.currentThread(), 'name'):
        name = threading.currentThread().name
    else:
        name = threading.currentThread().getName()

    if context == 'main':
        print '%s%s: %s' % (indent, name, state)
        return

    try:
        util.safe_mkdir_p(DEBUG_DIR)
        fout = open(os.path.join(DEBUG_DIR, 'buildservice-' + name), 'a')

        # ignore indent since we write in files
        fout.write('[%s] %s %s\n' % (context, time.strftime("%H:%M:%S", time.localtime()), state))

        if use_remaining:
            remaining = ''
            for i in threading.enumerate():
                remaining += i.name + ', '
            fout.write('Remaining: %s\n' % (remaining,))
        fout.close()
    except Exception, e:
        print >>sys.stderr, 'Exception in debug_thread: %s' % (e,)


def socket_closer_thread_run(obs_checkout, empty_event):
    # compatibility with old versions of python (< 2.6)
    if hasattr(empty_event, 'is_set'):
        empty_is_set = empty_event.is_set
    else:
        empty_is_set = empty_event.isSet

    while True:
        if empty_is_set():
            break

        obs_checkout.socket_timeouts_acquire()

        # Find the socket that is supposed to be closed the first, so we can
        # monitor it
        while True:
            if not len(obs_checkout.socket_timeouts):
                (max_time, current_socket) = (0, None)
                break

            (max_time, current_socket, url) = obs_checkout.socket_timeouts[0]

            if time.time() + SOCKET_TIMEOUT + 1 < max_time:
                debug_thread('monitor', 'closing socket for %s (too far)' % url)
                # close this socket: the max time is way too high
                current_socket.close()
                obs_checkout.socket_timeouts.remove((max_time, current_socket, url))
            else:
                break

        obs_checkout.socket_timeouts_release()

        # There's a socket to monitor, let's just do it
        if max_time > 0:

            while time.time() < max_time:
                time.sleep(1)
                # This is not thread-safe, but it can only go from False to
                # True.
                # If the value is still False, then we'll just try another
                # time (and worst case: we exit the loop because of the
                # timeout, but then we acquire the lock so the end will be
                # thread-safe: we won't close it twice).
                # If the value is True, then it's really closed anyway.
                if not current_socket.fp or current_socket.fp.closed:
                    break

            obs_checkout.socket_timeouts_acquire()
            if time.time() >= max_time:
                debug_thread('monitor', 'closing socket for %s (timed out)' % url)
                current_socket.close()
            if (max_time, current_socket, url) in obs_checkout.socket_timeouts:
                 obs_checkout.socket_timeouts.remove((max_time, current_socket, url))
            obs_checkout.socket_timeouts_release()

        else:
            # There's no socket to monitor at the moment, so we wait for one to
            # appear or for the notification of the end of the work.
            # We use less than the socket timeout value as timeout so we are
            # sure to not start too late the monitoring of the next socket (so
            # we don't allow a socket to stay more than its timeout).
            empty_event.wait(SOCKET_TIMEOUT / 2)


def obs_checkout_thread_run(obs_checkout):
    try:
        while True:
            debug_thread('thread_loop', 'start loop', use_remaining = True)
            if obs_checkout.queue.empty():
                break

            debug_thread('thread_loop', 'getting work...')
            # we don't want to block: the queue is filled at the beginning and
            # once it's empty, then it means we're done. So we want the
            # exception to happen.
            (project, package, meta) = obs_checkout.queue.get(block = False)
            debug_thread('main', 'starting %s/%s (meta: %d)' % (project, package, meta))

            try:
                debug_thread('thread_loop', 'work = %s/%s (meta: %d)' % (project, package, meta))
                if not package:
                    if meta:
                        obs_checkout.checkout_project_pkgmeta(project)
                    else:
                        obs_checkout.check_project(project)
                else:
                    if meta:
                        obs_checkout.checkout_package_meta(project, package)
                    else:
                        obs_checkout.checkout_package(project, package)
                debug_thread('thread_loop', 'work done')
            except Exception, e:
                print >>sys.stderr, 'Exception in worker thread for %s/%s (meta: %d): %s' % (project, package, meta, e)

            obs_checkout.queue.task_done()
            debug_thread('thread_loop', 'end loop', use_remaining = True)
    except Queue.Empty:
        pass
    debug_thread('thread_loop', 'exit loop', use_remaining = True)


#######################################################################


class ObsCheckout:

    def __init__(self, conf, dest_dir):
        global USE_DEBUG
        global DEBUG_DIR
        global SOCKET_TIMEOUT

        USE_DEBUG = conf.debug
        DEBUG_DIR = os.path.join(conf.cache_dir, 'debug')
        SOCKET_TIMEOUT = conf.threads_sockettimeout

        self.conf = conf
        self.dest_dir = dest_dir

        self.queue = Queue.Queue()
        self.queue2 = Queue.Queue()
        self.socket_timeouts = []
        self.socket_timeouts_lock = None


    def socket_timeouts_acquire(self):
        if self.socket_timeouts_lock:
            debug_thread('lock', 'acquiring lock')
            self.socket_timeouts_lock.acquire()
            debug_thread('lock', 'acquired lock')


    def socket_timeouts_release(self):
        if self.socket_timeouts_lock:
            self.socket_timeouts_lock.release()
            debug_thread('lock', 'released lock')


    def _download_url_to_file(self, url, file):
        """ Download url to file.

            Return the length of the downloaded file.

        """
        fin = None
        fout = None
        timeout = 0
        length = 0
        try:
            debug_thread('url', 'start %s (timeout = %d)' % (url, socket.getdefaulttimeout() or 0), ' ')
            fin = urllib2.urlopen(url)
            debug_thread('url', 'opened', ' ')

            self.socket_timeouts_acquire()
            timeout = time.time() + SOCKET_TIMEOUT
            bisect.insort(self.socket_timeouts, (timeout, fin, url))
            self.socket_timeouts_release()

            fout = open(file, 'w')

            while True:
                # This generally happens because of the monitor thread
                if not fin.fp:
                    raise socket.error('Timeout')

                bytes = fin.read(500 * 1024)
                cur_length = len(bytes)
                if cur_length == 0:
                    break
                fout.write(bytes)
                length += cur_length
            fout.close()

            self.socket_timeouts_acquire()
            if (timeout, fin, url) in self.socket_timeouts:
                self.socket_timeouts.remove((timeout, fin, url))
            fin.close()
            self.socket_timeouts_release()

            debug_thread('url', 'done', ' ')

            return length

        except Exception, e:
            debug_thread('url', 'exception: %s' % (e,), ' ')

            self.socket_timeouts_acquire()
            if (timeout, fin, url) in self.socket_timeouts:
                self.socket_timeouts.remove((timeout, fin, url))
            if fin:
                fin.close()
            self.socket_timeouts_release()

            if fout:
                fout.close()
            raise e


    def _get_file(self, project, package, filename, size, revision = None, try_again = True):
        """ Download a file of a package. """
        package_dir = os.path.join(self.dest_dir, project, package)
        destfile = os.path.join(package_dir, filename)
        tmpdestfile = destfile + '.new'

        try:
            query = None
            if revision:
                query = { 'rev': revision }
            url = osc_copy.makeurl(self.conf.apiurl, ['public', 'source', project, package, urllib.pathname2url(filename)], query=query)
            length = self._download_url_to_file(url, tmpdestfile)

            if length != size:
                if try_again:
                    util.safe_unlink(tmpdestfile)
                    return self._get_file(project, package, filename, size, revision, False)

            os.rename(tmpdestfile, destfile)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(tmpdestfile)

            if type(e) == urllib2.HTTPError and e.code == 404:
                print >>sys.stderr, 'File in package %s of project %s doesn\'t exist.' % (filename, package, project)
            elif try_again:
                self._get_file(project, package, filename, size, revision, False)
            else:
                print >>sys.stderr, 'Cannot get file %s for %s from %s: %s' % (filename, package, project, e)

            return


    def _get_files_metadata(self, project, package, save_basename, revision = None, try_again = True):
        """ Download the file list of a package. """
        package_dir = os.path.join(self.dest_dir, project, package)
        filename = os.path.join(package_dir, save_basename)
        tmpfilename = filename + '.new'

        # download files metadata
        try:
            query = None
            if revision:
                query = { 'rev': revision }
            url = osc_copy.makeurl(self.conf.apiurl, ['public', 'source', project, package], query=query)
            length = self._download_url_to_file(url, tmpfilename)

            if length == 0:
                # metadata files should never be empty
                if try_again:
                    util.safe_unlink(tmpfilename)
                    return self._get_files_metadata(project, package, save_basename, revision, False)

            os.rename(tmpfilename, filename)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(tmpfilename)

            if type(e) == urllib2.HTTPError and e.code == 404:
                print >>sys.stderr, 'Package %s doesn\'t exist in %s.' % (package, project)
            elif try_again:
                return self._get_files_metadata(project, package, save_basename, revision, False)
            elif revision:
                print >>sys.stderr, 'Cannot download file list of %s from %s with specified revision: %s' % (package, project, e)
            else:
                print >>sys.stderr, 'Cannot download file list of %s from %s: %s' % (package, project, e)

            return None

        try:
            return ET.parse(filename).getroot()
        except SyntaxError, e:
            if try_again:
                os.unlink(filename)
                return self._get_files_metadata(project, package, save_basename, revision, False)
            elif revision:
                print >>sys.stderr, 'Cannot parse file list of %s from %s with specified revision: %s' % (package, project, e)
            else:
                print >>sys.stderr, 'Cannot parse file list of %s from %s: %s' % (package, project, e)
            return None


    def _get_package_metadata_cache(self, project, package):
        """ Get the (md5, mtime) metadata from currently checkout data.

            We take the metadata from the expanded link first, and also loads
            the metadata from the non-expanded link (which overloads the
            previous one).

        """
        def add_metadata_from_file(file, cache):
            if not os.path.exists(file):
                return

            try:
                root = ET.parse(file).getroot()
            except SyntaxError:
                return

            # also get the md5 of the directory
            cache[os.path.basename(file)] = (root.get('srcmd5'), '')

            for node in root.findall('entry'):
                cache[node.get('name')] = (node.get('md5'), node.get('mtime'))

        package_dir = os.path.join(self.dest_dir, project, package)
        cache = {}

        files = os.path.join(package_dir, '_files-expanded')
        add_metadata_from_file(files, cache)
        files = os.path.join(package_dir, '_files')
        add_metadata_from_file(files, cache)

        return cache


    def _get_hash_from_file(self, algo, path):
        """ Return the hash of a file, using the specified algorithm. """
        if not os.path.exists(path):
            return None

        if algo not in [ 'md5' ]:
            print >>sys.stderr, 'Internal error: _get_hash_from_file called with unknown hash algorithm: %s' % algo
            return None

        hash = hashlib.new(algo)
        file = open(path, 'rb')
        while True:
            data = file.read(32768)
            if not data:
                break
            hash.update(data)
        file.close()
        return hash.hexdigest()


    def _get_package_file_checked_out(self, project, package, filename, cache, md5, mtime):
        """ Tells if a file of the package is already checked out. """
        if not cache.has_key(filename):
            return False
        if cache[filename] != (md5, mtime):
            return False

        path = os.path.join(self.dest_dir, project, package, filename)
        file_md5 = self._get_hash_from_file('md5', path)
        return file_md5 != None and file_md5 == md5


    def _cleanup_package_old_files(self, project, package, downloaded_files):
        """ Function to remove old files that should not be in a package
            checkout anymore.

            This should be called before all return statements in
            checkout_package. 

        """
        package_dir = os.path.join(self.dest_dir, project, package)
        for file in os.listdir(package_dir):
            if file in downloaded_files:
                continue
            os.unlink(os.path.join(package_dir, file))


    def checkout_package(self, project, package):
        """ Checks out a package.

            We use the files already checked out as a cache, to avoid
            downloading the same files again if possible.

            This means we need to make sure to remove all files that shouldn't
            be there when leaving this function. This is done with the calls to
            _cleanup_package_old_files().

        """
        if not package:
            print >>sys.stderr, 'Internal error: checkout_package called instead of checkout_project_pkgmeta'
            self.checkout_project_pkgmeta(project)
            return

        package_dir = os.path.join(self.dest_dir, project, package)
        util.safe_mkdir_p(package_dir)

        # Never remove _meta files, since they're not handled by the checkout process
        downloaded_files = [ '_meta' ]

        metadata_cache = self._get_package_metadata_cache(project, package)

        # find files we're interested in from the metadata
        root = self._get_files_metadata(project, package, '_files')
        downloaded_files.append('_files')
        if root is None:
            self._cleanup_package_old_files(project, package, downloaded_files)
            return

        is_link = False
        link_error = False
        # revision to expand a link
        link_md5 = None

        # detect if the package is a link package
        linkinfos_nb = len(root.findall('linkinfo'))
        if linkinfos_nb == 1:
            link_node = root.find('linkinfo')
            # The logic is taken from islink() in osc/core.py
            is_link = link_node.get('xsrcmd5') not in [ None, '' ] or link_node.get('lsrcmd5') not in [ None, '' ]
            link_error = link_node.get('error') not in [ None, '' ]
            link_md5 = link_node.get('xsrcmd5')
        elif linkinfos_nb > 1:
            print >>sys.stderr, 'Ignoring link in %s from %s: more than one <linkinfo>' % (package, project)

        if is_link:
            # download the _link file first. This makes it possible to know if
            # the project has a delta compared to the target of the link
            for node in root.findall('entry'):
                filename = node.get('name')
                md5 = node.get('md5')
                mtime = node.get('mtime')
                size = node.get('size')
                if filename == '_link':
                    if not self._get_package_file_checked_out(project, package, filename, metadata_cache, md5, mtime):
                        self._get_file(project, package, filename, size)
                    downloaded_files.append(filename)

            # if the link has an error, then we can't do anything else since we
            # won't be able to expand
            if link_error:
                self._cleanup_package_old_files(project, package, downloaded_files)
                return

            # look if we need to download the metadata of the expanded package
            if metadata_cache.has_key('_files-expanded') and metadata_cache['_files-expanded'][0] == link_md5:
                files = os.path.join(self.dest_dir, project, package, '_files-expanded')
                try:
                    root = ET.parse(files).getroot()
                except SyntaxError:
                    root = None
            else:
                root = self._get_files_metadata(project, package, '_files-expanded', link_md5)

            if root is None:
                self._cleanup_package_old_files(project, package, downloaded_files)
                return

            downloaded_files.append('_files-expanded')

        # look at all files and download what might be interesting
        for node in root.findall('entry'):
            filename = node.get('name')
            md5 = node.get('md5')
            mtime = node.get('mtime')
            size = node.get('size')
            # download .spec files
            if filename.endswith('.spec'):
                if not self._get_package_file_checked_out(project, package, filename, metadata_cache, md5, mtime):
                    self._get_file(project, package, filename, size, link_md5)
                downloaded_files.append(filename)

        self._cleanup_package_old_files(project, package, downloaded_files)


    def checkout_package_meta(self, project, package, try_again = True):
        """ Checks out the metadata of a package.
        
            If we're interested in devel projects of this project, and the
            devel package is not in a checked out devel project, then we queue
            a checkout of this devel project.

        """
        package_dir = os.path.join(self.dest_dir, project, package)
        util.safe_mkdir_p(package_dir)

        filename = os.path.join(package_dir, '_meta')
        tmpfilename = filename + '.new'

        try:
            url = osc_copy.makeurl(self.conf.apiurl, ['public', 'source', project, package, '_meta'])
            length = self._download_url_to_file(url, tmpfilename)

            if length == 0:
                # metadata files should never be empty
                if try_again:
                    util.safe_unlink(tmpfilename)
                    return self.checkout_package_meta(project, package, False)

            os.rename(tmpfilename, filename)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(tmpfilename)

            if type(e) == urllib2.HTTPError and e.code == 404:
                print >>sys.stderr, 'Package %s of project %s doesn\'t exist.' % (package, project)
            elif try_again:
                self.checkout_package_meta(project, package, False)
            else:
                print >>sys.stderr, 'Cannot get metadata of package %s in %s: %s' % (package, project, e)

            return

        # Are we interested in devel projects of this project, and if yes,
        # should we check out the devel project if needed?
        if not self.conf.projects.has_key(project):
            return
        if not self.conf.projects[project].checkout_devel_projects:
            return

        try:
            package_node = ET.parse(filename).getroot()
        except SyntaxError:
            return
 
        devel_node = package_node.find('devel')
        if devel_node is None:
            return

        devel_project = devel_node.get('project')
        project_dir = os.path.join(self.dest_dir, devel_project)
        if not os.path.exists(project_dir):
            self.queue_checkout_project(devel_project, parent = project, primary = False)


    def check_project(self, project, try_again = True):
        """ Checks if the current checkout of a project is up-to-date, and queue task if necessary. """
        project_dir = os.path.join(self.dest_dir, project)
        util.safe_mkdir_p(project_dir)

        filename = os.path.join(project_dir, '_status')

        try:
            url = osc_copy.makeurl(self.conf.apiurl, ['status', 'project', project])
            length = self._download_url_to_file(url, filename)

            if length == 0:
                # metadata files should never be empty
                if try_again:
                    util.safe_unlink(filename)
                    return self.check_project(project, False)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(filename)

            if type(e) == urllib2.HTTPError:
                if e.code == 404:
                    print >>sys.stderr, 'Project %s doesn\'t exist.' % (project,)
                elif e.code == 400:
                    # the status page doesn't always work :/
                    self.queue_checkout_project(project, primary = False, force_simple_checkout = True, no_config = True)
            elif try_again:
                self.check_project(project, False)
            else:
                print >>sys.stderr, 'Cannot get status of %s: %s' % (project, e)

            return

        try:
            packages_node = ET.parse(filename).getroot()
        except SyntaxError, e:
            util.safe_unlink(filename)

            if try_again:
                return self.check_project(project, False)
            else:
                print >>sys.stderr, 'Cannot parse status of %s: %s' % (project, e)

            return

        # We will have to remove all subdirectories that just don't belong to
        # this project anymore.
        subdirs_to_remove = [ file for file in os.listdir(project_dir) if os.path.isdir(os.path.join(project_dir, file)) ]

        # Here's what we check to know if a package needs to be checked out again:
        #  - if there's no subdir
        #  - if it's a link:
        #    - check that the md5 from the status is the xsrcmd5 from the file
        #      list
        #    - check that we have _files-expanded and that all spec files are
        #      checked out
        #  - if it's not a link: check that the md5 from the status is the
        #    srcmd5 from the file list
        for node in packages_node.findall('package'):
            name = node.get('name')
            srcmd5 = node.get('srcmd5')
            is_link = len(node.findall('link')) > 0

            try:
                subdirs_to_remove.remove(name)
            except ValueError:
                pass

            files = os.path.join(project_dir, name, '_files')
            if not os.path.exists(files):
                self.queue_checkout_package(project, name, primary = False)
                continue

            try:
                files_root = ET.parse(files).getroot()
            except SyntaxError:
                self.queue_checkout_package(project, name, primary = False)
                continue

            if is_link:
                previous_srcmd5 = files_root.get('xsrcmd5')
            else:
                previous_srcmd5 = files_root.get('srcmd5')

            if srcmd5 != previous_srcmd5:
                self.queue_checkout_package(project, name, primary = False)

            # make sure we have all spec files

            if is_link:
                # for links, we open the list of files when expanded
                files = os.path.join(project_dir, name, '_files-expanded')
                if not os.path.exists(files):
                    self.queue_checkout_package(project, name, primary = False)
                    continue

                try:
                    files_root = ET.parse(files).getroot()
                except SyntaxError:
                    self.queue_checkout_package(project, name, primary = False)
                    continue

            cont = False
            for entry in files_root.findall('entry'):
                filename = entry.get('name')
                if filename.endswith('.spec'):
                    specfile = os.path.join(project_dir, name, filename)
                    if not os.path.exists(specfile):
                        self.queue_checkout_package(project, name, primary = False)
                        cont = True
                        break
            if cont:
                continue

        # Remove useless subdirectories
        for subdir in subdirs_to_remove:
            shutil.rmtree(os.path.join(project_dir, subdir))

        util.safe_unlink(filename)


    def checkout_project_pkgmeta(self, project, try_again = True):
        """ Checks out the packages metadata of all packages in a project. """
        project_dir = os.path.join(self.dest_dir, project)
        util.safe_mkdir_p(project_dir)

        filename = os.path.join(project_dir, '_pkgmeta')
        tmpfilename = filename + '.new'

        try:
            url = osc_copy.makeurl(self.conf.apiurl, ['search', 'package'], ['match=%s' % urllib.quote('@project=\'%s\'' % project)])
            length = self._download_url_to_file(url, tmpfilename)

            if length == 0:
                # metadata files should never be empty
                if try_again:
                    util.safe_unlink(tmpfilename)
                    return self.checkout_project_pkgmeta(project, False)

            os.rename(tmpfilename, filename)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(tmpfilename)

            if type(e) == urllib2.HTTPError and e.code == 404:
                print >>sys.stderr, 'Project %s doesn\'t exist.' % (project,)
            elif try_again:
                self.checkout_project_pkgmeta(project, False)
            else:
                print >>sys.stderr, 'Cannot get packages metadata of %s: %s' % (project, e)

            return


    def run(self):
        if self.socket_timeouts != []:
            print >>sys.stderr, 'Internal error: list of socket timeouts is not empty before running'
            return
        # queue is empty or does not exist: it could be that the requested
        # project does not exist
        if self.queue.empty():
            return

        debug_thread('main', 'queue has %d items' % self.queue.qsize())

        if self.conf.threads > 1:
            # Architecture with threads:
            #  + we fill a queue with all the tasks that have to be done
            #  + the main thread does nothing until the queue is empty
            #  + we create a bunch of threads that will take the tasks from the
            #    queue
            #  + we create a monitor thread that ensures that the socket
            #    connections from the other threads don't hang forever. The
            #    issue is that those threads use urllib2, and urllib2 will
            #    remove the timeout from the underlying socket. (see
            #    socket.makefile() documentation)
            #  + there's an event between the main thread and the monitor
            #    thread to announce to the monitor thread that the queue is
            #    empty and that it can leave.
            #  + once the queue is empty:
            #    - the helper threads all exit since there's nothing left to do
            #    - the main thread is waken up and sends an event to the
            #      monitor thread. It waits for it to exit.
            #    - the monitor thread receives the event and exits.
            #    - the main thread can continue towards the end of the process.

            # this is used to signal the monitor thread it can exit
            empty_event = threading.Event()
            # this is the lock for the data shared between the threads
            self.socket_timeouts_lock = threading.Lock()

            if SOCKET_TIMEOUT > 0:
                monitor = threading.Thread(target=socket_closer_thread_run, args=(self, empty_event))
                monitor.start()

            thread_args = (self,)
            for i in range(min(self.conf.threads, self.queue.qsize())):
                t = threading.Thread(target=obs_checkout_thread_run, args=thread_args)
                t.start()

            self.queue.join()
            # tell the monitor thread to quit and wait for it
            empty_event.set()
            if SOCKET_TIMEOUT > 0:
                monitor.join()
        else:
            try:
                while not self.queue.empty():
                    (project, package, meta) = self.queue.get(block = False)
                    debug_thread('main', 'starting %s/%s' % (project, package))
                    if not package:
                        if meta:
                            obs_checkout.checkout_project_pkgmeta(project)
                        else:
                            obs_checkout.check_project(project)
                    else:
                        if meta:
                            obs_checkout.checkout_package_meta(project, package)
                        else:
                            obs_checkout.checkout_package(project, package)
            except Queue.Empty:
                pass

        # secondary queue is not empty, so we do a second run
        if not self.queue2.empty():
            debug_thread('main', 'Working on second queue')
            self.queue = self.queue2
            self.queue2 = Queue.Queue()
            self.run()


    def _write_project_config(self, project):
        """ We need to write the project config to a file, because nothing
            remembers if a project is a devel project, and from which project
            it is, so it's impossible to know what settings should apply
            without such a file. """
        if not self.conf.projects.has_key(project):
            return

        project_dir = os.path.join(self.dest_dir, project)
        util.safe_mkdir_p(project_dir)

        filename = os.path.join(project_dir, '_obs-db-options')

        fout = open(filename, 'w')
        fout.write('parent=%s\n' % self.conf.projects[project].parent)
        fout.write('branch=%s\n' % self.conf.projects[project].branch)
        fout.write('ignore-fallback=%d\n' % self.conf.projects[project].ignore_fallback)
        fout.write('force-project-parent=%d\n' % self.conf.projects[project].force_project_parent)
        fout.write('lenient-delta=%d\n' % self.conf.projects[project].lenient_delta)
        fout.close()


    def _copy_project_config(self, project, copy_from):
        from_file = os.path.join(self, self.dest_dir, copy_from, '_obs-db-options')
        if not os.path.exists(from_file):
            return

        project_dir = os.path.join(self.dest_dir, project)
        util.safe_mkdir_p(project_dir)

        filename = os.path.join(project_dir, '_obs-db-options')
        shutil.copy(from_file, filename)


    def _get_packages_in_project(self, project, try_again = True):
        project_dir = os.path.join(self.dest_dir, project)
        util.safe_mkdir_p(project_dir)

        filename = os.path.join(project_dir, '_pkglist')

        try:
            url = osc_copy.makeurl(self.conf.apiurl, ['source', project])
            length = self._download_url_to_file(url, filename)

            if length == 0:
                # metadata files should never be empty
                if try_again:
                    util.safe_unlink(filename)
                    return self._get_packages_in_project(project, False)

        except (urllib2.HTTPError, urllib2.URLError, socket.error), e:
            util.safe_unlink(filename)

            if type(e) == urllib2.HTTPError and e.code == 404:
                return (None, 'Project %s doesn\'t exist.' % (project,))
            elif try_again:
                return self._get_packages_in_project(project, False)
            else:
                return (None, str(e))

        try:
            root = ET.parse(filename).getroot()
        except SyntaxError, e:
            util.safe_unlink(filename)

            if try_again:
                return self._get_packages_in_project(project, False)
            else:
                return (None, 'Cannot parse list of packages in %s: %s' % (project, e))

        packages = [ node.get('name') for node in root.findall('entry') ]
        util.safe_unlink(filename)

        return (packages, None)


    def queue_pkgmeta_project(self, project, primary = True):
        if primary:
            q = self.queue
        else:
            q = self.queue2

        q.put((project, '', True))


    def queue_check_project(self, project, primary = True):
        if primary:
            q = self.queue
        else:
            q = self.queue2

        q.put((project, '', False))


    def queue_checkout_package_meta(self, project, package, primary = True):
        if primary:
            q = self.queue
        else:
            q = self.queue2

        q.put((project, package, True))


    def queue_checkout_package(self, project, package, primary = True):
        if primary:
            q = self.queue
        else:
            q = self.queue2

        q.put((project, package, False))


    def queue_checkout_packages(self, project, packages, primary = True):
        if primary:
            q = self.queue
        else:
            q = self.queue2

        for package in packages:
            q.put((project, package, False))


    def queue_checkout_project(self, project, parent = None, primary = True, force_simple_checkout = False, no_config = False):
        """ Queue a checkout of a project.

            If there's already a checkout for this project, instead of a full
            checkout, a check of what is locally on disk and what should be
            there will be done to only update what is necessary.

            force_simple_checkout is used when what is needed is really just a
            checkout of this project, and nothing else (no metadata for all
            packages, and no devel projects).

        """
        project_dir = os.path.join(self.dest_dir, project)

        if not no_config:
            if parent:
                self._copy_project_config(project, parent)
            else:
                self._write_project_config(project)

        if os.path.exists(project_dir) and not force_simple_checkout:
            debug_thread('main', 'Queuing check for %s' % (project,))
            self.queue_check_project(project, primary)
        else:
            debug_thread('main', 'Queuing packages of %s' % (project,))
            (packages, error) = self._get_packages_in_project(project)

            if error is not None:
                print >>sys.stderr, 'Ignoring project %s: %s' % (project, error)
                return

            self.queue_checkout_packages(project, packages, primary)

        if not force_simple_checkout:
            if (not self.conf.projects.has_key(project) or
                not self.conf.projects[project].checkout_devel_projects):
                # the pkgmeta of the project is automatically downloaded when
                # looking for devel projects
                self.queue_pkgmeta_project(project, primary)
            else:
                self._queue_checkout_devel_projects(project, primary)


    def _queue_checkout_devel_projects(self, project, primary = True):
        self.checkout_project_pkgmeta(project)
        pkgmeta_file = os.path.join(self.dest_dir, project, '_pkgmeta')
        if not os.path.exists(pkgmeta_file):
            print >>sys.stderr, 'Ignoring devel projects for project %s: no packages metadata' % (project,)
            return

        devel_projects = set()

        try:
            collection = ET.parse(pkgmeta_file).getroot()
            package = collection.find('package')
            if package == None:
                print >>sys.stderr, 'Project %s doesn\'t exist.' % (project,)
                return

            for package in collection.findall('package'):
                devel = package.find('devel')
                # "not devel" won't work (probably checks if devel.text is
                # empty)
                if devel == None:
                    continue
                devel_project = devel.get('project')
                if devel_project and devel_project != project:
                    devel_projects.add(devel_project)

        except SyntaxError, e:
            print >>sys.stderr, 'Ignoring devel projects for project %s: %s' % (project, e)
            return

        for devel_project in devel_projects:
            self.queue_checkout_project(devel_project, parent = project, primary = primary)


    def remove_checkout_package(self, project, package):
        """ Remove the checkout of a package. """
        path = os.path.join(self.dest_dir, project, package)
        if os.path.exists(path):
            shutil.rmtree(path)

    def remove_checkout_project(self, project):
        """ Remove the checkout of a project. """
        path = os.path.join(self.dest_dir, project)
        if os.path.exists(path):
            shutil.rmtree(path)
