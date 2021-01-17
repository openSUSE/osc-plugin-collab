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

from posixpath import join as posixjoin

import util

MATCH_CHANGE_NAME = ''
# FIXME: we hardcode this list of branches since, well, there's no better way to do that :/
BRANCHES_WITHOUT_PKG_MATCH = [ 'fallback', 'cpan', 'pypi' ]

#######################################################################

class UpstreamDb:

    def __init__(self, dest_dir, db_dir, debug = False):
        self.dest_dir = dest_dir
        self._debug = debug

        # we'll store an int, so let's use an int right now
        self._now = int(time.time())

        # keep in memory what we removed
        self._removed_matches = []
        # this is by branch
        self._removed_upstream = {}

        self._dbfile = os.path.join(db_dir, 'upstream.db')

        self.db = None
        self.cursor = None

    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self._debug:
            print('UpstreamDb: %s' % s)

    def __del__(self):
        # needed for the commit
        self._close_db()

    def _open_db(self, create_if_needed = False):
        """ Open a database file, and sets up everything. """
        if self.db:
            return True

        create = False
        if not os.path.exists(self._dbfile):
            if not create_if_needed:
                return False
            else:
                util.safe_mkdir_p(os.path.dirname(self._dbfile))
                create = True

        self.db = sqlite3.connect(self._dbfile)
        self.db.row_factory = sqlite3.Row
        self.cursor = self.db.cursor()

        if create:
            self._sql_setup()

        return True

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
            print('No upstream/package name match database available, keeping previous data.', file=sys.stderr)
            return

        handled = []

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

            if srcpackage in handled:
                print('Source package %s defined more than once in %s.' % (srcpackage, matchfile), file=sys.stderr)
            elif srcpackage in oldmatches:
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
                handled.append(srcpackage)
            else:
                # Add the entry
                self.cursor.execute('''INSERT INTO upstream_pkg_name_match VALUES (
                    NULL, ?, ?, ?
                    );''',
                    (srcpackage, upstream, self._now))
                handled.append(srcpackage)

        file.close()

        # Remove matches that were removed in the source file
        if len(oldmatches) > 0:
            ids = [ id for (id, oldupstream) in list(oldmatches.values()) ]
            where = ' OR '.join([ 'id = ?' for i in range(len(ids)) ])
            self.cursor.execute('''DELETE FROM upstream_pkg_name_match WHERE %s;''' % where, ids)
            #  will be used in get_changed_packages()
            self._removed_matches = list(oldmatches.keys())
        else:
            self._removed_matches = []

    def _get_upstream_name_branches(self):
        result = {}

        self.cursor.execute('''SELECT upstream FROM upstream_pkg_name_match WHERE upstream LIKE "%|%"''')
        for row in self.cursor:
            name_branch = row['upstream']
            index = name_branch.find('|')
            name = name_branch[:index]
            limit = name_branch[index + 1:]
            item = (name_branch, limit)

            if name in result:
                name_branches = result[name]
                name_branches.append(item)
                result[name] = name_branches
            else:
                result[name] = [ item ]

        return result

    def _get_branch_data(self, branch):
        self.cursor.execute('''SELECT id, mtime FROM branches WHERE
            branch = ?;''', (branch,))
        row = self.cursor.fetchone()
        if row:
            return (row['id'], row['mtime'])
        else:
            return ('', '')

    def _update_upstream_data(self, branch, upstream_name_branches):
        branch_path = os.path.join(self.dest_dir, branch)

        if not os.path.exists(branch_path):
            print('No file %s available for requested branch %s, keeping previous data if available.' % (branch_path, branch), file=sys.stderr)
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

        # upstream data, after we've converted the names to branch names if
        # needed. For instance, glib:1.2.10 will translate to the "glib|1.3"
        # name but also to the "glib" name if it doesn't exist yet or if the
        # version there is lower than 1.2.10.
        real_upstream_data = {}

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

            if match.group(1) == 'fallback':
                url = ''
            elif match.group(1) == 'nonfgo':
                url = match.group(4)
            elif match.group(1) == 'upstream':
                url = ''
            elif match.group(1) == 'cpan':
                url = posixjoin('http://cpan.perl.org/CPAN/authors/id/', match.group(4))
            elif match.group(1) == 'pypi':
                url = match.group(4)
            elif match.group(1) == 'fgo':
                versions = version.split('.')
                if len(versions) == 1:
                    majmin = version
                elif int(versions[0]) >= 40:
                    majmin = versions[0]
                else:
                    majmin = versions[0] + '.' + versions[1]
                url = 'https://download.gnome.org/sources/%s/%s/%s-%s.tar.xz' % (name, majmin, name, version)
            else:
                print('Unknown upstream group for metadata: %s (full line: \'%s\').' % (match.group(1), line), file=sys.stderr)
                url = ''

            ignore = False
            if name in real_upstream_data:
                (current_version, current_url) = real_upstream_data[name]
                if util.version_ge(current_version, version):
                    ignore = True

            if not ignore:
                real_upstream_data[name] = (version, url)

            # Now also fill data for 'glib|1.2.10' if it fits
            if name in upstream_name_branches:
                # name = 'glib', upstream_name_branch = 'glib|1.2.10'
                # and limit = '1.2.10'
                for (upstream_name_branch, limit) in upstream_name_branches[name]:
                    if upstream_name_branch in real_upstream_data:
                        (current_version, current_url) = real_upstream_data[upstream_name_branch]
                        if util.version_ge(current_version, version):
                            continue

                    if util.version_ge(version, limit):
                        continue

                    real_upstream_data[upstream_name_branch] = (version, url)


        for (name, (version, url)) in list(real_upstream_data.items()):
            if name in olddata:
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

        # Remove data that was removed in the source file
        if len(olddata) > 0:
            ids = [ id for (id, version, url) in list(olddata.values()) ]
            # Delete by group of 50, since it once had to remove ~1800 items
            # and it didn't work fine
            chunk_size = 50
            ids_len = len(ids)
            for index in range(ids_len / chunk_size):
                chunk_ids = ids[index * chunk_size : (index + 1) * chunk_size]
                where = ' OR '.join([ 'id = ?' for i in range(len(chunk_ids)) ])
                self.cursor.execute('''DELETE FROM upstream WHERE %s;''' % where, chunk_ids)
            remainder = ids_len % chunk_size
            if remainder > 0:
                chunk_ids = ids[- remainder:]
                where = ' OR '.join([ 'id = ?' for i in range(len(chunk_ids)) ])
                self.cursor.execute('''DELETE FROM upstream WHERE %s;''' % where, chunk_ids)

            self._removed_upstream[branch] = list(olddata.keys())
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
        else:
            return ''

    def _exist_in_branch_from_db(self, branch, name):
        (branch_id, branch_mtime) = self._get_branch_data(branch)
        if not branch_id:
            return False

        self.cursor.execute('''SELECT name FROM upstream WHERE
            name = ? AND branch = ?;''', (name, branch_id))
        row = self.cursor.fetchone()
        if row:
            return True
        else:
            return False

    def exists_in_branches(self, branches, srcpackage):
        if not self._open_db():
            return False

        name = self._get_upstream_name(srcpackage)

        for branch in branches:
            if branch in BRANCHES_WITHOUT_PKG_MATCH:
                query_name = srcpackage
            else:
                query_name = name

            if query_name and self._exist_in_branch_from_db(branch, query_name):
                return True

        return False

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

    def get_upstream_data(self, branches, srcpackage):
        if not self._open_db():
            return ('', '', '')

        name = self._get_upstream_name(srcpackage)

        (version, url) = ('', '')

        for branch in branches:
            if branch in BRANCHES_WITHOUT_PKG_MATCH:
                query_name = srcpackage
            else:
                query_name = name

            if query_name:
                (version, url) = self._get_data_from_db(branch, query_name)
            if version:
                break

        if not version:
            if self._is_without_upstream(srcpackage):
                version = '--'
            else:
                version = ''

        return (name, version, url)

    def get_mtime(self):
        if not self._open_db():
            return -1

        self.cursor.execute('''SELECT MAX(updated) FROM upstream_pkg_name_match;''')
        max_match = self.cursor.fetchone()[0]
        self.cursor.execute('''SELECT MAX(updated) FROM upstream;''')
        max_data = self.cursor.fetchone()[0]
        if not isinstance(max_data, int):
            max_data = 0
        return max(max_match, max_data)

    def get_changed_packages(self, old_mtime):
        if not self._open_db():
            return {}

        changed = {}

        self.cursor.execute('''SELECT srcpackage FROM upstream_pkg_name_match
                    WHERE updated > ?;''', (old_mtime,))
        changed[MATCH_CHANGE_NAME] = [ row['srcpackage'] for row in self.cursor ]
        changed[MATCH_CHANGE_NAME].extend(self._removed_matches)

        self.cursor.execute('''SELECT id, branch FROM branches;''')
        branches = []
        for (id, branch) in self.cursor:
            branches.append((id, branch))
            if branch in self._removed_upstream:
                changed[branch] = self._removed_upstream[branch]
            else:
                changed[branch] = []

        # Doing a joint query is slow, so we do a cache first
        match_cache = {}
        self.cursor.execute('''SELECT srcpackage, upstream FROM upstream_pkg_name_match;''')
        for (srcpackage, upstream) in self.cursor:
            if upstream in match_cache:
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
            if branch in BRANCHES_WITHOUT_PKG_MATCH:
                for (name,) in self.cursor:
                    changed[branch].append(name)
            else:
                for (name,) in self.cursor:
                    if name in match_cache:
                        changed[branch].extend(match_cache[name])

        self._debug_print('%d upstream(s) changed' % sum([ len(i) for i in list(changed.values()) ]))

        for branch in list(changed.keys()):
            if not changed[branch]:
                del changed[branch]

        return changed

    def update(self, project_configs, rebuild = False):
        if rebuild:
            self._close_db()
            if os.path.exists(self._dbfile):
                os.unlink(self._dbfile)

        self._open_db(create_if_needed = True)

        self._update_upstream_pkg_name_match('upstream-packages-match.txt')

        upstream_name_branches = self._get_upstream_name_branches()

        branches = []
        for project in list(project_configs.keys()):
            branches.extend(project_configs[project].branches)
        branches = set(branches)

        for branch in branches:
            if branch:
                self._update_upstream_data(branch, upstream_name_branches)

        self._remove_old_branches(branches)

        self.db.commit()

