#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

from libdb import *
from libhttp import *
import cgi
from cgi import escape
import cgitb; cgitb.enable()
import os
import sys

print_text_header()

form = cgi.FieldStorage()

if form.has_key('future'):
    use_future = True
else:
    use_future = False

db = PackageDB(use_future)

project_var = get_arg(form, 'project', 'GNOME:Factory')

if not form.has_key('mode'):
    mode = 'delta'
else:
    mode = form.getfirst('mode')
    if mode != 'error' and mode != 'delta':
        mode = 'delta'

db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (project_var,))
row = db.cursor.fetchone()
if row:
    project_id = row['id']
else:
    project_id = -1

if mode == 'delta':
    db.cursor.execute('''SELECT name FROM %s WHERE project = ? AND obs_link_has_delta = 1 ORDER BY name;''' % SrcPackage.sql_table, (project_id,))

    for row in db.cursor:
        print row['name']
elif mode == 'error':
    db.cursor.execute('''SELECT name, obs_error, obs_error_details FROM %s WHERE project = ? AND obs_error != '' ORDER BY name;''' % SrcPackage.sql_table, (project_id,))

    for row in db.cursor:
        print row['name'] + ';' + row['obs_error'] + ';' + row['obs_error_details']
