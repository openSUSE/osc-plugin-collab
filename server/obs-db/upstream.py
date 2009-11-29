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

import re
import sqlite3
import time

FALLBACK_BRANCH_NAME = '__fallback__'
MATCH_CHANGE_NAME = ''

#######################################################################

class UpstreamDb:

    def __init__(self, project_configs, dest_dir, db_dir, debug):
        self.dest_dir = dest_dir
        self._debug = debug

        # we'll store an int, so let's use an int right now
        self._now = int(time.time())

        # keep in memory what we removed
        self._removed_matches = []
        # this is by branch
        self._removed_upstream = {}

        dbfile = os.path.join(db_dir, 'upstream.db')
        do_setup = not os.path.exists(dbfile)

        self.db = sqlite3.connect(dbfile)
        self.db.row_factory = sqlite3.Row
        self.cursor = self.db.cursor()

        if do_setup:
            self._sql_setup()

        self._update_upstream_pkg_name_match('upstream-packages-match.txt')
        self._update_upstream_data('fallback', True)

        branches = set([ project_configs[project].branch for project in project_configs.keys() ])
        for branch in branches:
            if branch:
                self._update_upstream_data(branch)

        # add fallback branch
        branches.add(FALLBACK_BRANCH_NAME)
        self._remove_old_branches(branches)

        self.db.commit()

    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self._debug:
            print 'UpstreamDb: %s' % s

    def __del__(self):
        # needed for the commit
        self._close_db()

    def _close_db(self):
        """ Closes the currently open database. """
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.db:
            self.db.commit()
            self.db.close()
            self.db = None

    def _sql_setup(self):
        self.cursor.execute('''CREATE TABLE upstream_pkg_name_match (
            id INTEGER PRIMARY KEY,
            srcpackage TEXT,
            upstream TEXT,
            updated INTEGER
            );''')
        self.cursor.execute('''CREATE TABLE upstream (
            id INTEGER PRIMARY KEY,
            branch INTEGER,
            name TEXT,
            version TEXT,
            url TEXT,
            updated INTEGER
            );''')
        # Note: the branch named FALLBACK_BRANCH_NAME will contain the fallback data
        self.cursor.execute('''CREATE TABLE branches (
            id INTEGER PRIMARY KEY,
            branch TEXT,
            mtime INTEGER
            );''')

    def _is_line_comment(self, line):
        return line[0] == '#' or line.strip() == ''

    def _update_upstream_pkg_name_match(self, matchfile):
        matchpath = os.path.join(self.dest_dir, matchfile)

        self.cursor.execute('''SELECT * FROM upstream_pkg_name_match;''')
        oldmatches = {}
        for row in self.cursor:
            oldmatches[row['srcpackage']] = (row['id'], row['upstream'])

        if not os.path.exists(matchpath):
            print >> sys.stderr, 'No upstream/package name match database available, keeping previous data.'
            return

        file = open(matchpath)
        re_names = re.compile('^(.+):(.*)$')
        while True:
            line = file.readline()

            if len(line) == 0:
                break
            if self._is_line_comment(line):
                continue

            match = re_names.match(line)
            if not match:
                continue

            upstream = match.group(1)
            if match.group(2) != '':
                srcpackage = match.group(2)
            else:
                srcpackage = upstream

            if oldmatches.has_key(srcpackage):
                # Update the entry if it has changed
                (id, oldupstream) = oldmatches[srcpackage]
                if oldupstream != upstream:
                    # Note: we don't put the mtime here, since we use the
                    # updated time in get_changed_packages
                    self.cursor.execute('''UPDATE upstream_pkg_name_match SET
                        upstream = ?, updated = ?
                        WHERE id = ?
                        ;''',
                        (upstream, self._now, id))
                del oldmatches[srcpackage]
            else:
                # Add the entry
                self.cursor.execute('''INSERT INTO upstream_pkg_name_match VALUES (
                    NULL, ?, ?, ?
                    );''',
                    (srcpackage, upstream, self._now))

        file.close()

        # Remove matches that were removed in the source file
        if len(oldmatches) > 0:
            ids = [ id for (id, oldupstream) in oldmatches.values() ]
            where = ' OR '.join([ 'id = ?' for i in range(len(ids)) ])
            self.cursor.execute('''DELETE FROM upstream_pkg_name_match WHERE %s;''' % where, ids)
            #  will be used in get_changed_packages()
            self._removed_matches = oldmatches.keys()
        else:
            self._removed_matches = []

    def _get_branch_data(self, branch):
        self.cursor.execute('''SELECT id, mtime FROM branches WHERE
            branch = ?;''', (branch,))
        row = self.cursor.fetchone()
        if row:
            return (row['id'], row['mtime'])
        else:
            return ('', '')

    def _update_upstream_data(self, branch, is_fallback = False):
        branch_path = os.path.join(self.dest_dir, branch)

        if is_fallback:
            branch = FALLBACK_BRANCH_NAME

        if not os.path.exists(branch_path):
            print >> sys.stderr, 'No file available for requested branch %s, keeping previous data if available.' % (branch or 'fallback')
            return

        (branch_id, branch_mtime) = self._get_branch_data(branch)
        stats = os.stat(branch_path)
        new_mtime = stats.st_mtime

        if not branch_id:
            # the branch does not exist, add it
            self.cursor.execute('''INSERT INTO branches VALUES (
                NULL, ?, ?
                );''',
                (branch, new_mtime))
            self.cursor.execute('''SELECT last_insert_rowid();''')
            branch_id = self.cursor.fetchone()[0]
        else:
            # do not update anything if the file has not changed
            if branch_mtime >= new_mtime:
                return
            # else update the mtime
            self.cursor.execute('''UPDATE branches SET
                mtime = ? WHERE id = ?;''',
                (new_mtime, branch_id))

        self.cursor.execute('''SELECT * FROM upstream WHERE branch = ?;''', (branch_id,))
        olddata = {}
        for row in self.cursor:
            olddata[row['name']] = (row['id'], row['version'], row['url'])

        # a guard against multiple definitions for a module in the same file
        done = {}

        if is_fallback:
            # bad hack to support the fallback format with a regexp with the
            # same amount of groups in the match
            re_upstream_data = re.compile('^(,?)([^,]+),([^,]+)(,.*)?$')
        else:
            re_upstream_data = re.compile('^([^:]*):([^:]+):([^:]+):(.*)$')

        file = open(branch_path)
        while True:
            line = file.readline()

            if len(line) == 0:
                break
            if self._is_line_comment(line):
                continue
            line = line[:-1]

            match = re_upstream_data.match(line)
            if not match:
                continue

            name = match.group(2)
            version = match.group(3)

            # ignore data if it was already in the file
            if done.has_key(name):
                continue
            done[name] = True

            if is_fallback:
                url = ''
            elif match.group(1) == 'nonfgo':
                url = match.group(4)
            elif match.group(1) == 'upstream':
                url = ''
            else:
                versions = version.split('.')
                if len(versions) == 1:
                    majmin = version
                else:
                    majmin = versions[0] + '.' + versions[1]
                url = 'http://ftp.gnome.org/pub/GNOME/sources/%s/%s/%s-%s.tar.bz2' % (name, majmin, name, version)

            if olddata.has_key(name):
                # Update the entry if it has changed
                (id, oldversion, oldurl) = olddata[name]
                if oldversion != version or oldurl != url:
                    # Note: we don't put the mtime here, since we use the
                    # updated time in get_changed_packages
                    self.cursor.execute('''UPDATE upstream SET
                        version = ?, url = ?, updated = ?
                        WHERE id = ?
                        ;''',
                        (version, url, self._now, id))
                del olddata[name]
            else:
                # Add the entry
                self.cursor.execute('''INSERT INTO upstream VALUES (
                    NULL, ?, ?, ?, ?, ?
                    );''',
                    (branch_id, name, version, url, self._now))

        file.close()

        # Remove data that as removed in the source file
        if len(olddata) > 0:
            ids = [ id for (id, version, url) in olddata.values() ]
            where = ' OR '.join([ 'id = ?' for i in range(len(ids)) ])
            self.cursor.execute('''DELETE FROM upstream WHERE %s;''' % where, ids)
            self._removed_upstream[branch] = olddata.keys()
        else:
            self._removed_upstream[branch] = []

    def _remove_old_branches(self, branches):
        self.cursor.execute('''SELECT * FROM branches;''')
        for row in self.cursor:
            branch = row['branch']
            if not branch in branches:
                id = row['id']
                self.cursor.execute('''DELETE FROM upstream WHERE branch = ?;''', (id,))
                self.cursor.execute('''DELETE FROM branches WHERE id = ?;''', (id,))

    def _is_without_upstream(self, name):
        index = name.rfind('branding')
        if index > 0:
            return name[index:] in ['branding-openSUSE', 'branding-SLED', 'branding-SLES']
        return False

    def _get_upstream_name(self, srcpackage):
        self.cursor.execute('''SELECT upstream FROM upstream_pkg_name_match WHERE
            srcpackage = ?;''', (srcpackage,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        elif self._is_without_upstream(srcpackage):
            return srcpackage
        else:
            return ''

    def _get_data_from_db(self, branch, name):
        (branch_id, branch_mtime) = self._get_branch_data(branch)
        if not branch_id:
            return ('', '')

        self.cursor.execute('''SELECT version, url FROM upstream WHERE
            name = ? AND branch = ?;''', (name, branch_id))
        row = self.cursor.fetchone()
        if row:
            return (row[0], row[1])
        else:
            return ('', '')

    def get_upstream_data(self, branch, srcpackage, ignore_fallback):
        name = self._get_upstream_name(srcpackage)

        if branch:
            (version, url) = self._get_data_from_db(branch, name)
        else:
            (version, url) = ('', '')

        if not version:
            if self._is_without_upstream(name):
                version = '--'
            elif not ignore_fallback:
                (version, url) = self._get_data_from_db(FALLBACK_BRANCH_NAME, srcpackage)
            else:
                version = ''

        return (name, version, url)

    def get_mtime(self):
        self.cursor.execute('''SELECT MAX(updated) FROM upstream_pkg_name_match;''')
        max_match = self.cursor.fetchone()[0]
        self.cursor.execute('''SELECT MAX(updated) FROM upstream;''')
        max_data = self.cursor.fetchone()[0]
        return max(max_match, max_data)

    def get_changed_packages(self, old_mtime):
        changed = {}

        self.cursor.execute('''SELECT srcpackage FROM upstream_pkg_name_match
                    WHERE updated > ?;''', (old_mtime,))
        changed[MATCH_CHANGE_NAME] = [ row['srcpackage'] for row in self.cursor ]
        changed[MATCH_CHANGE_NAME].extend(self._removed_matches)

        self.cursor.execute('''SELECT id, branch FROM branches;''')
        branches = []
        for (id, branch) in self.cursor:
            branches.append((id, branch))
            if self._removed_upstream.has_key(branch):
                changed[branch] = self._removed_upstream[branch]
            else:
                changed[branch] = []

        # Doing a joint query is slow, so we do a cache first
        match_cache = {}
        self.cursor.execute('''SELECT srcpackage, upstream FROM upstream_pkg_name_match;''')
        for (srcpackage, upstream) in self.cursor:
            if match_cache.has_key(upstream):
                match_cache[upstream].append(srcpackage)
            else:
                match_cache[upstream] = [ srcpackage ]


        for (id, branch) in branches:
            # Joint query that is slow
            #self.cursor.execute('''SELECT A.srcpackage
            #            FROM upstream_pkg_name_match as A, upstream as B
            #            WHERE B.updated > ? AND B.name = A.upstream AND B.branch = ?;''', (old_mtime, id))
            #changed[branch].extend([ row['srcpackage'] for row in self.cursor ])
            self.cursor.execute('''SELECT name FROM upstream
                        WHERE updated > ? AND branch = ?;''', (old_mtime, id))
            if branch != FALLBACK_BRANCH_NAME:
                for (name,) in self.cursor:
                    if match_cache.has_key(name):
                        changed[branch].extend(match_cache[name])
            else:
                for row in self.cursor:
                    changed[branch].append(row['name'])

        self._debug_print('%d upstream(s) changed' % sum([ len(i) for i in changed.values() ]))

        return changed

#######################################################################


def main(args):
    class ProjectConfig:
        def __init__(self, branch):
            self.branch = branch

    configs = {}
    configs['2.26'] = ProjectConfig('versions-gnome-2.26')
    configs['latest'] = ProjectConfig('versions-latest')

    upstream = UpstreamDb(configs, '/tmp/obs-dissector/tmp')

    print 'gtk2 (2.26): %s' % (upstream.get_upstream_data('versions-gnome-2.26', 'gtk2', True),)
    print 'gtk2 (latest): %s' % (upstream.get_upstream_data('versions-latest', 'gtk2', True),)
    print 'OpenOffice_org (latest, fallback): %s' % (upstream.get_upstream_data('versions-latest', 'OpenOffice_org', False),)


if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