#######################################################################


def main(args):
    class ProjectConfig:
        def __init__(self, branch):
            self.branch = branch

    configs = {}
    configs['gnome-2.32'] = ProjectConfig('gnome-2.32')
    configs['latest'] = ProjectConfig('latest')

    upstream = UpstreamDb('/tmp/obs-dissector/cache/upstream', '/tmp/obs-dissector/tmp')
    upstream.update(configs)

    print('glib (latest): %s' % (upstream.get_upstream_data('latest', 'glib', True),))
    print('glib2 (latest): %s' % (upstream.get_upstream_data('latest', 'glib2', True),))
    print('gtk2 (2.32): %s' % (upstream.get_upstream_data('gnome-2.32', 'gtk2', True),))
    print('gtk2 (latest): %s' % (upstream.get_upstream_data('latest', 'gtk2', True),))
    print('gtk3 (latest): %s' % (upstream.get_upstream_data('latest', 'gtk3', True),))
    print('gobby04 (latest): %s' % (upstream.get_upstream_data('latest', 'gobby04', True),))
    print('gobby (latest): %s' % (upstream.get_upstream_data('latest', 'gobby', True),))
    print('OpenOffice_org (latest, fallback): %s' % (upstream.get_upstream_data('latest', 'OpenOffice_org', False),))


if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
