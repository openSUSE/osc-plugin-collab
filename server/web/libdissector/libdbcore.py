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

import sqlite3
import time

from stat import *

import config


#######################################################################


_db_file = os.path.join(config.datadir, 'obs.db')

table_file = 'file'
table_source = 'source'
table_patch = 'patch'
table_rpmlint = 'rpmlint'
table_package = 'package'
table_srcpackage = 'srcpackage'
table_project = 'project'


#######################################################################


pkg_query = 'SELECT %s.* FROM %s, %s WHERE %s.name = ? AND %s.name = ? AND %s.project = %s.id;' % (table_srcpackage, table_project, table_srcpackage, table_project, table_srcpackage, table_srcpackage, table_project)


#######################################################################


def get_db_mtime(raw = False):
    mtime = time.gmtime(os.stat(_db_file)[ST_MTIME])

    if raw:
        return mtime
    else:
        return time.strftime('%d/%m/%Y (%H:%M UTC)', mtime)


#######################################################################


class ObsDbException(Exception):

    def __init__(self, value):
        self.msg = value

    def __str__(self):
        return self.msg


#######################################################################


class ObsDb:

    def __init__(self):
        if not os.path.exists(_db_file):
            raise ObsDbException('Database %s unavailable' % (os.path.abspath(_db_file)))

        self.conn = sqlite3.connect(_db_file)
        if not self.conn:
            raise ObsDbException('Database unavailable')

        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute('''SELECT * FROM %s;''' % 'db_version')
        row = self.cursor.fetchone()
        if row:
            self.db_major = row['major']
            self.db_minor = row['minor']
        else:
            self.db_major = -1
            self.db_minor = -1
    
    def __del__(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def get_db_version(self):
        return (self.db_major, self.db_minor)

    def cursor_new(self):
        return self.conn.cursor()
