#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

from libdb import *
from libhttp import *
import cgi
from cgi import escape
import cgitb; cgitb.enable()
import os
import sys

def compare_versions_a_gt_b (a, b):
    split_a = a.split('.')
    split_b = b.split('.')
    if len(split_a) != len(split_b):
        return a > b
    for i in range(len(split_a)):
        try:
            int_a = int(split_a[i])
            int_b = int(split_b[i])
            if int_a > int_b:
                return True
            if int_b > int_a:
                return False
        except ValueError:
            if split_a[i] > split_b[i]:
                return True
            if split_b[i] > split_a[i]:
                return False

    return False

form = cgi.FieldStorage()
if form.has_key('future'):
    use_future = True
else:
    use_future = False

if form.has_key('format') and form.getfirst('format') == 'csv':
    use_csv = True
else:
    use_csv = False

project_var = get_arg(form, 'project', 'GNOME:Factory')
package_var = get_arg(form, 'package')

if use_csv:
    print_text_header()
else:
    print_html_header()
    print_header('Versions of packages in the Build Service for project %s' % escape(project_var))

db = PackageDB(use_future)

project = Project(db.cursor, project_var)
if project.parent:
    parent = Project(db.cursor, project.parent)
else:
    parent = None

use_upstream = not project.ignore_upstream

if not use_csv:
    print_project_selector(db.cursor, project_var)
    if not package_var:
        db.cursor.execute('''SELECT COUNT(*) FROM %s WHERE project = ?;''' % SrcPackage.sql_table, (project.id,))
        row = db.cursor.fetchone()
        print '<h1>%s source packages in %s</h1>' % (escape(str(row[0])), escape(project.name))
    print '<table>'

    header = '<tr><th>Package</th>'
    if parent:
        header += '<th>%s</th>' % escape(parent.name)
    header += '<th>%s</th>' % escape(project.name)
    if use_upstream:
        header += '<th>Upstream</th>'
    header += '</tr>'

    print header
else:
    if parent:
        print '#meta: parent=%s' % parent.name
    if not use_upstream:
        print '#meta: ignore-upstream'

if package_var:
    db.cursor.execute('''SELECT * FROM %s WHERE project = ? AND name = ?;''' % (SrcPackage.sql_table,), (project.id, package_var))
else:
    db.cursor.execute('''SELECT * FROM %s WHERE project = ? ORDER BY name;''' % (SrcPackage.sql_table,), (project.id,))

helper_cursor = db.db.cursor()
for row in db.cursor:

    name = row['name']
    version = row['version']
    upstream_version = row['upstream_version']
    upstream_url = row['upstream_url']
    has_delta = row['obs_link_has_delta'] != 0

    if parent:
        helper_cursor.execute('''SELECT version FROM %s WHERE project = ? and name = ?;''' % SrcPackage.sql_table, (parent.id, name))
        helper_row = helper_cursor.fetchone()
        if helper_row:
            parent_version = helper_row['version']
        else:
            parent_version = '--'
    else:
        parent_version = ''

    color = None
    if parent and parent_version != '--' and (has_delta or not parent_version or compare_versions_a_gt_b(version, parent_version)):
        color = 'blue'

    if use_upstream:
        if upstream_version != '' and upstream_version != '--':
            if compare_versions_a_gt_b(upstream_version, parent_version) and compare_versions_a_gt_b(upstream_version, version):
                color = 'red'
        elif color is None and upstream_version != '--':
            color = 'yellow'

    if color in ['blue']:
        text_color = 'color: white;'
    else:
        text_color = ''

    if color:
        style = ' style="background: %s; %s"' % (color, text_color)
    else:
        style = ''

    if use_csv:
        print '%s;%s;%s;%s;' % (name, parent_version, version, upstream_version)
    else:
        row = '<tr><td%s>%s</td>' % (style, escape(name))
        if parent:
            row += '<td>%s</td>' % escape(parent_version)
        row += '<td>%s</td>' % escape(version)
        if use_upstream:
            if upstream_url and upstream_url != '':
                version_cell = '<a href="' + escape(upstream_url) + '">' + escape(upstream_version) + '</a>'
            else:
                version_cell = escape(upstream_version)
            row += '<td>%s</td>' % version_cell
        row += '</tr>'

        print row

if not use_csv:
    print '</table>'

    print '<table>'
    print '<tr><th>Legend</th></tr>'
    print '<tr><td>Package is perfect!</td></tr>'
    print '<tr><td style="background: blue; color: white;">Has delta with parent</td></tr>'
    print '<tr><td style="background: yellow;">No upstream data</td></tr>'
    print '<tr><td style="background: red;">Upstream has a new version</td></tr>'
    print '</table>'

    print_foot()
