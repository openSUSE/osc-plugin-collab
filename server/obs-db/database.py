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

import operator
import re
import sqlite3

try:
    from lxml import etree as ET
except ImportError:
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

import upstream
import util

# This script was originally written for an usage with autobuild. It has been
# adapted for the build service, but a few features might still need to be
# ported. TODO-BS or FIXME-BS might indicate them.

# Files to just ignore in the file list of a package.
IGNORE_FILES = [ 'ready', 'MD5SUMS', 'MD5SUMS.meta' ]

# Would be nice to get the list of failed package builds. In autobuild, look
# at /work/built/info/failed/ TODO-BS

# In autobuild, it's easy to get access to the rpmlint reports. Keep this empty
# until we find an easy way to do the same for the build service (maybe just
# parse the output of the build log?)
RPMLINT_ERRORS_PATH = ''
#RPMLINT_ERRORS_PATH = os.path.join(OBS_DISSECTOR_DIR, 'tmp', 'rpmlint')

# Changing this means breaking compatibility with previous db
DB_MAJOR = 4
# Changing this means changing the db while keeping compatibility
# Increase when changing the db. Reset to 0 when changing DB_MAJOR.
DB_MINOR = 0


#######################################################################

class ObsDbException(Exception):
    pass

#######################################################################

class Base:
    sql_table = 'undefined'
    sql_lastid = -1

    @classmethod
    def sql_setup(cls, cursor):
        pass

    def _sql_update_last_id(self, cursor):
        cursor.execute('''SELECT last_insert_rowid();''')
        self.sql_id = cursor.fetchone()[0]
        self.__class__.sql_lastid = self.sql_id

#######################################################################

