#!/usr/bin/env python
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

import cStringIO
import gzip
import re
import sqlite3

import cgi

try:
    from lxml import etree as ET
except ImportError:
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

from libdissector import config
from libdissector import libdbcore
from libdissector import libinfoxml

if config.cgitb:
    import cgitb; cgitb.enable()

# Database containing reservations. Can be created if needed.
RESERVATION_DBFILE = os.path.join(config.datadir, 'reservations.db')

# Protocol version is X.Y.
#  + when breaking compatibility in the XML, then increase X and reset Y to 0.
#  + when adding a new feature in a compatible way, increase Y.
PROTOCOL_MAJOR = 0
PROTOCOL_MINOR = 1

#######################################################################


class ApiOutput:

    def __init__(self):
        self.root = ET.Element('api')
        self.root.set('version', '%d.%d' % (PROTOCOL_MAJOR, PROTOCOL_MINOR))
        self.result = None
        self.compress = False

    def set_compress(self, compress):
        can_compress = False
        if os.environ.has_key('HTTP_ACCEPT_ENCODING'):
            accepted = os.environ['HTTP_ACCEPT_ENCODING'].split(',')
            accepted = [ item.strip() for item in accepted ]
            can_compress = 'gzip' in accepted

        self.compress = can_compress and compress

    def set_result(self, ok = True, detail = ''):
        if self.result is None:
            self.result = ET.SubElement(self.root, 'result')

        if ok:
            self.result.set('ok', 'true')
        else:
            self.result.set('ok', 'false')
        if detail:
            self.result.text = detail

    def add_node(self, node):
        self.root.append(node)

    def _output(self):
        print 'Content-type: text/xml'
        print

        ET.ElementTree(self.root).write(sys.stdout)

    def _output_compressed(self):
        # Thanks to http://www.xhaus.com/alan/python/httpcomp.html
        zbuf = cStringIO.StringIO()
        zfile = gzip.GzipFile(mode = 'wb', fileobj = zbuf)
        ET.ElementTree(self.root).write(zfile)
        zfile.close()
        compressed = zbuf.getvalue()

        print 'Content-type: text/xml'
        print 'Content-Encoding: gzip'
        print 'Content-Length: %d' % len(compressed)
        print

        sys.stdout.write(compressed)

    def output(self):
        if self.compress and False:
            self._output_compressed()
        else:
            self._output()


#######################################################################


class ApiGeneric:

    def __init__(self, output, protocol, args, form):
        self.output = output
        self.protocol = protocol
        self.args = args
        self.form = form
        self.future = form.has_key('future')
        self.db = libdbcore.ObsDb(self.future)

    def __del__(self):
        del self.db

    def _find_project_for_package(self, package, projects):
        '''
            Find the first project in the list of projects containing the
            specified package.
        '''
        query = 'SELECT COUNT(*) FROM %s, %s WHERE %s.name = ? AND %s.name = ? AND %s.project = %s.id;' % (libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_srcpackage, libdbcore.table_project)
        for project in projects:
            self.db.cursor.execute(query, (project, package))
            row = self.db.cursor.fetchone()
            if row[0] != 0:
                return project

        return None

    def _package_exists(self, project, package):
        '''
            Checks a package exists.
        '''
        query = 'SELECT version FROM %s, %s WHERE %s.name = ? AND %s.name = ? AND %s.project = %s.id;' % (libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_srcpackage, libdbcore.table_project)
        self.db.cursor.execute(query, (project, package))
        row = self.db.cursor.fetchone()
        return row is not None

    def _find_devel_package(self, project, package):
        '''
            Find the end devel package of a specified package.
        '''
        query = 'SELECT devel_project, devel_package FROM %s, %s WHERE %s.name = ? AND %s.name = ? AND %s.project = %s.id;' % (libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_project, libdbcore.table_srcpackage, libdbcore.table_srcpackage, libdbcore.table_project)
        while True:
            self.db.cursor.execute(query, (project, package))
            row = self.db.cursor.fetchone()
            if not row:
                return (project, package)

            devel_project = row['devel_project']
            devel_package = row['devel_package']

            if not devel_project:
                return (project, package)

            project = devel_project
            package = devel_package or package

        return (project, package)

    def _parse_standard_args(self, paths):
        '''
            Parse a path that is in the form of either of the following:
              + <project>
              + <project>/<package>
              + <package>?project=aa&project=...
        '''
        if len(paths) == 1 and not paths[0]:
            return (True, None, None)
        elif len(paths) == 1 or (len(paths) == 2 and not paths[1]):
            projects = self.form.getlist('project')
            if projects:
                package = paths[0]
                project = self._find_project_for_package(package, projects)
                if project:
                    return (True, project, package)
                else:
                    self.output.set_result(False, 'Non existing package: %s' % package)
                    return (False, None, None)
            else:
                project = paths[0]
                return (True, project, None)
        else:
            project = paths[0]
            package = paths[1]
            return (True, project, package)

    def run(self):
        pass


