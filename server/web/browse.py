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

import cgi
from cgi import escape

import sqlite3

from libdissector import config
from libdissector import buildservice
from libdissector import libhttp

if config.cgitb:
    import cgitb; cgitb.enable()

DATABASE = os.path.join(config.datadir, 'packagelist.db')

form = cgi.FieldStorage()
if form.has_key('project'):
    project_var = form.getfirst('project')
else:
    project_var = None

if form.has_key('package'):
    package_var = form.getfirst('package')
else:
    package_var = None

libhttp.print_html_header()

if project_var and package_var:
    title = 'Browse %s in %s' % (escape(package_var), escape(project_var))
elif project_var and not package_var:
    title = 'Browse Packages in %s' % escape(project_var)
elif package_var:
    title = 'Find Package %s in openSUSE' % escape(package_var)
else:
    title = 'Browse openSUSE Source'
libhttp.print_header(title)

if not os.path.exists(DATABASE):
    print '<h2>Error: database currently unavailable</h2>'
    print_foot()
    sys.exit(0)

db = sqlite3.connect(DATABASE)
if not db:
    print '<h2>Error: database currently unavailable</h2>'
    print_foot()
    sys.exit(0)

db.row_factory = sqlite3.Row
cursor = db.cursor()

def link_to_self(label):
    return '<a href="%s">%s</a>' % (escape(os.environ['SCRIPT_NAME']), escape(label))

def link_to_project(project):
    project_esc = escape(project)
    return '<a href="%s?project=%s">%s</a>' % (escape(os.environ['SCRIPT_NAME']), project_esc, project_esc)

def link_to_project_package(project, package, show_project = False):
    project_esc = escape(project)
    package_esc = escape(package)
    if show_project:
        label = project_esc
    else:
        label = package_esc
    return '<a href="%s?project=%s&amp;package=%s">%s</a>' % (escape(os.environ['SCRIPT_NAME']), project_esc, package_esc, label)

def link_to_package(package):
    package_esc = escape(package)
    return '<a href="%s?package=%s">%s</a>' % (escape(os.environ['SCRIPT_NAME']), package_esc, package_esc)

if project_var and package_var:
    project_esc = escape(project_var)
    package_esc = escape(package_var)
    print '<h2>Content of %s (%s)</h2>' % (link_to_package(package_var), link_to_project(project_var))
    try:
        (files, srcmd5) = buildservice.fetch_package_content(project_var, package_var)
        print '<ul>'
        for file in files:
            print '<li>%s</li>' % buildservice.get_source_link(project_var, package_var, file, srcmd5, do_escape = True, text = file)
        print '</ul>'
    except buildservice.BuildServiceException, e:
        print escape('%s' % e)

elif project_var and not package_var:
    project_esc = escape(project_var)

    cursor.execute('''SELECT * FROM %s WHERE project = ?;''' % 'projects', (project_var,))
    row = cursor.fetchone()
    if not row:
        print '<h2>Error: project "%s" is unknown</h2>' % (project_esc,)
    else:
        print '<h2>Packages in %s <small style="font-size: smaller">(%s)</small></h2>' % (project_esc, link_to_self('see all projects'))
        cursor.execute('''SELECT * FROM %s WHERE project_id = ? ORDER BY package;''' % 'packages', (row['id'],))
        print '<ul>'
        for row in cursor:
            print '<li>%s</li>' % link_to_project_package(project_var, row['package'])
        print '</ul>'

elif package_var:
    package_esc = escape(package_var)

    cursor.execute('''SELECT project FROM %s, %s WHERE package = ? AND %s.project_id = %s.id ORDER BY project;''' % ('packages', 'projects', 'packages', 'projects'), (package_var,))
    rows = cursor.fetchall()
    if len(rows) == 0:
        print '<h2>Error: package "%s" is unknown</h2>' % (package_esc,)
    else:
        print '<h2>Projects containing %s <small style="font-size: smaller">(%s)</small></h2>' % (package_esc, link_to_self('see all projects'))
        print '<ul>'
        for row in rows:
            print '<li>%s</li>' % link_to_project_package(row['project'], package_var, show_project = True)
        print '</ul>'

else:
    print '<h2>openSUSE projects</h2>'
    cursor.execute('''SELECT * FROM %s ORDER BY project;''' % 'projects')
    print '<ul>'
    for row in cursor:
        print '<li>%s</li>' % link_to_project(row['project'])
    print '</ul>'

cursor.close()
db.close()
libhttp.print_foot()
