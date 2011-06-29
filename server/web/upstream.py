#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

from libdb import *
from libhttp import *
import cgi
from cgi import escape
import cgitb; cgitb.enable()
import os
import sys

form = cgi.FieldStorage()

if form.has_key('future'):
    use_future = True
else:
    use_future = False

project_var = get_arg(form, 'project', 'GNOME:Factory')
package_var = get_arg(form, 'package')

print_text_header()

db = PackageDB(use_future)

db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (project_var,))
row = db.cursor.fetchone()
if row:
    project_id = row['id']
else:
    project_id = -1

if package_var:
    db.cursor.execute('''SELECT name, upstream_version, upstream_url FROM %s WHERE project = ? AND name = ?;''' % SrcPackage.sql_table, (project_id, package_var))
else:
    db.cursor.execute('''SELECT name, upstream_version, upstream_url FROM %s WHERE project = ? ORDER BY name;''' % SrcPackage.sql_table, (project_id,))

for row in db.cursor:

    name = row['name']
    upstream_version = row['upstream_version']
    upstream_url = row['upstream_url']

    print '%s;%s;%s;' % (name, upstream_version, upstream_url)