#######################################################################


class ApiInfo(ApiGeneric):
    '''
        api/info
        api/info/<project>
        api/info/<project>/<package>

        api/info/<package>?project=aa&project=...
    '''

    def _list_projects(self):
        self.db.cursor.execute('''SELECT name FROM %s ORDER BY name;''' % libdbcore.table_project)
        for row in self.db.cursor:
            node = ET.Element('project')
            node.set('name', row['name'])
            self.output.add_node(node)

    def _list_project(self, project):
        info = libinfoxml.InfoXml(self.db, self.future)
        try:
            node = info.get_project_node(project)
            self.output.add_node(node)
            output.set_compress(True)
        except libinfoxml.InfoXmlException, e:
            self.output.set_result(False, e.msg)

    def _list_package(self, project, package):
        info = libinfoxml.InfoXml(self.db, self.future)
        try:
            prj_node = info.get_project_node(project, False)
            pkg_node = info.get_package_node(project, package)
            prj_node.append(pkg_node)
            self.output.add_node(prj_node)
        except libinfoxml.InfoXmlException, e:
            self.output.set_result(False, e.msg)

    def run(self):
        paths = self.args.split('/')
        if len(paths) > 2:
            self.output.set_result(False, 'Too many arguments to "info" command')
            return

        (ok, project, package) = self._parse_standard_args(paths)
        if not ok:
            return

        if not project:
            self._list_projects()
        elif not package:
            self._list_project(project)
        else:
            self._list_package(project, package)


#######################################################################


