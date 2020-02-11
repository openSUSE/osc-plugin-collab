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

import cgi
from cgi import escape

from libdissector import buildservice
from libdissector import config
from libdissector import libdbcore
from libdissector import libdbhtml
from libdissector import libhttp

if config.cgitb:
    import cgitb; cgitb.enable()


#######################################################################


def get_page_title(project, srcpackage, tag):
    if project and srcpackage and tag:
        return 'Patches tagged %s for package %s in project %s' % (escape(tag), escape(srcpackage), escape(project))
    elif project and srcpackage:
        return 'Patches for package %s in project %s' % (escape(srcpackage), escape(project))
    elif project and tag:
        return 'Patches tagged %s in project %s' % (escape(tag), escape(project))
    elif project:
        return 'Patches in project %s' % (escape(project))
    else:
        return 'Patches'


#######################################################################


def get_package(db, project, srcpackage, tag):
    db.cursor.execute(libdbcore.pkg_query, (project, srcpackage))
    row = db.cursor.fetchone()
    
    if not row:
        return 'Error: package %s does not exist in project %s' % (escape(project), escape(srcpackage))

    if row['is_obs_link'] and row['srcmd5']:
        rev = row['srcmd5']
    else:
        rev = None

    if tag:
        db.cursor.execute('''SELECT * FROM %s WHERE srcpackage = ? AND tag = ? ORDER BY nb_in_pack;''' % libdbcore.table_patch, (row['id'], tag))
    else:
        db.cursor.execute('''SELECT * FROM %s WHERE srcpackage = ? ORDER BY nb_in_pack;''' % libdbcore.table_patch, (row['id'],))

    s = ''
    s += '<pre>\n'

    count = 0
    for row in db.cursor:
        count += 1
        url = buildservice.get_source_url(project, srcpackage, row['filename'], rev, True)
        s += '%s: <a href=\"%s\">%s</a>' % (row['nb_in_pack'], url, row['filename'])
        if row['disabled'] != 0:
            s += ' (not applied)'
        s += '\n'

    s += '</pre>\n'

    if tag:
        s = '<h2>%d patches tagged %s for package %s in project %s</h2>\n' % (count, escape(tag), escape(srcpackage), escape(project)) + s
    else:
        s = '<h2>%d patches for package %s in project %s</h2>\n' % (count, escape(srcpackage), escape(project)) + s

    return s


#######################################################################


def get_project(db, project, tag):
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % libdbcore.table_project, (project,))
    row = db.cursor.fetchone()
    
    if not row:
        return 'Error: project %s does not exist' % escape(project)

    project_id = row['id']

    if tag == 'None':
        tag_sql = ''
    else:
        tag_sql = tag

    if tag:
        db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? AND tag = ?;''' % (libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_srcpackage) , (project_id, tag_sql))
    else:
        db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ?;''' % (libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_srcpackage) , (project_id,))
    
    row = db.cursor.fetchone()
    count = escape(str(row[0]))

    s = ''

    if tag:
        s += '<h2>%s patches tagged %s in project %s</h2>\n<p>\n' % (count, escape(tag), escape(project))

        db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? AND tag = ? GROUP BY srcpackage ORDER BY c DESC;''' % (libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_srcpackage), (project_id, tag_sql))
        for row in db.cursor:
            s += '<a href="%s?project=%s&amp;srcpackage=%s&amp;tag=%s">%s</a>: %s<br />\n' % (escape(os.environ['SCRIPT_NAME']), escape(project), escape(row['n']), escape(tag or ''), escape(row['n']), escape(str(row['c'])))

        s += '</p>\n'

    else:
        s += '<h2>%s patches in project %s</h2>\n' % (count, escape(project))

        s += '<h3>Order by tag</h3>\n<p>\n'

        db.cursor.execute('''SELECT COUNT(*) AS c, tag FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY tag ORDER BY c DESC;''' % (libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_srcpackage), (project_id,))

        for row in db.cursor:
            if row['tag'] == '':
                row_tag = 'None'
            else:
                row_tag = escape(row['tag'])

            s += '<a href="%s?project=%s&amp;tag=%s">%s</a>: %s<br />\n' % (escape(os.environ['SCRIPT_NAME']), escape(project), row_tag, row_tag, escape(str(row['c'])))

        s += '</p>\n<h3>Order by source package</h3>\n<p>\n'

        db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY srcpackage ORDER BY c DESC;''' % (libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_patch, libdbcore.table_srcpackage, libdbcore.table_srcpackage), (project_id,))
        for row in db.cursor:
            s += '<a href="%s?project=%s&amp;srcpackage=%s">%s</a>: %s<br />\n' % (escape(os.environ['SCRIPT_NAME']), escape(project), escape(row['n']), escape(row['n']), escape(str(row['c'])))

        s += '</p>\n'

    return s


#######################################################################


def get_page_content(db, project, srcpackage, tag):
    if not project:
        return 'Error: no project specified'

    if srcpackage:
        return get_package(db, project, srcpackage, tag)
    else:
        return get_project(db, project, tag)


#######################################################################


form = cgi.FieldStorage()

libhttp.print_html_header()

project = libhttp.get_project(form)
srcpackage = libhttp.get_srcpackage(form)
tag = libhttp.get_arg(form, 'tag')

db = libdbcore.ObsDb()

title = get_page_title(project, srcpackage, tag)
content = get_page_content(db, project, srcpackage, tag)

libhttp.print_header(title)

if not srcpackage:
    print(libdbhtml.get_project_selector(current_project = project, db = db))
print(content)

libhttp.print_foot()