class File(Base):
    sql_table = 'file'

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            mtime INTEGER,
            srcpackage INTEGER
            );''' % cls.sql_table)

    @classmethod
    def sql_get_all(cls, cursor, srcpackage):
        files = []

        cursor.execute('''SELECT * FROM %s WHERE
            srcpackage = ?
            ;''' % cls.sql_table,
            (srcpackage.sql_id,))

        for row in cursor.fetchall():
            file = File(srcpackage, row['filename'], row['mtime'])
            file.sql_id = row['id']
            files.append(file)

        return files

    @classmethod
    def sql_remove_all(cls, cursor, ids):
        if type(ids) == list:
            where = ' OR '.join([ 'srcpackage = ?' for i in range(len(ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                srcpackage = ?
                ;''' % cls.sql_table,
                (ids,))

    def __init__(self, src, name, mtime):
        self.sql_id = -1

        self.filename = name
        self.src_package = src
        try:
            self.mtime = int(mtime)
        except SyntaxError, e:
            print >> sys.stderr, 'Cannot parse %s as mtime for %s/%s: %s' % (mtime, src, name, e)
            self.mtime = -1

    def sql_add(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding file %s.' % (self.src_package.name, self.filename))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?, ?, ?
            );''' % self.sql_table,
            (self.filename, self.mtime, self.src_package.sql_id))
        self._sql_update_last_id(cursor)

    def sql_update_from(self, cursor, new_file):
        if self.sql_id < 0:
            raise ObsDbException('File %s of %s used for update does not have a SQL id.' % (self.filename, self.src_package.name))
        cursor.execute('''UPDATE %s SET
            mtime = ?
            WHERE id = ?
            ;''' % self.sql_table,
            (new_file.mtime, self.sql_id))

    def sql_remove(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing file %s.' % (self.src_package.name, self.filename))
        cursor.execute('''DELETE FROM %s WHERE
            filename = ? AND
            srcpackage = ?
            ;''' % self.sql_table,
            (self.filename, self.src_package.sql_id))

    def __ne__(self, other):
        if (self.filename != other.filename or
            self.mtime != other.mtime or
            self.src_package.name != other.src_package.name or
            self.src_package.project.name != other.src_package.project.name):
            return True
        return False

    def __eq__(self, other):
        return not self.__ne__(other)

#######################################################################

class Source(Base):
    sql_table = 'source'

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            srcpackage INTEGER,
            nb_in_pack INTEGER
            );''' % cls.sql_table)

    @classmethod
    def sql_get_all(cls, cursor, srcpackage):
        sources = []

        cursor.execute('''SELECT * FROM %s WHERE
            srcpackage = ?
            ;''' % cls.sql_table,
            (srcpackage.sql_id,))

        for row in cursor.fetchall():
            source = Source(srcpackage, row['filename'], row['nb_in_pack'])
            source.sql_id = row['id']
            sources.append(source)

        return sources

    @classmethod
    def sql_remove_all(cls, cursor, ids):
        if type(ids) == list:
            where = ' OR '.join([ 'srcpackage = ?' for i in range(len(ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                srcpackage = ?
                ;''' % cls.sql_table,
                (ids,))

    def __init__(self, src, name, i):
        self.sql_id = -1

        self.filename = name
        self.src_package = src
        self.number = i

    def sql_add(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding source %s.' % (self.src_package.name, self.filename))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?, ?, ?
            );''' % self.sql_table,
            (self.filename, self.src_package.sql_id, self.number))
        self._sql_update_last_id(cursor)

    def sql_update_from(self, cursor, new_source):
        if self.sql_id < 0:
            raise ObsDbException('Source %s of %s used for update does not have a SQL id.' % (self.filename, self.src_package.name))
        cursor.execute('''UPDATE %s SET
            nb_in_pack = ?
            WHERE id = ?
            ;''' % self.sql_table,
            (new_source.number, self.sql_id))

    def sql_remove(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing source %s.' % (self.src_package.name, self.filename))
        cursor.execute('''DELETE FROM %s WHERE
            filename = ? AND
            srcpackage = ? AND
            nb_in_pack = ?
            ;''' % self.sql_table,
            (self.filename, self.src_package.sql_id, self.number))

    def __ne__(self, other):
        if (self.filename != other.filename or
            self.number != other.number or
            self.src_package.name != other.src_package.name or
            self.src_package.project.name != other.src_package.project.name):
            return True
        return False

    def __eq__(self, other):
        return not self.__ne__(other)

#######################################################################

class Patch(Base):
    sql_table = 'patch'

    # Format of tag is: "# PATCH-{FIX|FEATURE}-{OPENSUSE|SLED|UPSTREAM} name-of-file.patch bncb.novell.com_bug_number bgob.gnome.org_bug_number you@example.com -- this patch..."
    # PATCH-NEEDS-REBASE is also a known tag
    # We remove trailing ':' for tags too...
    re_strip_comment = re.compile('^#[#\s]*([\S]*[^:\s]):?\s*(.*)$', re.UNICODE)
    # anything that looks like something.diff or something.patch
    re_get_filename = re.compile('^\s*(\S+\.(?:diff|patch))\s*(.*)$')
    # anything that looks like word123 or word#123
    re_get_bug_number = re.compile('^\s*([a-zA-Z]+)#?(\d+)\s*(.*)$')
    # anything that looks like a@a
    re_get_email = re.compile('^\s*(\S+@\S+)\s*(.*)$')
    # remove "--" if it's leading the string
    re_get_short_descr = re.compile('^\s*(?:--\s*)?(.*)$')

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            srcpackage INTEGER,
            nb_in_pack INTEGER,
            apply_order INTEGER,
            disabled INTEGER,
            tag TEXT,
            tag_filename TEXT,
            short_descr TEXT,
            descr TEXT,
            bnc INTEGER,
            bgo INTEGER,
            bmo INTEGER,
            bln INTEGER,
            brc INTEGER,
            fate INTEGER,
            cve INTEGER
            );''' % cls.sql_table)

    @classmethod
    def sql_get_all(cls, cursor, srcpackage):
        patches = []

        cursor.execute('''SELECT * FROM %s WHERE
            srcpackage = ?
            ;''' % cls.sql_table,
            (srcpackage.sql_id,))

        for row in cursor.fetchall():
            patch = Patch(srcpackage, row['filename'], row['nb_in_pack'], row['disabled'])
            patch.sql_id = row['id']
            patch.apply_order = row['apply_order']
            patch.tag = row['tag']
            patch.tag_filename = row['tag_filename']
            patch.bnc = row['bnc']
            patch.bgo = row['bgo']
            patch.bmo = row['bmo']
            patch.bln = row['bln']
            patch.brc = row['brc']
            patch.fate = row['fate']
            patch.cve = row['cve']
            patch.short_descr = row['short_descr']
            patch.descr = row['descr']
            patches.append(patch)

        return patches

    @classmethod
    def sql_remove_all(cls, cursor, ids):
        if type(ids) == list:
            where = ' OR '.join([ 'srcpackage = ?' for i in range(len(ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                srcpackage = ?
                ;''' % cls.sql_table,
                (ids,))

    def __init__(self, src, name, i, disabled=True):
        self.sql_id = -1

        self.filename = name
        self.number = i
        self.apply_order = -1
        if disabled:
            self.disabled = 1
        else:
            self.disabled = 0
        self.src_package = src
        self.tag = ''
        self.tag_filename = ''
        self.bnc = 0
        self.bgo = 0
        self.bmo = 0
        self.bln = 0
        self.brc = 0
        self.fate = 0
        self.cve = 0
        self.short_descr = ''
#FIXME read the header from the patch itself
        self.descr = ''

    def set_tag(self, tag_line):
        match = Patch.re_strip_comment.match(tag_line)
        if not match:
            return
        self.tag = match.group(1)
        buf = match.group(2)

        match = Patch.re_get_filename.match(buf)
        if match:
            self.tag_filename = match.group(1)
            buf = match.group(2)

        while True:
            match = Patch.re_get_bug_number.match(buf)
            if not match:
                break

            buf = match.group(3)

            if match.group(1) == 'bnc':
                self.bnc = int(match.group(2))
            elif match.group(1) == 'bgo':
                self.bgo = int(match.group(2))
            elif match.group(1) == 'bmo':
                self.bmo = int(match.group(2))
            elif match.group(1) == 'bln':
                self.bln = int(match.group(2))
            elif match.group(1) == 'brc':
                self.brc = int(match.group(2))
            elif match.group(1) == 'fate':
                self.fate = int(match.group(2))
            elif match.group(1) == 'cve':
                self.cve = int(match.group(2))

        match = Patch.re_get_email.match(buf)
        if match:
#FIXME what to do with match.group(1)
            buf = match.group(2)

        match = Patch.re_get_short_descr.match(buf)
        if match:
            self.short_descr = match.group(1)
        else:
            print >> sys.stderr, 'Weird error with patch tag analysis on %s: ' % tag_line
            self.short_descr = buf

    def set_apply_order(self, order):
        self.apply_order = order

    def set_disabled(self, disabled):
        if disabled:
            self.disabled = 1
        else:
            self.disabled = 0

    def sql_add(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding patch %s.' % (self.src_package.name, self.filename))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
            );''' % self.sql_table,
            (self.filename, self.src_package.sql_id, self.number, self.apply_order, self.disabled,
             self.tag, self.tag_filename, self.short_descr, self.descr,
             self.bnc, self.bgo, self.bmo, self.bln, self.brc, self.fate, self.cve))
        self._sql_update_last_id(cursor)

    def sql_update_from(self, cursor, new_patch):
        if self.sql_id < 0:
            raise ObsDbException('Patch %s of %s used for update does not have a SQL id.' % (self.filename, self.src_package.name))
        cursor.execute('''UPDATE %s SET
            nb_in_pack = ?,
            apply_order = ?,
            disabled = ?,
            tag = ?,
            tag_filename = ?,
            short_descr = ?,
            descr = ?,
            bnc = ?,
            bgo = ?,
            bmo = ?,
            bln = ?,
            brc = ?,
            fate = ?,
            cve = ?
            WHERE id = ?
            ;''' % self.sql_table,
            (new_patch.number, new_patch.apply_order, new_patch.disabled,
             new_patch.tag, new_patch.tag_filename, new_patch.short_descr, new_patch.descr,
             new_patch.bnc, new_patch.bgo, new_patch.bmo, new_patch.bln, new_patch.brc, new_patch.fate, new_patch.cve,
             self.sql_id))

    def sql_remove(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing patch %s.' % (self.src_package.name, self.filename))
        cursor.execute('''DELETE FROM %s WHERE
            filename = ? AND
            srcpackage = ? AND
            nb_in_pack = ?
            ;''' % self.sql_table,
            (self.filename, self.src_package.sql_id, self.number))

    def __ne__(self, other):
        if (self.filename != other.filename or
            self.number != other.number or
            self.apply_order != other.apply_order or
            self.disabled != other.disabled or
            self.tag != other.tag or
            self.tag_filename != other.tag_filename or
            self.bnc != other.bnc or
            self.bgo != other.bgo or
            self.bmo != other.bmo or
            self.bln != other.bln or
            self.brc != other.brc or
            self.fate != other.fate or
            self.cve != other.cve or
            self.short_descr != other.short_descr or
            self.descr != other.descr or
            self.src_package.name != other.src_package.name or
            self.src_package.project.name != other.src_package.project.name):
            return True
        return False

    def __eq__(self, other):
        return not self.__ne__(other)

#######################################################################

class RpmlintReport(Base):
    sql_table = 'rpmlint'
    re_rpmlint = re.compile('\s*(.+):\s+(.):\s+(\S+)\s+(\S*)(?:\s+.*)?')
    re_rpmlint_summary = re.compile('\s*\d+\s+packages\s+and\s+\d+\s+spec\s*files\s+checked\s*;')

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            srcpackage INTEGER,
            level TEXT,
            type TEXT,
            detail TEXT,
            descr TEXT
            );''' % cls.sql_table)

    @classmethod
    def sql_get_all(cls, cursor, srcpackage):
        rpmlints = []

        cursor.execute('''SELECT * FROM %s WHERE
            srcpackage = ?
            ;''' % cls.sql_table,
            (srcpackage.sql_id,))

        for row in cursor.fetchall():
            rpmlint = RpmlintReport(srcpackage, row['level'], row['type'], row['detail'])
            rpmlint.sql_id = row['id']
            rpmlint.descr = row['descr']
            rpmlints.append(rpmlint)

        return rpmlints

    @classmethod
    def sql_remove_all(cls, cursor, ids):
        if type(ids) == list:
            where = ' OR '.join([ 'srcpackage = ?' for i in range(len(ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                srcpackage = ?
                ;''' % cls.sql_table,
                (ids,))

    @classmethod
    def analyze(cls, srcpackage, filepath):
        rpmlints = []

        file = open(filepath)

        # read everything until we see the rpmlint report header
        while True:
            line = file.readline()
            if line == '':
                break

            # this is not the beginning of the header
            if line[:-1] != 'RPMLINT report:':
                continue

            # we've found the beginning of the header, so let's read the whole
            # header
            line = file.readline()
            # note: we remove spurious spaces because the build service sometimes add some
            if line[:-1].replace(' ', '') != '===============':
                # oops, this is not what we expected, so go back.
                file.seek(-len(line), os.SEEK_CUR)

            break

        rpmlints_without_descr = []
        descr = None
        separator = True

        # now let's analyze the real important lines
        while True:
            line = file.readline()
            if line == '':
                break

            # empty line: this is either the separator between two series of
            # entries of the same type, or just an empty line.
            # in the former case, this means we'll be able to set the
            # description of the former series and save the series; we just
            # need to be sure we're starting a new series
            if line[:-1] == '':
                separator = True
                continue

            # let's see if this is the end of the rpmlint report, and stop
            # reading if this is the case
            match = cls.re_rpmlint_summary.match(line)
            if match:
                break

            # is this a new entry?
            match = cls.re_rpmlint.match(line)
            if match:
                # we had an old series, so save it
                if separator:
                    if len(rpmlints_without_descr) > 0:
                        for rpmlint in rpmlints_without_descr:
                            rpmlint.descr = descr
                        rpmlints.extend(rpmlints_without_descr)
                        # reset state
                        rpmlints_without_descr = []
                        descr = None
                    separator = False

                package = match.group(1)
                src = package.find('.src:')
                if src > 0:
                    line = package.rstrip()[src + len('.src:'):]
                    try:
                        line = int(line)
                    except:
                        print >> sys.stderr, 'Cannot parse source package line in rpmlint line from %s (%s): %s' % (srcpackage.name, srcpackage.project.name, package)
                        line = None
                else:
                    line = None

                level = match.group(2)
                type = match.group(3)
                detail = match.group(4).strip()
                if line != None:
                    if detail == '':
                        detail = 'line %d' % line
                    else:
                        detail = detail + ' (line %d)' % line

                rpmlints_without_descr.append(RpmlintReport(srcpackage, level, type, detail))
                continue

            # this is not a new entry and not an empty line, so this is the
            # description for the past few rpmlint entries. This is only
            # expected if we had some entries before
            if len(rpmlints_without_descr) == 0:
                print >> sys.stderr, 'Unexpected rpmlint line from %s (%s): %s' % (srcpackage.name, srcpackage.project.name, line[:-1])
                continue

            if descr:
                descr = descr + ' ' + line[:-1]
            else:
                descr = line[:-1]


        if len(rpmlints_without_descr) > 0:
            rpmlints.extend(rpmlints_without_descr)

        file.close()

        return rpmlints

    def __init__(self, src_package, level, type, detail):
        self.sql_id = -1

        self.src_package = src_package
        self.level = level
        self.type = type
        self.detail = detail
        self.descr = None

    def sql_add(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding rpmlint report.' % (self.src_package.name,))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?,
            ?, ?, ?, ?
            );''' % self.sql_table,
            (self.src_package.sql_id,
             self.level, self.type, self.detail, self.descr))
        self._sql_update_last_id(cursor)

    def sql_update_from(self, cursor, new_report):
        raise ObsDbException('Rpmlint reports cannot be updated since they do not change with time (they get added or removed).')

    def sql_remove(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing rpmlint report.' % (self.src_package.name,))
        cursor.execute('''DELETE FROM %s WHERE
            srcpackage = ? AND
            level = ? AND
            type = ? AND
            detail = ? AND
            descr = ?
            ;''' % self.sql_table,
            (self.src_package.sql_id, self.level, self.type, self.detail, self.descr))

    def __ne__(self, other):
        if (self.level != other.level or
            self.type != other.type or
            self.detail != other.detail or
            self.descr != other.descr or
            self.src_package.name != other.src_package.name or
            self.src_package.project.name != other.src_package.project.name):
            return True
        return False

    def __eq__(self, other):
        return not self.__ne__(other)

#######################################################################

class Package(Base):
    sql_table = 'package'

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            name TEXT,
            srcpackage INTEGER,
            summary TEXT,
            description TEXT
            );''' % cls.sql_table)

    @classmethod
    def sql_get_all(cls, cursor, srcpackage):
        packages = []

        cursor.execute('''SELECT * FROM %s WHERE
            srcpackage = ?
            ;''' % cls.sql_table,
            (srcpackage.sql_id,))

        for row in cursor.fetchall():
            package = Package(srcpackage, row['name'])
            package.sql_id = row['id']
            package.summary = row['summary']
            package.description = row['description']
            packages.append(package)

        return packages

    @classmethod
    def sql_remove_all(cls, cursor, ids):
        if type(ids) == list:
            where = ' OR '.join([ 'srcpackage = ?' for i in range(len(ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                srcpackage = ?
                ;''' % cls.sql_table,
                (ids,))

    def __init__(self, src, name):
        self.sql_id = -1

        self.name = name
        self.src_package = src
        self.summary = ''
#FIXME we don't parse the descriptions right now
        self.description = ''

    def sql_add(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding package %s.' % (self.src_package.name, self.name))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?, ?,
            ?, ?
            );''' % self.sql_table,
            (self.name, self.src_package.sql_id,
             self.summary, self.description))
        self._sql_update_last_id(cursor)

    def sql_update_from(self, cursor, new_package):
        if self.sql_id < 0:
            raise ObsDbException('Package %s of %s used for update does not have a SQL id.' % (self.name, self.src_package.name))
        cursor.execute('''UPDATE %s SET
            summary = ?,
            description = ?
            WHERE id = ?
            ;''' % self.sql_table,
            (new_package.summary, new_package.description, self.sql_id))

    def sql_remove(self, cursor):
        if self.src_package.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing package %s.' % (self.src_package.name, self.name))
        cursor.execute('''DELETE FROM %s WHERE
            name = ? AND
            srcpackage = ?
            ;''' % self.sql_table,
            (self.name, self.src_package.sql_id))

    def set_summary(self, summary):
        # make sure we have utf-8 for sqlite3, else we get
        # sqlite3.ProgrammingError
        try:
            self.summary = summary.encode('utf8')
        except UnicodeDecodeError:
            # we couldn't convert to utf-8: it's likely because we had latin1
            self.summary = summary.decode('latin1')

    def set_description(self, description):
        # see comments in set_summary()
        try:
            self.description = description.encode('utf8')
        except UnicodeDecodeError:
            self.description = description.decode('latin1')

    def __ne__(self, other):
        if (self.name != other.name or
            self.summary != other.summary or
            self.description != other.description or
            self.src_package.name != other.src_package.name or
            self.src_package.project.name != other.src_package.project.name):
            return True
        return False

    def __eq__(self, other):
        return not self.__ne__(other)

#######################################################################

class SrcPackage(Base):
    sql_table = 'srcpackage'

    re_spec_define = re.compile('^%define\s+(\S*)\s+(\S*)', re.IGNORECASE)
    re_spec_name = re.compile('^Name:\s*(\S*)', re.IGNORECASE)
    re_spec_version = re.compile('^Version:\s*(\S*)', re.IGNORECASE)
    re_spec_summary = re.compile('^Summary:\s*(.*)', re.IGNORECASE)
    re_spec_source = re.compile('^Source(\d*):\s*(\S*)', re.IGNORECASE)
    re_spec_patch = re.compile('^((?:#[#\s]*)?)Patch(\d*):\s*(\S*)', re.IGNORECASE)
    re_spec_package = re.compile('^%package\s*(\S.*)', re.IGNORECASE)
    re_spec_package2 = re.compile('^-n\s*(\S*)', re.IGNORECASE)
    re_spec_lang_package = re.compile('^%lang_package', re.IGNORECASE)
    re_spec_prep = re.compile('^%prep', re.IGNORECASE)
    re_spec_build = re.compile('^%build', re.IGNORECASE)
    re_spec_apply_patch = re.compile('^((?:#[#\s]*)?)%patch(\d*)', re.IGNORECASE)

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            name TEXT,
            project INTEGER,
            srcmd5 TEXT,
            version TEXT,
            link_project TEXT,
            link_package TEXT,
            devel_project TEXT,
            devel_package TEXT,
            upstream_name TEXT,
            upstream_version TEXT,
            upstream_url TEXT,
            is_obs_link INTEGER,
            obs_link_has_delta INTEGER,
            obs_error TEXT,
            obs_error_details TEXT
            );''' % cls.sql_table)

    def _sql_fill(self, cursor):
        self.files = File.sql_get_all(cursor, self)
        self.sources = Source.sql_get_all(cursor, self)
        self.patches = Patch.sql_get_all(cursor, self)
        self.rpmlint_reports = RpmlintReport.sql_get_all(cursor, self)
        self.packages = Package.sql_get_all(cursor, self)

    @classmethod
    def _sql_get_from_row(cls, cursor, project, row, recursive = False):
        pkg_object = SrcPackage(row['name'], project)
        pkg_object.sql_id = row['id']
        pkg_object.project = project
        pkg_object.srcmd5 = row['srcmd5']
        pkg_object.version = row['version']
        pkg_object.link_project = row['link_project']
        pkg_object.link_package = row['link_package']
        pkg_object.devel_project = row['devel_project']
        pkg_object.devel_package = row['devel_package']
        pkg_object.upstream_name = row['upstream_name']
        pkg_object.upstream_version = row['upstream_version']
        pkg_object.upstream_url = row['upstream_url']
        pkg_object.is_link = row['is_obs_link'] != 0
        pkg_object.has_delta = row['obs_link_has_delta'] != 0
        pkg_object.error = row['obs_error']
        pkg_object.error_details = row['obs_error_details']

        if recursive:
            pkg_object._sql_fill(cursor)

        return pkg_object

    @classmethod
    def sql_get(cls, cursor, project, name, recursive = False):
        cursor.execute('''SELECT * FROM %s WHERE
            name = ? AND
            project = ?
            ;''' % cls.sql_table,
            (name, project.sql_id))

        rows = cursor.fetchall()
        length = len(rows)

        if length == 0:
            return None
        elif length > 1:
            raise ObsDbException('More than one source package named %s for project %s in database.' % (name, project.name))

        return cls._sql_get_from_row(cursor, project, rows[0], recursive)

    @classmethod
    def sql_get_all(cls, cursor, project, recursive = False):
        srcpackages = []

        cursor.execute('''SELECT * FROM %s WHERE
            project = ?
            ;''' % cls.sql_table,
            (project.sql_id,))

        for row in cursor.fetchall():
            srcpackage = cls._sql_get_from_row(cursor, project, row, False)
            srcpackages.append(srcpackage)

        if recursive:
            # we do a second loop so we can use only one cursor, that shouldn't
            # matter much since the loop is not the slow part
            for srcpackage in srcpackages:
                srcpackage._sql_fill(cursor)

        return srcpackages

    @classmethod
    def sql_remove_all(cls, cursor, project_ids):
        if type(project_ids) == list:
            where = ' OR '.join([ 'project = ?' for i in range(len(project_ids)) ])
            cursor.execute('''SELECT id FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                project_ids)
        else:
            cursor.execute('''SELECT id FROM %s WHERE
                project = ?
                ;''' % cls.sql_table,
                (project_ids,))

        ids = [ id for (id,) in cursor.fetchall() ]
        if not ids:
            return

        Package.sql_remove_all(cursor, ids)
        RpmlintReport.sql_remove_all(cursor, ids)
        Source.sql_remove_all(cursor, ids)
        Patch.sql_remove_all(cursor, ids)
        File.sql_remove_all(cursor, ids)

        if type(project_ids) == list:
            where = ' OR '.join([ 'project = ?' for i in range(len(project_ids)) ])
            cursor.execute('''DELETE FROM %s WHERE
                %s;''' % (cls.sql_table, where),
                project_ids)
        else:
            cursor.execute('''DELETE FROM %s WHERE
                project = ?
                ;''' % cls.sql_table,
                (project_ids,))

    @classmethod
    def sql_simple_remove(cls, cursor, project, package):
        cursor.execute('''SELECT A.id FROM %s as A, %s as B WHERE
            A.project = B.id AND
            B.name = ? AND
            A.name = ?
            ;''' % (cls.sql_table, Project.sql_table),
            (project, package))

        ids = [ id for (id,) in cursor.fetchall() ]
        if not ids:
            return

        Package.sql_remove_all(cursor, ids)
        RpmlintReport.sql_remove_all(cursor, ids)
        Source.sql_remove_all(cursor, ids)
        Patch.sql_remove_all(cursor, ids)
        File.sql_remove_all(cursor, ids)

        where = ' OR '.join([ 'id = ?' for i in range(len(ids)) ])
        cursor.execute('''DELETE FROM %s WHERE
            %s;''' % (cls.sql_table, where),
            ids)

    def __init__(self, name, project):
        self.sql_id = -1

        self.name = name
        self.project = project
        self.srcmd5 = ''
        self.version = ''

        self.upstream_name = ''
        self.upstream_version = ''
        self.upstream_url = ''

        self.packages = []
        self.sources = []
        self.patches = []
        self.files = []
        self.rpmlint_reports = []

        self.link_project = ''
        self.link_package = ''
        self.devel_project = ''
        self.devel_package = ''

        # not booleans, since sqlite doesn't support this
        self.is_link = 0
        # 1 means link delta, 2 means delta but without link so a human being
        # has to look on how to synchronize this
        self.has_delta = 0
        self.error = ''
        self.error_details = ''

        # the package is a link using the branch mechanism
        self.has_branch = 0
        # there's a local _meta file for this package
        self.has_meta = False

        self._ready_for_sql = False

    def sql_add(self, cursor):
        if not self._ready_for_sql:
            raise ObsDbException('Source package %s is a shim object, not to be put in database.' % (self.name,))

        if self.project.sql_id == -1:
            raise ObsDbException('No SQL id for %s when adding source package %s.' % (self.project.name, self.name))
        cursor.execute('''INSERT INTO %s VALUES (
            NULL,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );''' % self.sql_table,
            (self.name, self.project.sql_id, self.srcmd5, self.version, self.link_project, self.link_package, self.devel_project, self.devel_package, self.upstream_name, self.upstream_version, self.upstream_url, self.is_link, self.has_delta, self.error, self.error_details))
        self._sql_update_last_id(cursor)

        for package in self.packages:
            package.sql_add(cursor)

        for rpmlint in self.rpmlint_reports:
            rpmlint.sql_add(cursor)

        for source in self.sources:
            source.sql_add(cursor)

        for patch in self.patches:
            patch.sql_add(cursor)

        for file in self.files:
            file.sql_add(cursor)

    def sql_update_from(self, cursor, new_srcpackage):
        if not new_srcpackage._ready_for_sql:
            raise ObsDbException('Source package %s used for update is a shim object, not to be put in database.' % (new_srcpackage.name,))
        if self.sql_id < 0:
            raise ObsDbException('Source package %s used for update does not have a SQL id.' % (self.name,))

        # might be needed by objects like files that we'll add to the database
        # if they were not present before
        new_srcpackage.sql_id = self.sql_id

        # we obviously don't need to update the id, the name or the project
        cursor.execute('''UPDATE %s SET
            srcmd5 = ?,
            version = ?,
            link_project = ?,
            link_package = ?,
            devel_project = ?,
            devel_package = ?,
            upstream_name = ?,
            upstream_version = ?,
            upstream_url = ?,
            is_obs_link = ?,
            obs_link_has_delta = ?,
            obs_error = ?,
            obs_error_details = ?
            WHERE id = ?
            ;''' % self.sql_table,
            (new_srcpackage.srcmd5, new_srcpackage.version, new_srcpackage.link_project, new_srcpackage.link_package, new_srcpackage.devel_project, new_srcpackage.devel_package, new_srcpackage.upstream_name, new_srcpackage.upstream_version, new_srcpackage.upstream_url, new_srcpackage.is_link, new_srcpackage.has_delta, new_srcpackage.error, new_srcpackage.error_details, self.sql_id))

        def pop_first(list):
            try:
                return list.pop(0)
            except IndexError:
                return None

        def update_list(cursor, oldlist, newlist, attr):
            """ Generic function to update list of objects like files, patches, etc.

                This requires that the lists are sortable by an attribute
                (attr) and that __ne__ and sql_update_from methods exists for
                the objects.

            """
            oldlist.sort(key=operator.attrgetter(attr))
            newlist.sort(key=operator.attrgetter(attr))
            # copy the new list to not edit it
            copylist = list(newlist)
            newitem = pop_first(copylist)
            for olditem in oldlist:
                if not newitem:
                    olditem.sql_remove(cursor)
                    continue
                oldattr = getattr(olditem, attr)
                newattr = getattr(newitem, attr)
                if oldattr < newattr:
                    olditem.sql_remove(cursor)
                elif newattr > oldattr:
                    newitem.sql_add(cursor)
                    newitem = pop_first(copylist)
                else:
                    if olditem != newitem:
                        olditem.sql_update_from(cursor, newitem)
                    newitem = pop_first(copylist)

        update_list(cursor, self.packages, new_srcpackage.packages, 'name')
        update_list(cursor, self.sources,  new_srcpackage.sources,  'filename')
        update_list(cursor, self.patches,  new_srcpackage.patches,  'filename')
        update_list(cursor, self.files,    new_srcpackage.files,    'filename')

        # Rpmlint warnings can only get added/removed, not updated
        for rpmlint in self.rpmlint_reports:
            if not rpmlint in new_srcpackage.rpmlint_reports:
                rpmlint.sql_remove(cursor)
        for rpmlint in new_srcpackage.rpmlint_reports:
            if not rpmlint in self.rpmlint_reports:
                rpmlint.sql_add(cursor)

    def sql_remove(self, cursor):
        if self.project.sql_id == -1:
            raise ObsDbException('No SQL id for %s when removing source package %s.' % (self.project.name, self.name))

        if self.sql_id == -1:
            cursor.execute('''SELECT id FROM %s WHERE
                name = ? AND
                project = ?
                ;''' % self.sql_table,
                (self.name, self.project.sql_id))
            self.sql_id = cursor.fetchone()[0]

        Package.sql_remove_all(cursor, self.sql_id)
        RpmlintReport.sql_remove_all(cursor, self.sql_id)
        Source.sql_remove_all(cursor, self.sql_id)
        Patch.sql_remove_all(cursor, self.sql_id)
        File.sql_remove_all(cursor, self.sql_id)

        cursor.execute('''DELETE FROM %s WHERE
            id = ?
            ;''' % self.sql_table,
            (self.sql_id,))

    def read_from_disk(self, project_directory, upstream_db):
        srcpackage_dir = os.path.join(project_directory, self.name)

        self._analyze_files(srcpackage_dir)
        self._analyze_specs(srcpackage_dir)
        self._analyze_meta(srcpackage_dir)
        self._get_rpmlint_errors()

        if upstream_db and self.project.branch:
            (self.upstream_name, self.upstream_version, self.upstream_url) = upstream_db.get_upstream_data(self.project.branch, self.name, self.project.ignore_fallback)

        if self.project.parent and self.project.parent != self.project.name and not self.is_link and not self.error:
            self.error = 'not-link'

        self._ready_for_sql = True

    def _analyze_files(self, srcpackage_dir):
        linkfile = os.path.join(srcpackage_dir, '_link')
        if os.path.exists(linkfile):
            self.is_link = 1

            try:
                root = ET.parse(linkfile).getroot()
            except SyntaxError, e:
                print >> sys.stderr, 'Cannot parse %s: %s' % (linkfile, e)
            else:
                node = root.find('patches')
                if node is not None:
                    if node.find('delete') != None or node.find('apply') != None:
                        self.has_delta = 1
                    if node.find('branch') != None:
                        self.has_branch = 1

        root = None
        files = os.path.join(srcpackage_dir, '_files-expanded')
        if not os.path.exists(files):
            files = os.path.join(srcpackage_dir, '_files')
        if os.path.exists(files):
            try:
                root = ET.parse(files).getroot()
            except SyntaxError, e:
                print >> sys.stderr, 'Cannot parse %s: %s' % (files, e)
            else:
                self.srcmd5 = root.get('srcmd5')
                linkinfo = root.find('linkinfo')
                if linkinfo != None:
                    link_project = linkinfo.get('project')
                    if link_project:
                        self.link_project = link_project
                    link_package = linkinfo.get('package')
                    if link_package:
                        self.link_package = link_package

                    error = linkinfo.get('error')
                    if error:
                        if error.find('does not exist in project') != -1:
                            self.error = 'not-in-parent'
                        elif error.find('could not apply patch') != -1:
                            self.error = 'need-merge-with-parent'
                        self.error_details = error

                    if self.error:
                        self.has_delta = 1

                for node in root.findall('entry'):
                    filename = node.get('name')
                    if filename in IGNORE_FILES:
                        continue
                    mtime = node.get('mtime')
                    self.files.append(File(self, filename, mtime))

        # if we want to force the parent to the project parent, then we do it
        # only if the package is a link and there's no error in the link
        # package
        if self.project.force_project_parent and self.is_link and not self.error and (self.link_project not in [ self.project.parent, self.project.name ] or self.link_package != self.name):
            self.is_link = 0
            self.has_delta = 0
            self.link_project = None
            self.link_package = None

        if not self.is_link and root is not None:
            self._compare_raw_files_with_parent(srcpackage_dir, root)

    def _compare_raw_files_with_parent(self, srcpackage_dir, root):
        '''
            Compare the content of two source packages by looking at the
            present files, and their md5sum.
        '''
        if root is None:
            return
        if not self.project.parent or self.project.parent == self.project.name:
            return

        parent_package_dir = os.path.join(srcpackage_dir, '..', '..', self.project.parent, self.name)
        files = os.path.join(parent_package_dir, '_files-expanded')
        if not os.path.exists(files):
            files = os.path.join(parent_package_dir, '_files')

        if not os.path.exists(files):
            return

        try:
            parent_root = ET.parse(files).getroot()
        except SyntaxError, e:
            print >> sys.stderr, 'Cannot parse %s: %s' % (files, e)
            return

        parent_files = {}
        for node in parent_root.findall('entry'):
            filename = node.get('name')
            if filename in IGNORE_FILES:
                continue
            md5 = node.get('md5')
            parent_files[filename] = md5

        for node in root.findall('entry'):
            filename = node.get('name')
            if filename in IGNORE_FILES:
                continue
            md5 = node.get('md5')
            if not parent_files.has_key(filename):
                self.has_delta = 2
                break
            elif md5 != parent_files[filename]:
                if self.project.lenient_delta:
                    # we don't really care about .changes here
                    if filename[-8:] == '.changes':
                        continue
                    # for spec files, we try to ignore the irrelevant stuff
                    elif filename[-5:] == '.spec':
                        spec = os.path.join(srcpackage_dir, filename)
                        parent_spec = os.path.join(parent_package_dir, filename)
                        if self._specs_are_different_lenient(spec, parent_spec):
                            self.has_delta = 2
                            break
                else:
                    self.has_delta = 2
                    break
            del parent_files[filename]

    def _specs_are_different_lenient(self, spec_a, spec_b):
        '''
            Compare two spec files, but ignore some useless changes:
             - ignore space changes
             - ignore blank lines
             - ignore comments
             - ignore Release tag
             - ignore %changelog
        '''

        def strip_useless_spaces(s):
            return ' '.join(s.split())

        def get_next_line(file):
            while True:
                line = file.readline()
                if len(line) == 0:
                    return None
                line = line[:-1]
                line = strip_useless_spaces(line)
                if not line:
                    continue
                if line[0] == '#':
                    continue
                if line.startswith('Release:'):
                    continue
                if line == '%changelog':
                    return None
                return line

        if not os.path.exists(spec_a) or not os.path.exists(spec_b):
            return True

        file_a = open(spec_a)
        file_b = open(spec_b)

        diff = False

        while True:
            line_a = get_next_line(file_a)
            line_b = get_next_line(file_b)
            if line_a is None:
                if line_b is not None:
                    diff = True
                break
            if line_b is None:
                diff = True
                break
            if line_a != line_b:
                diff = True
                break

        file_a.close()
        file_b.close()

        return diff

    def _analyze_specs(self, srcpackage_dir):
        # Only look at one spec file, since the build service works this way.
        # By default, we take the spec file with the same name as the source
        # package; if it doesn't exist, we take the first one.
        bestfile = None
        specname = self.name + '.spec'

        def _name_is_perfect_match(specname, filename):
            # if the file has a prefix, it has to be '_service:.*' to be
            # considered as perfect candidate
            return filename == specname or (filename.startswith('_service:') and filename.endswith(':' + specname))

        for file in self.files:
            if file.filename[-5:] == '.spec':
                if _name_is_perfect_match(specname, file.filename):
                    if not bestfile or bestfile.mtime < file.mtime:
                        bestfile = file
                else:
                    if not bestfile:
                        bestfile = file
                    elif not _name_is_perfect_match(specname, bestfile.filename) and bestfile.mtime < file.mtime:
                        # the current best file has not a perfect name, so we
                        # just take the best one based on the mtime
                        bestfile = file

        if bestfile:
            self._analyze_spec(os.path.join(srcpackage_dir, bestfile.filename))

    def _analyze_spec(self, filename):
        '''Analyze a spec file and extract the relevant data from there'''
        if not os.path.exists(filename):
            print >> sys.stderr, 'Spec file %s of %s/%s does not exist' % (os.path.basename(filename), self.project.name, self.name)
            return

        spec = open(filename)

        current_package = None
        defines = {}
        defines['name'] = self.name

        def subst_defines(s, defines):
            '''Replace macros like %{version} and %{name} in strings. Useful
               for sources and patches '''
            for key in defines.keys():
                if s.find(key) != -1:
                    value = defines[key]
                    s = s.replace('%%{%s}' % key, value)
                    s = s.replace('%%%s' % key, value)
            return s

        # to help if Summary is defined before Name
        early_summary = False

        line = 'empty'
        while True:
            # we need to remember the previous line for patch tags
#FIXME: some packages have comments on two lines...
            previous_line = line
            line = spec.readline()
            if line == '':
                break

            match = SrcPackage.re_spec_prep.match(line)
            if match:
                break

            match = SrcPackage.re_spec_define.match(line)
            if match:
                value = subst_defines(match.group(2), defines)
                defines[match.group(1)] = value
                continue

            match = SrcPackage.re_spec_name.match(line)
            if match:
                name = match.group(1)
                defines['name'] = name
                current_package = Package(self, match.group(1))
                if early_summary:
                    # if we had a summary before the name, then use it now
                    current_package.set_summary(early_summary)
                    early_summary = None
                self.packages.append(current_package)
                continue

            match = SrcPackage.re_spec_lang_package.match(line)
            if match:
                current_package = Package(self, defines['name'] + '-lang')
                self.packages.append(current_package)
                continue

            match = SrcPackage.re_spec_package.match(line)
            if match:
                pack_line = subst_defines(match.group(1), defines)
                match = SrcPackage.re_spec_package2.match(pack_line)
                if match:
                    current_package = Package(self, match.group(1))
                else:
                    current_package = Package(self, defines['name'] + '-' + pack_line)
                self.packages.append(current_package)
                continue

            match = SrcPackage.re_spec_version.match(line)
            if match:
                # Ignore version if it's redefined for a second package.
                # Test case: MozillaThunderbird.spec, where the main package
                # has a version, and the enigmail subpackage has another
                # version.
                if self.version and len(self.packages) > 1:
                    continue

                self.version = subst_defines(match.group(1), defines)
                defines['version'] = self.version
                continue

            match = SrcPackage.re_spec_summary.match(line)
            if match:
                if not current_package:
                    # save the summary for later
                    early_summary = match.group(1)
                    continue
                current_package.set_summary(match.group(1))
                continue

            match = SrcPackage.re_spec_source.match(line)
            if match:
                if match.group(1) == '':
                    nb = '0'
                else:
                    nb = match.group(1)
                buf = subst_defines(match.group(2), defines)
                source = Source(self, buf, nb)
                self.sources.append(source)
                continue

            match = SrcPackage.re_spec_patch.match(line)
            if match:
                # we don't need it here: we'll explicitly mark the patches as
                # applied later
                disabled = (match.group(1) != '')
                if match.group(2) == '':
                    nb = '0'
                else:
                    nb = match.group(2)
                buf = subst_defines(match.group(3), defines)
                patch = Patch(self, buf, nb)
                patch.set_tag(previous_line)
                self.patches.append(patch)
                continue

        order = 0
        while True:
            line = spec.readline()
            if line == '':
                break

            match = SrcPackage.re_spec_build.match(line)
            if match:
                break

            match = SrcPackage.re_spec_apply_patch.match(line)
            if match:
                disabled = (match.group(1) != '')
                if match.group(2) == '':
                    nb = '0'
                else:
                    nb = match.group(2)
                for patch in self.patches:
                    if patch.number == nb:
                        patch.set_disabled(disabled)
                        patch.set_apply_order(order)
                        break
                order = order + 1
                continue

        spec.close()

    def _analyze_meta(self, srcpackage_dir):
        meta_file = os.path.join(srcpackage_dir, '_meta')
        if not os.path.exists(meta_file):
            return

        try:
            package = ET.parse(meta_file).getroot()
        except SyntaxError, e:
            print >> sys.stderr, 'Cannot parse %s: %s' % (meta_file, e)
            return

        self.has_meta = True

        devel = package.find('devel')
        # "not devel" won't work (probably checks if devel.text is empty)
        if devel == None:
            return

        self.devel_project = devel.get('project', '')
        if not self.devel_project:
            return
        self.devel_package = devel.get('package', '')

    def _get_rpmlint_errors(self):
        if not RPMLINT_ERRORS_PATH or RPMLINT_ERRORS_PATH == '':
            return

        filepath = os.path.join(os.sep, RPMLINT_ERRORS_PATH, self.project.name, self.name + '.log')
        if not os.path.exists(filepath):
            return

        self.rpmlint_reports = RpmlintReport.analyze(self, filepath)

#######################################################################

class Project(Base):
    sql_table = 'project'

    @classmethod
    def sql_setup(cls, cursor):
        cursor.execute('''CREATE TABLE %s (
            id INTEGER PRIMARY KEY,
            name TEXT,
            parent TEXT,
            ignore_upstream INTEGER
            );''' % cls.sql_table)

    @classmethod
    def _sql_get_from_row(cls, cursor, row):
        prj_object = Project(row['name'])
        prj_object.sql_id = row['id']
        prj_object.parent = row['parent']
        prj_object.ignore_upstream = row['ignore_upstream'] != 0

        return prj_object

    @classmethod
    def sql_get(cls, cursor, name, recursive = False):
        cursor.execute('''SELECT * FROM %s WHERE
            name = ?
            ;''' % cls.sql_table,
            (name,))

        rows = cursor.fetchall()
        length = len(rows)

        if length == 0:
            return None
        elif length > 1:
            raise ObsDbException('More than one project named %s in database.' % name)

        row = rows[0]

        prj_object = cls._sql_get_from_row(cursor, row)

        if recursive:
            prj_object.srcpackages = SrcPackage.sql_get_all(cursor, prj_object, recursive)

        return prj_object

    @classmethod
    def sql_get_all(cls, cursor, recursive = False):
        projects = []

        cursor.execute('''SELECT * FROM %s;''' % cls.sql_table)

        for row in cursor.fetchall():
            project = cls._sql_get_from_row(cursor, row)
            projects.append(project)

        if recursive:
            # we do a second loop so we can use only one cursor, that shouldn't
            # matter much since the loop is not the slow part
            prj_object.srcpackages = SrcPackage.sql_get_all(cursor, prj_object, recursive)

        return projects

    @classmethod
    def sql_simple_remove(cls, cursor, project):
        cursor.execute('''SELECT id FROM %s WHERE
            name = ?
            ;''' % cls.sql_table,
            (project,))

        ids = [ id for (id,) in cursor.fetchall() ]
        if not ids:
            return

        SrcPackage.sql_remove_all(cursor, ids)

        where = ' OR '.join([ 'id = ?' for i in range(len(ids)) ])
        cursor.execute('''DELETE FROM %s WHERE
            %s;''' % (cls.sql_table, where),
            ids)

    def __init__(self, name):
        self.sql_id = -1

        self.name = name
        self.srcpackages = []

        # Various options set for this project
        self.parent = ''
        self.branch = ''
        # Should we ignore fallback upstream versions for packages in this
        # project?
        self.ignore_fallback = False
        # Should we ignore the project/package a link points to and always use
        # the configured parent project of this project as parent for the
        # packages?
        # This is useful for projects that are kept in sync with copypac
        # instead of linkpac (and when the devel project links to another
        # parent project). Eg: parent is openSUSE:Published, but package is
        # openSUSE:Devel/test and links to openSUSE:11.1/test
        self.force_project_parent = False
        # When comparing non-link packages to find a delta, should we ignore
        # changes in .changes or useless changes in .spec?
        self.lenient_delta = False

        self._ready_for_sql = False

    def sql_add(self, cursor):
        if not self._ready_for_sql:
            raise ObsDbException('Project %s is a shim object, not to be put in database.' % (self.name,))

        cursor.execute('''INSERT INTO %s VALUES (
            NULL, ?, ?, ?
            );''' % self.sql_table,
            (self.name, self.parent, self.branch == ''))
        self._sql_update_last_id(cursor)

        for srcpackage in self.srcpackages:
            srcpackage.sql_add(cursor)

    def sql_remove(self, cursor):
        if self.sql_id == -1:
            cursor.execute('''SELECT id FROM %s WHERE
                name = ?
                ;''' % self.sql_table,
                (self.name,))
            self.sql_id = cursor.fetchone()[0]

        SrcPackage.sql_remove_all(cursor, self.sql_id)

        cursor.execute('''DELETE FROM %s WHERE
            id = ?
            ;''' % self.sql_table,
            (self.sql_id,))

    def _sync_config(self, projects_config, override_project_name = None):
        """
            When override_project_name is not None, then it means we are using
            the parent configuration.

        """
        if not projects_config:
            return False

        name = override_project_name or self.name

        if not projects_config.has_key(name):
            if not override_project_name and self.parent:
                return self._sync_config(projects_config, override_project_name = self.parent)

            return False

        project_config = projects_config[name]

        if not override_project_name and project_config.parent != self.name:
            self.parent = project_config.parent
        self.branch = project_config.branch
        self.ignore_fallback = project_config.ignore_fallback
        self.force_project_parent = project_config.force_project_parent
        self.lenient_delta = project_config.lenient_delta

        return True

    def read_config(self, projects_config, parent_directory):
        """ Gets the config option for this project, saved in the _obs-db-options file. """
        # We first try to get the project configuration from the global
        # configuration
        if self._sync_config(projects_config):
            return

        # We failed, so let's use the special configuration cache
        config_file = os.path.join(parent_directory, self.name, '_obs-db-options')

        if not os.path.exists(config_file):
            return

        file = open(config_file)
        lines = file.readlines()
        file.close()

        for line in lines:
            line = line[:-1]
            if line.startswith('parent='):
                parent = line[len('parent='):]
                if parent == self.name:
                    parent = ''
                self.parent = parent

            elif line.startswith('branch='):
                branch = line[len('branch='):]
                if not branch:
                    self.branch = ''
                    continue
                self.branch = branch

            elif line.startswith('ignore-fallback='):
                ignore_fallback = line[len('ignore-fallback='):]
                self.ignore_fallback = ignore_fallback.lower() in [ '1', 'true' ]

            elif line.startswith('force-project-parent='):
                force_project_parent = line[len('force-project-parent='):]
                self.force_project_parent = force_project_parent.lower() in [ '1', 'true' ]

            elif line.startswith('lenient-delta='):
                lenient_delta = line[len('lenient-delta='):]
                self.lenient_delta = lenient_delta.lower() in [ '1', 'true' ]

            else:
                raise ObsDbException('Unknown project config option for %s: %s' % (self.name, line))

    def get_meta(self, parent_directory, package_name):
        """ Get the devel package for a specific package. """
        meta_file = os.path.join(parent_directory, self.name, '_pkgmeta')
        if not os.path.exists(meta_file):
            return ('', '')

        try:
            collection = ET.parse(meta_file).getroot()
        except SyntaxError, e:
            print >> sys.stderr, 'Cannot parse %s: %s' % (meta_file, e)
            return ('', '')

        for package in collection.findall('package'):
            name = package.get('name')
            if name != package_name:
                continue

            devel = package.find('devel')
            # "not devel" won't work (probably checks if devel.text is empty)
            if devel == None:
                return ('', '')

            devel_project = devel.get('project', '')
            if not devel_project:
                return ('', '')
            devel_package = devel.get('package', '')

            return (devel_project, devel_package)

        return ('', '')

    def _read_meta(self, project_dir):
        meta_devel = {}

        meta_file = os.path.join(project_dir, '_pkgmeta')
        if not os.path.exists(meta_file):
            return meta_devel

        try:
            collection = ET.parse(meta_file).getroot()
        except SyntaxError, e:
            print >> sys.stderr, 'Cannot parse %s: %s' % (meta_file, e)
            return meta_devel

        for package in collection.findall('package'):
            name = package.get('name')
            if not name:
                continue

            devel = package.find('devel')
            # "not devel" won't work (probably checks if devel.text is empty)
            if devel == None:
                continue

            devel_project = devel.get('project', '')
            if not devel_project:
                continue
            devel_package = devel.get('package', '')

            meta_devel[name] = (devel_project, devel_package)

        return meta_devel

    def read_from_disk(self, parent_directory, upstream_db):
        """
            Note: read_config() has to be called before.

        """
        project_dir = os.path.join(parent_directory, self.name)
        if not os.path.exists(project_dir):
            return

        meta_devel = self._read_meta(project_dir)

        for file in os.listdir(project_dir):
            if file in ['_pkgmeta']:
                continue

            if not os.path.isdir(os.path.join(project_dir, file)):
                continue

            srcpackage = SrcPackage(file, self)
            srcpackage.read_from_disk(project_dir, upstream_db)

            if not srcpackage.has_meta and meta_devel.has_key(srcpackage.name):
                (srcpackage.devel_project, srcpackage.devel_package) = meta_devel[srcpackage.name]

            self.srcpackages.append(srcpackage)

        self._ready_for_sql = True

#######################################################################

class ObsDb:

    def __init__(self, conf, db_dir, mirror_dir, upstream):
        self.conf = conf
        self.db_dir = db_dir
        self.mirror_dir = mirror_dir
        self.upstream = upstream

        self._filename = os.path.join(self.db_dir, 'obs.db')
        self._dbconn = None
        self._cursor = None

    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self.conf.debug:
            print 'ObsDb: %s' % s

    def __del__(self):
        # needed for the commit
        self._close_db()

    def get_cursor(self):
        """ Return a cursor to the database. """
        self._open_existing_db_if_necessary()
        return self._dbconn.cursor()

    def exists(self):
        """ Return True if a database already exists. """
        if not os.path.exists(self._filename):
            return False

        try:
            self._open_existing_db_if_necessary()

            # make sure we have the same version of the format, else it's
            # better to start from scratch
            self._cursor.execute('''SELECT major, minor FROM db_version;''')
            (major, minor) = self._cursor.fetchone()
            if major != DB_MAJOR or minor != DB_MINOR:
                return False

            # just check there are some projects there, to be sure it's valid
            self._cursor.execute('''SELECT id FROM %s;''' % Project.sql_table)
            if len(self._cursor.fetchall()) <= 0:
                return False
        except:
            return False

        return True

    def _open_db(self, filename):
        """ Open a database file, and sets up everything. """
        if self._dbconn:
            self._close_db()
        self._dbconn = sqlite3.connect(filename)
        self._dbconn.row_factory = sqlite3.Row
        self._dbconn.text_factory = sqlite3.OptimizedUnicode
        self._cursor = self._dbconn.cursor()

    def _close_db(self):
        """ Closes the currently open database. """
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._dbconn:
            self._dbconn.commit()
            self._dbconn.close()
            self._dbconn = None

    def _open_existing_db_if_necessary(self):
        """ Opens the database if it's not already opened. """
        if self._dbconn:
            return
        if not os.path.exists(self._filename):
            raise ObsDbException('Database file %s does not exist.' % self._filename)
        self._open_db(self._filename)

    def _create_tables(self):
        self._cursor.execute('''CREATE TABLE db_version (
            major INTEGER,
            minor INTEGER
            );''')
        self._cursor.execute('''INSERT INTO db_version VALUES (
            ?, ?
            );''', (DB_MAJOR, DB_MINOR))

        Project.sql_setup(self._cursor)
        SrcPackage.sql_setup(self._cursor)
        Package.sql_setup(self._cursor)
        Source.sql_setup(self._cursor)
        Patch.sql_setup(self._cursor)
        File.sql_setup(self._cursor)
        RpmlintReport.sql_setup(self._cursor)

        self._dbconn.commit()

    def rebuild(self):
        """ Rebuild the database from scratch. """
        # We rebuild in a temporary file in case there's a bug in the script :-)
        tmpfilename = self._filename + '.new'
        if os.path.exists(tmpfilename):
            os.unlink(tmpfilename)

        util.safe_mkdir_p(self.db_dir)

        self._debug_print('Rebuilding the database')

        try:
            self._open_db(tmpfilename)
            self._create_tables()

            for file in os.listdir(self.mirror_dir):
                if not os.path.isdir(os.path.join(self.mirror_dir, file)):
                    continue
                self.add_project(file)

            self._close_db()
            os.rename(tmpfilename, self._filename)
        except Exception, e:
            if os.path.exists(tmpfilename):
                os.unlink(tmpfilename)
            raise e

    def add_project(self, project):
        """ Add data of all packages from project in the database. """
        self._open_existing_db_if_necessary()

        self._debug_print('Adding project %s' % project)

        prj_object = Project(project)
        prj_object.read_config(self.conf.projects, self.mirror_dir)
        prj_object.read_from_disk(self.mirror_dir, self.upstream)

        prj_object.sql_add(self._cursor)
        # It's apparently not needed to commit each time to keep a low-memory
        # profile, and committing is slowing things down.
        # self._dbconn.commit()

    def update_project(self, project):
        """ Update data of all packages from project in the database. """
        self._open_existing_db_if_necessary()

        # It's simpler to just remove all packages and add them again
        self.remove_project(project)
        self.add_project(project)

    def remove_project(self, project):
        """ Remove the project from the database. """
        self._open_existing_db_if_necessary()

        self._debug_print('Removing project %s' % project)

        Project.sql_simple_remove(self._cursor, project)

    def _add_package_internal(self, prj_object, package):
        """ Internal helper to add a package. """
        self._debug_print('Adding %s/%s' % (prj_object.name, package))

        project_dir = os.path.join(self.mirror_dir, prj_object.name)
        srcpackage_dir = os.path.join(project_dir, package)
        if not os.path.exists(srcpackage_dir):
            print >> sys.stderr, 'Added package %s in %s does not exist in mirror.' % (package, prj_object.name)
            return

        pkg_object = SrcPackage(package, prj_object)
        pkg_object.read_from_disk(project_dir, self.upstream)
        if not pkg_object.has_meta:
            # In theory, this shouldn't be needed since added packages
            # should have a _meta file. Since it's unlikely to happen, it's
            # okay to parse a big project-wide file.
            self._debug_print('No meta during addition of %s/%s' % (prj_object.name, package))
            (pkg_object.devel_project, pkg_object.devel_package) = prj_object.get_meta(self.mirror_dir, package)

        pkg_object.sql_add(self._cursor)

        # Make sure we also have the devel project if we're interested in that
        if pkg_object.has_meta and pkg_object.devel_project and self.conf.projects.has_key(prj_object.name) and self.conf.projects[prj_object.name].checkout_devel_projects:
            devel_prj_object = Project.sql_get(self._cursor, pkg_object.devel_project)
            if not devel_prj_object:
                self.add_project(pkg_object.devel_project)

    def _update_package_internal(self, prj_object, package, oldpkg_object):
        """ Internal helper to update a package. """
        self._debug_print('Updating %s/%s' % (prj_object.name, package))

        project_dir = os.path.join(self.mirror_dir, prj_object.name)
        srcpackage_dir = os.path.join(project_dir, package)
        if not os.path.exists(srcpackage_dir):
            print >> sys.stderr, 'Updated package %s in %s does not exist in mirror.' % (package, prj_object.name)
            return

        update_children = False

        pkg_object = SrcPackage(package, prj_object)
        pkg_object.read_from_disk(project_dir, self.upstream)
        if not pkg_object.has_meta:
            # If the metadata was updated, we should have a _meta file for the
            # package. If this is not the case, then the metadata was not
            # updated, and then it's okay to keep the old metadata (instead of
            # parsing a big project-wide file).
            pkg_object.devel_project = oldpkg_object.devel_project
            pkg_object.devel_package = oldpkg_object.devel_package
        else:
            if (pkg_object.devel_project != oldpkg_object.devel_project or
                pkg_object.devel_package != oldpkg_object.devel_package):
                update_children = True

        oldpkg_object.sql_update_from(self._cursor, pkg_object)

        # If the devel package has changed, then "children" packages might have
        # a different error now. See _not_real_devel_package().
        if update_children:
            self._cursor.execute('''SELECT A.name, B.name
                                    FROM %s AS A, %s AS B
                                    WHERE B.project = A.id AND B.link_project = ? AND (B.link_package = ? OR B.name = ?)
                                    ;''' % (Project.sql_table, SrcPackage.sql_table),
                                    (prj_object.name, package, package))
            children = [ (child_project, child_package) for (child_project, child_package) in self._cursor ]
            for (child_project, child_package) in children:
                self.update_package(child_project, child_package)

        # Make sure we also have the devel project if we're interested in that
        if pkg_object.has_meta and pkg_object.devel_project and self.conf.projects.has_key(prj_object.name) and self.conf.projects[prj_object.name].checkout_devel_projects:
            self._debug_print('Looking at meta during update of %s/%s' % (prj_object.name, package))
            devel_prj_object = Project.sql_get(self._cursor, pkg_object.devel_project)
            if not devel_prj_object:
                self.add_project(pkg_object.devel_project)

    def add_package(self, project, package):
        """ Add the package data in the database from the mirror. """
        self._open_existing_db_if_necessary()

        self._debug_print('Trying to add/update %s/%s' % (project, package))

        prj_object = Project.sql_get(self._cursor, project)
        if not prj_object:
            self.add_project(project)
            return

        prj_object.read_config(self.conf.projects, self.mirror_dir)

        pkg_object = SrcPackage.sql_get(self._cursor, prj_object, package, True)
        if pkg_object:
            self._update_package_internal(prj_object, package, pkg_object)
        else:
            self._add_package_internal(prj_object, package)

    def update_package(self, project, package):
        """ Update the package data in the database from the mirror. """
        # We actually share the code to be more robust
        self.add_package(project, package)

    def remove_package(self, project, package):
        """ Remove the package from the database. """
        self._open_existing_db_if_necessary()

        self._debug_print('Removing %s/%s' % (project, package))

        SrcPackage.sql_simple_remove(self._cursor, project, package)

    def get_devel_projects(self, project):
        """ Return the list of devel projects used by packages in project. """
        self._open_existing_db_if_necessary()

        self._cursor.execute('''SELECT A.devel_project FROM %s as A, %s AS B
                                WHERE A.project = B.id AND B.name = ?
                                GROUP BY devel_project
                                ;''' % (SrcPackage.sql_table, Project.sql_table),
                                (project,))
        return [ devel_project for (devel_project,) in self._cursor.fetchall() if devel_project ]

    def get_projects(self):
        """ Return the list of projects in the database. """
        self._open_existing_db_if_necessary()

        self._cursor.execute('''SELECT name FROM %s;''' % Project.sql_table)
        return [ name for (name,) in self._cursor.fetchall() ]

    def upstream_changes(self, upstream_mtime):
        """ Updates the upstream data that has changed since last time.
        
            Return a list of projects that have been updated.
        
        """
        branches = self.upstream.get_changed_packages(upstream_mtime)

        if not branches:
            return []

        self._open_existing_db_if_necessary()

        # Get all projects, with their config, and update the necessary
        # packages if needed
        projects = Project.sql_get_all(self._cursor, recursive = False)
        for project in projects:
            project.read_config(self.conf.projects, self.mirror_dir)

        updated_projects = set()

        for branch in branches.keys():
            if not branches[branch]:
                continue

            for project in projects:
                if branch == upstream.FALLBACK_BRANCH_NAME:
                    if project.ignore_fallback:
                        continue
                if branch != upstream.MATCH_CHANGE_NAME:
                    if project.branch != branch and branch not in [upstream.FALLBACK_BRANCH_NAME, upstream.CPAN_BRANCH_NAME]:
                        continue

                self._cursor.execute('''SELECT name FROM %s WHERE project = ?;''' % SrcPackage.sql_table, (project.sql_id,))
                srcpackages = [ name for (name,) in self._cursor ]

                # so we're only interested in the intersection of the two sets
                # (in the project, and in the changed entries)
                affected_srcpackages = set(branches[branch]).intersection(srcpackages)

                if not affected_srcpackages:
                    continue

                updated_projects.add(project.name)

                self._debug_print('Upstream changes: %s -- %s' % (project.name, affected_srcpackages))

                for srcpackage in affected_srcpackages:
                    (upstream_name, upstream_version, upstream_url) = self.upstream.get_upstream_data(project.branch, srcpackage, project.ignore_fallback)
                    self._cursor.execute('''UPDATE %s SET
                            upstream_name = ?, upstream_version = ?, upstream_url = ?
                            WHERE name = ? AND project = ?;''' % SrcPackage.sql_table,
                            (upstream_name, upstream_version, upstream_url, srcpackage, project.sql_id))

        return list(updated_projects)

    def get_packages_with_upstream_change(self, upstream_mtime):
        """ Get the list of packages that are affected by upstream changes.

            Return a list of projects, each containing a list of packages, each
            one containing a tuple (upstream_version, upstream_url).

        """
        branches = self.upstream.get_changed_packages(upstream_mtime)

        if not branches:
            return []

        self._open_existing_db_if_necessary()

        # Get all projects, with their config, and update the necessary
        # packages if needed
        projects = Project.sql_get_all(self._cursor, recursive = False)
        for project in projects:
            project.read_config(self.conf.projects, self.mirror_dir)

        result = {}

        for branch in branches.keys():
            if not branches[branch]:
                continue

            for project in projects:
                if branch == upstream.FALLBACK_BRANCH_NAME:
                    if project.ignore_fallback:
                        continue
                if branch != upstream.MATCH_CHANGE_NAME:
                    if project.branch != branch and branch not in [upstream.FALLBACK_BRANCH_NAME, upstream.CPAN_BRANCH_NAME]:
                        continue

                self._cursor.execute('''SELECT name FROM %s WHERE project = ?;''' % SrcPackage.sql_table, (project.sql_id,))
                srcpackages = [ name for (name,) in self._cursor ]

                # so we're only interested in the intersection of the two sets
                # (in the project, and in the changed entries)
                affected_srcpackages = set(branches[branch]).intersection(srcpackages)

                if not affected_srcpackages:
                    continue

                if not result.has_key(project.name):
                    result[project.name] = {}

                self._debug_print('Upstream changes: %s -- %s' % (project.name, affected_srcpackages))

                for srcpackage in affected_srcpackages:
                    if branch in [upstream.FALLBACK_BRANCH_NAME, upstream.CPAN_BRANCH_NAME] and result[project.name].has_key(srcpackage):
                        continue

                    (upstream_name, upstream_version, upstream_url) = self.upstream.get_upstream_data(project.branch, srcpackage, project.ignore_fallback)
                    result[project.name][srcpackage] = (upstream_version, upstream_url)

        return result

    def post_analyze(self):
        """
            Do some post-commit analysis on the db, to find new errors now that
            we have all the data.
        """
        self._open_existing_db_if_necessary()

        self._debug_print('Post analysis')

        def _not_link_and_not_in_parent(devel_package_cache, cursor_helper, row):
            """
                Check if this is not a link and if it doesn't exist in the
                potential parent. In that case, the error is that maybe it
                should exist there
            """
            # Note: if the package was changed in any way, we won't have
            # the 'not-link-not-in-parent' error (since it's added only here).
            # So if we have it, it means the package hasn't been updated and is
            # therefore still a link. But the parent might have been created in
            # the meantime, so it's possible to go back to 'not-link'.

            if row['obs_error'] not in [ 'not-link', 'not-link-not-in-parent' ]:
                return False

            project_parent = row['project_parent']
            if not project_parent:
                return False

            try:
                devel_package_cache[project_parent][row['name']]
                error = 'not-link'
            except KeyError:
                error = 'not-link-not-in-parent'

            if row['obs_error'] != error:
                details = ''
                cursor_helper.execute('''UPDATE %s SET obs_error = ?, obs_error_details = ? WHERE id = ?;''' % SrcPackage.sql_table, (error, details, row['id']))
                return True

            return False

        def _not_real_devel_package(devel_package_cache, cursor_helper, row):
            """
                Look if the link package should really exist there (ie, is it
                the devel package of the parent?)
            """
            # Note: the errors created here can disappear when the devel
            # package of the link package changes, without the current package
            # changing. This is handled in _update_package_internal().

            # the errors here are not relevant to toplevel projects (ie,
            # projects without a parent)
            if row['project_parent'] == '':
                return False

            link_project = row['link_project']
            link_package = row['link_package'] or row['name']

            # internal link inside a project (to build another spec file)
            if link_project == row['project']:
                return False

            try:
                (devel_project, devel_package) = devel_package_cache[link_project][link_package]
                if devel_project != row['project'] or devel_package != row['name']:
                    if devel_project:
                        error = 'not-real-devel'
                        details = 'development project is %s' % devel_project
                    else:
                        error = 'parent-without-devel'
                        details = ''
                    cursor_helper.execute('''UPDATE %s SET obs_error = ?, obs_error_details = ? WHERE id = ?;''' % SrcPackage.sql_table, (error, details, row['id']))
                    return True

            except KeyError:
                # this happens when the parent package doesn't exist; link will
                # be broken, so we already have an error
                pass

            return False


        devel_package_cache = {}
        cursor_helper = self._dbconn.cursor()

        self._cursor.execute('''SELECT name FROM %s;''' % Project.sql_table)
        for row in self._cursor:
            devel_package_cache[row['name']] = {}

        self._cursor.execute('''SELECT A.name, A.devel_project, A.devel_package, B.name AS project FROM %s AS A, %s AS B WHERE A.project = B.id;''' % (SrcPackage.sql_table, Project.sql_table))
        for row in self._cursor:
            devel_package = row['devel_package'] or row['name']
            devel_package_cache[row['project']][row['name']] = (row['devel_project'], devel_package)

        self._cursor.execute('''SELECT A.id, A.name, A.obs_error, A.link_project, A.link_package, B.name AS project, B.parent AS project_parent FROM %s AS A, %s AS B WHERE A.project = B.id;''' % (SrcPackage.sql_table, Project.sql_table))
        for row in self._cursor:
            if _not_link_and_not_in_parent(devel_package_cache, cursor_helper, row):
                continue

            if _not_real_devel_package(devel_package_cache, cursor_helper, row):
                continue

        cursor_helper.close()