class ApiReserve(ApiGeneric):
    '''
        api/reserve (list)
        api/reserve/<project> (list)
        api/reserve/<project>/<package> (list)
        api/reserve/<project>/<package>?cmd=list
        api/reserve/<project>/<package>?cmd=set&user=<user>
        api/reserve/<project>/<package>?cmd=unset&user=<user>

        api/reserve?project=aa&project=... (list)
        api/reserve/<package>?project=aa&project=...&cmd=...

        For all package-related commands, ignoredevel=1 or ignoredevel=true can
        be used to not make the reservation work on the development package of
        the package, but to force the commands on this package in this project.
    '''

    def __init__(self, output, protocol, args, form):
        ApiGeneric.__init__(self, output, protocol, args, form)

        self.dbreserve = None
        self.cursor = None

    def __del__(self):
        if self.cursor:
            self.cursor.close()
        if self.dbreserve:
            self.dbreserve.close()

    def _get_reservation_database(self):
        create = True
        if os.path.exists(RESERVATION_DBFILE):
            create = False
            if not os.access(RESERVATION_DBFILE, os.W_OK):
                self.output.set_result(False, 'Read-only database')
                return False
        else:
            dirname = os.path.dirname(RESERVATION_DBFILE)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

        self.dbreserve = sqlite3.connect(RESERVATION_DBFILE)
        if not self.dbreserve:
            self.output.set_result(False, 'No access to database')
            return False

        self.dbreserve.row_factory = sqlite3.Row
        self.cursor = self.dbreserve.cursor()

        if create:
            self.cursor.execute('''CREATE TABLE reserve (date TEXT, user TEXT, package TEXT, project TEXT);''')

        return True

    def _prune_old_reservations(self):
        self.cursor.execute('''DELETE FROM reserve WHERE datetime(date, '+36 hours') < datetime('now');''')

    def _check_no_abuse(self):
        # just don't do anything if we have more than 200 reservations (we're
        # getting spammed)
        self.cursor.execute('''SELECT COUNT(*) FROM reserve;''')

        row = self.cursor.fetchone()
        if not row or row[0] > 200:
            self.output.set_result(False, 'Database currently unavailable')
            return False

        return True

    def _create_node(self, project, package, user):
        node = ET.Element('reservation')
        node.set('project', project)
        node.set('package', package)
        if user:
            node.set('user', user)
        return node

    def _list_all(self, projects = None):
        if projects:
            projects_where = ' OR '.join(['project = ?' for project in projects])
            self.cursor.execute('''SELECT * FROM reserve WHERE %s ORDER BY project, package;''' % projects_where, projects)
        else:
            self.cursor.execute('''SELECT * FROM reserve ORDER BY project, package;''')

        for row in self.cursor:
            node = self._create_node(row['project'], row['package'], row['user'])
            self.output.add_node(node)

    def _run_project_package(self, project, package):
        ignore_devel = False
        if form.has_key('ignoredevel'):
            if form.getfirst('ignoredevel').lower() in [ '1', 'true' ]:
                ignore_devel = True

        if not ignore_devel:
            (project, package) = self._find_devel_package(project, package)

        if not self._package_exists(project, package):
            self.output.set_result(False, 'Non existing package: %s/%s' % (project, package))
            return

        if form.has_key('cmd'):
            cmd = form.getfirst('cmd')
        else:
            cmd = 'list'

        if cmd not in [ 'list', 'set', 'unset' ]:
            self.output.set_result(False, 'Unknown "reserve" subcommand: %s' % cmd)
            return

        if form.has_key('user'):
            user = form.getfirst('user')
        else:
            user = None

        if cmd in [ 'set', 'unset' ] and not user:
            self.output.set_result(False, 'No user specified')
            return

        self.cursor.execute('''SELECT user FROM reserve WHERE project = ? AND package = ?;''', (project, package,))
        row = self.cursor.fetchone()
        if row:
            reserved_by = row['user']
        else:
            reserved_by = None

        if cmd == 'list':
            # we just want the reservation node
            pass
        elif cmd == 'set':
            if reserved_by:
                self.output.set_result(False, 'Package already reserved by %s' % reserved_by)
            else:
                self.cursor.execute('''INSERT INTO reserve VALUES (datetime('now'), ?, ?, ?);''', (user, package, project))
                reserved_by = user
        elif cmd == 'unset':
            if not reserved_by:
                self.output.set_result(False, 'Package not reserved')
            elif reserved_by != user:
                self.output.set_result(False, 'Package reserved by %s' % reserved_by)
            else:
                self.cursor.execute('''DELETE FROM reserve WHERE user = ? AND project = ? AND package = ?''', (user, project, package))
                reserved_by = None

        self.dbreserve.commit()
        node = self._create_node(project, package, reserved_by)
        self.output.add_node(node)

    def run(self):
        if not self._get_reservation_database():
            return

        # automatically remove old reservations
        self._prune_old_reservations()

        if not self._check_no_abuse():
            return

        paths = self.args.split('/')
        if len(paths) > 2:
            self.output.set_result(False, 'Too many arguments to "reserve" command')
            return

        (ok, project, package) = self._parse_standard_args(paths)
        if not ok:
            return

        if not project:
            projects = self.form.getlist('project')
            self._list_all(projects)
        elif not package:
            self._list_all((project,))
        else:
            self._run_project_package(project, package)


#######################################################################


def handle_args(output, path, form):
    paths = path.split('/', 1)
    if len(paths) == 1:
        command = paths[0]
        args = ''
    else:
        (command, args) = paths

    if form.has_key('version'):
        client_version = form.getfirst('version')
    else:
        client_version = '0.1'

    client_version_items = client_version.split('.')
    for item in client_version_items:
        try:
            int(item)
        except ValueError:
            output.set_result(False, 'Invalid protocol version')
            return
    protocol = int(client_version_items[0])
    if int(client_version_items[0]) > PROTOCOL_MAJOR:
        output.set_result(False, 'Protocol version requested is unknown')
        return

    # assume the result is successful at first :-)
    output.set_result()

    if not command:
        output.set_result(False, 'No command specified')
    elif command == 'info':
        try:
            info = ApiInfo(output, protocol, args, form)
            info.run()
        except libdbcore.ObsDbException, e:
            output.set_result(False, str(e))
    elif command == 'reserve':
        try:
            reserve = ApiReserve(output, protocol, args, form)
            reserve.run()
        except libdbcore.ObsDbException, e:
            output.set_result(False, str(e))
    else:
        output.set_result(False, 'Unknown command "%s"' % command)


#######################################################################

if os.environ.has_key('PATH_INFO'):
    path = os.environ['PATH_INFO']
    # remove consecutive slashes
    path = re.sub('//+', '/', path)
    # remove first slash
    path = path[1:]
else:
    path = ''

output = ApiOutput()

form = cgi.FieldStorage()
handle_args(output, path, form)

output.output()
