# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2009, Novell, Inc.
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
# Authors: Vincent Untz <vuntz@novell.com>
#

import os
import sys

import errno
import filecmp

try:
    from lxml import etree as ET
except ImportError:
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

import database
import util


#######################################################################


# Create a global dictionary that will contain the name of the SQL tables, for
# easier use
SQL_TABLES = {}
for attrname in database.__dict__.keys():
    attr = database.__getattribute__(attrname)
    if hasattr(attr, 'sql_table'):
        SQL_TABLES[attrname] = attr.sql_table


#######################################################################


class InfoXmlException(Exception):
    pass


#######################################################################


class InfoXml:

    def __init__(self, dest_dir, cursor, debug = False):
        self.dest_dir = dest_dir
        self._debug = debug
        self._cursor = cursor

        self._version_cache = None

    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self._debug:
            print 'XML: %s' % s

    def _get_version(self, project, package):
        """ Gets the version of a package, in a safe way. """
        try:
            return self._version_cache[project][package]
        except KeyError, e:
            return None

    def _get_package_node_from_row(self, row, ignore_upstream, default_parent_project):
        """ Get the XML node for the package defined in row. """
        name = row['name']
        version = row['version']
        link_project = row['link_project']
        link_package = row['link_package']
        devel_project = row['devel_project']
        devel_package = row['devel_package']
        upstream_version = row['upstream_version']
        upstream_url = row['upstream_url']
        is_link = row['is_obs_link']
        has_delta = row['obs_link_has_delta']
        error = row['obs_error']
        error_details = row['obs_error_details']

        parent_version = None
        devel_version = None

        package = ET.Element('package')
        package.set('name', name)

        if link_project:
            if (link_project != default_parent_project) or (link_package and link_package != name):
                node = ET.SubElement(package, 'parent')
                node.set('project', link_project)
                if link_package and link_package != name:
                    node.set('package', link_package)
            parent_version = self._get_version(link_project, link_package or name)
        elif default_parent_project:
            parent_version = self._get_version(default_parent_project, name)

        if devel_project:
            node = ET.SubElement(package, 'devel')
            node.set('project', devel_project)
            if devel_package and devel_package != name:
                node.set('package', devel_package)
            devel_version = self._get_version(devel_project, devel_package or name)

        if version or upstream_version or parent_version or devel_version:
            node = ET.SubElement(package, 'version')
            if version:
                node.set('current', version)
            if upstream_version:
                node.set('upstream', upstream_version)
            if parent_version:
                node.set('parent', parent_version)
            if devel_version:
                node.set('devel', devel_version)

        if upstream_url:
            upstream = ET.SubElement(package, 'upstream')
            if upstream_url:
                node = ET.SubElement(upstream, 'url')
                node.text = upstream_url

        if is_link:
            node = ET.SubElement(package, 'link')
            if has_delta:
                node.set('delta', 'true')
            else:
                node.set('delta', 'false')
        # deep delta (ie, delta in non-link packages)
        elif has_delta:
            node = ET.SubElement(package, 'delta')

        if error:
            node = ET.SubElement(package, 'error')
            node.set('type', error)
            if error_details:
                node.text = error_details

        return package

    def _get_project_node(self, project):
        """ Get the XML node for project. """
        self._cursor.execute('''SELECT * FROM %(Project)s WHERE name = ?;''' % SQL_TABLES, (project,))
        row = self._cursor.fetchone()

        if not row:
            raise InfoXmlException('Non-existing project: %s' % project)

        if not self._version_cache.has_key(project):
            raise InfoXmlException('Version cache was not created correctly: %s is not in the cache' % project)

        project_id = row['id']
        parent_project = row['parent']
        ignore_upstream = row['ignore_upstream']

        prj_node = ET.Element('project')
        prj_node.set('name', project)
        if parent_project:
            prj_node.set('parent', parent_project)
        if ignore_upstream:
            prj_node.set('ignore_upstream', 'true')

        should_exist = {}
        self._cursor.execute('''SELECT A.name AS parent_project, B.name AS parent_package, B.devel_package
                               FROM %(Project)s AS A, %(SrcPackage)s AS B
                               WHERE A.id = B.project AND devel_project = ?
                               ORDER BY A.name, B.name;''' % SQL_TABLES, (project,))
        for row in self._cursor:
            should_parent_project = row['parent_project']
            should_parent_package = row['parent_package']
            should_devel_package = row['devel_package'] or should_parent_package
            should_exist[should_devel_package] = (should_parent_project, should_parent_package)

        self._cursor.execute('''SELECT * FROM %(SrcPackage)s
                               WHERE project = ?
                               ORDER BY name;''' % SQL_TABLES, (project_id,))
        for row in self._cursor:
            pkg_node = self._get_package_node_from_row(row, ignore_upstream, parent_project)
            prj_node.append(pkg_node)
            try:
                del should_exist[row['name']]
            except KeyError:
                pass

        if len(should_exist) > 0:
            missing_node = ET.Element('missing')
            for (should_package_name, (should_parent_project, should_parent_package)) in should_exist.iteritems():
                missing_pkg_node = ET.Element('package')

                missing_pkg_node.set('name', should_package_name)
                missing_pkg_node.set('parent_project', should_parent_project)
                if should_package_name != should_parent_package:
                    missing_pkg_node.set('parent_package', should_parent_package)

                missing_node.append(missing_pkg_node)

            prj_node.append(missing_node)

        return prj_node

    def _create_version_cache(self, projects = None):
        """ Creates a cache containing version of all packages. """
        # This helps us avoid doing many small SQL queries, which is really
        # slow.
        #
        # The main difference is that we do one SQL query + many hash accesses,
        # vs 2*(total number of packages in the database) SQL queries. On a
        # test run, the difference results in ~1min15s vs ~5s. That's a 15x
        # time win.
        self._version_cache = {}

        if not projects:
            self._cursor.execute('''SELECT name FROM %(Project)s;''' % SQL_TABLES)
            projects = [ row['name'] for row in self._cursor ]

        for project in projects:
            self._version_cache[project] = {}

        self._cursor.execute('''SELECT A.name, A.version, B.name AS project
                               FROM %(SrcPackage)s AS A, %(Project)s AS B
                               WHERE A.project = B.id;''' % SQL_TABLES)

        for row in self._cursor:
            self._version_cache[row['project']][row['name']] = row['version']

    def _write_xml_for_project(self, project):
        """ Writes the XML file for a project.

            Note that we don't touch the old file if the result is the same.
            This can be useful for browser cache.

        """
        node = self._get_project_node(project)

        filename = os.path.join(self.dest_dir, project + '.xml')
        tmpfilename = filename + '.tmp'

        tree = ET.ElementTree(node)

        try:
            tree.write(tmpfilename)

            # keep the old file if there's no change (useful when downloaded
            # from the web to not re-download again the file)
            if os.path.exists(filename):
                if filecmp.cmp(filename, tmpfilename, shallow = False):
                    self._debug_print('XML for %s did not change' % project)
                    os.unlink(tmpfilename)
                    return

            os.rename(tmpfilename, filename)
        except Exception, e:
            if os.path.exists(tmpfilename):
                os.unlink(tmpfilename)
            raise e

    def run(self):
        """ Creates the XML files for all projects. """
        util.safe_mkdir_p(self.dest_dir)

        self._cursor.execute('''SELECT name FROM %(Project)s;''' % SQL_TABLES)
        projects = [ row['name'] for row in self._cursor ]

        self._create_version_cache(projects)

        for project in projects:
            self._debug_print('Writing XML for %s' % project)
            self._write_xml_for_project(project)


#######################################################################


def main(args):
    import sqlite3

    if len(args) != 3:
        print >> sys.stderr, 'Usage: %s dbfile project' % args[0]
        sys.exit(1)

    filename = args[1]
    project = args[2]

    if not os.path.exists(filename):
        print >> sys.stderr, '%s does not exist.' % filename
        sys.exit(1)

    try:
        db = sqlite3.connect(filename)
    except sqlite3.OperationalError, e:
        print >> sys.stderr, 'Error while opening %s: %s' % (filename, e)
        sys.exit(1)

    db.row_factory = sqlite3.Row
    db.text_factory = sqlite3.OptimizedUnicode
    cursor = db.cursor()

    info = InfoXml('.', cursor, True)

    try:
        info._create_version_cache()
        node = info._get_project_node(project)
    except InfoXmlException, e:
        print >> sys.stderr, 'Error while creating the XML for %s: %s' % (project, e)
        sys.exit(1)

    tree = ET.ElementTree(node)
    try:
        print ET.tostring(tree, pretty_print = True)
    except TypeError:
        # pretty_print only works with lxml
        tree.write(sys.stdout)

    cursor.close()
    db.close()


if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
    except IOError, e:
        if e.errno == errno.EPIPE:
            pass
