#!/usr/bin/env python3
# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2008-2010, Novell, Inc.
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

import base64
import cgi
import socket
import shutil

from libdissector import config
from libdissector import libinfoxml

# Upload with:
# # Upload the db
# curl --silent --show-error -F dbfile=@/path/to/obs.db http://server/path/obs-upload.py

UPLOAD_DIR = config.datadir
AUTHORIZED_IPS = config.upload_authorized_ips
AUTHORIZED_HOSTS = config.upload_authorized_hosts

def log_error (s):
    print('obs-upload: %s' % s, end=' ', file=sys.stderr)

def save_uploaded_file_internal (filename, fileitem, tmppath, destpath):
    fout = file (tmppath, 'wb')

    size = 0
    complete = False

    while 1:
        chunk = fileitem.file.read(100000)
        if not chunk:
            complete = True
            break
        size = size + len(chunk)
        # if bigger than 15MB, we give up. This way, it's not possible to fill
        # the disk
        # FWIW: file size was 2683904 on 2009-03-28
        # file size was 12480512 on 2009-07-25
        # file size was 10097664 on 2009-08-28
        # file size was 9393152 on 2009-08-31
        if size > 1024*1024*15:
            break
        fout.write (chunk)
    fout.close()

    if not complete:
        print('File upload cancelled: file is too big')
        log_error ('File upload cancelled: file is too big')
        return False

    if filename == 'obs.db':
        if size < 1024*1024*8:
            print('File upload cancelled: file is not as expected')
            log_error ('File upload cancelled: obs.db too small (%d)' % size)
            return False

    try:
        os.rename(tmppath, destpath)
        return True
    except:
        print('File upload cancelled: cannot rename file')
        log_error ('File upload cancelled: cannot rename file')
        return False

def save_uploaded_file (form, form_field, upload_dir, filename):
    if form_field not in form:
        return False

    fileitem = form[form_field]
    if not fileitem.file:
        return False

    # force the filename where we save, so we're not remote exploitable
    tmppath = os.path.join(upload_dir, filename + '.tmp')
    destpath = os.path.join(upload_dir, filename)

    try:
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        ret = save_uploaded_file_internal (filename, fileitem, tmppath, destpath)
    except Exception as e:
        print('Unknown error')
        log_error ('Unknown error: %s' % str(e))
        ret = False

    if os.path.exists(tmppath):
        os.unlink(tmppath)

    return ret

def create_cache(filename):
    if filename != 'obs.db':
        return

    try:
        info = libinfoxml.InfoXml()
    except Exception as e:
        print('Unknown error when accessing the database')
        log_error ('Unknown error when accessing the database: %s' % str(e))
        return

    if os.path.exists(info.cache_dir) and not os.access(info.cache_dir, os.W_OK):
        print('Cannot verify database: no access')
        log_error ('Cannot verify database: no access')
        return

    # We'll first write to a temporary directory since it's a long operation
    # and we don't want to make data unavailable
    cache_dir = info.cache_dir
    tmp_cache_dir = info.cache_dir + '.tmp'
    bak_cache_dir = info.cache_dir + '.bak'
    info.cache_dir = tmp_cache_dir

    # Remove this check: worst case, we'll have data about a project that
    # doesn't exist anymore or we'll overwrite a cache file that was just
    # created. In both cases, it's not a big deal -- especially since this
    # shouldn't stay long in time.
    ## This is racy (check for existence and then creation), but it should be
    ## okay in the end since there is only one client
    #if os.path.exists(info.cache_dir):
    #    print 'Cannot verify database: already verifying'
    #    return

    try:
        info.create_cache()

        # First move the old cache away before installing the new one (fast
        # operation), and then nuke the old cache
        if os.path.exists(bak_cache_dir):
            shutil.rmtree(bak_cache_dir)
        if os.path.exists(cache_dir):
            os.rename(cache_dir, bak_cache_dir)
        os.rename(tmp_cache_dir, cache_dir)
        if os.path.exists(bak_cache_dir):
            shutil.rmtree(bak_cache_dir)
    except Exception as e:
        print('Cannot verify database')
        log_error ('Cannot verify database: no access (%s)' % str(e))
        try:
            if os.path.exists(tmp_cache_dir):
                shutil.rmtree(tmp_cache_dir)
            if os.path.exists(bak_cache_dir):
                if not os.path.exists(cache_dir):
                    os.rename(bak_cache_dir, cache_dir)
                else:
                    shutil.rmtree(bak_cache_dir)
        except:
            pass

print('content-type: text/html\n')

form = cgi.FieldStorage()
if 'destfile' in form:
    dest = form.getfirst('destfile')
    if not dest in ['obs.db']:
        print('Unknown file')
        sys.exit(0)
else:
    # Just assume it's the standard database
    dest = 'obs.db'

authorized_ips = AUTHORIZED_IPS[:]
for host in AUTHORIZED_HOSTS:
    try:
        ip = socket.gethostbyname(host)
        authorized_ips.append(ip)
    except:
        pass

if os.environ['REMOTE_ADDR'] in authorized_ips:
    ret = save_uploaded_file (form, 'dbfile', UPLOAD_DIR, dest)
    if ret and dest in ['obs.db']:
        create_cache(dest)
else:
    print('Unauthorized access')
