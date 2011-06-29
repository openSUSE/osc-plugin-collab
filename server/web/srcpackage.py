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
srcpackage_var = get_arg(form, 'srcpackage')

print_html_header()

if srcpackage_var:
    title = 'Information about source package "%s"' % escape(srcpackage_var)
else:
    title = 'Query openSUSE source packages'
print_header(title)

db = PackageDB()

if srcpackage_var:
    srcpackage = SrcPackage.get_from_db(srcpackage_var, db.cursor)
    if not srcpackage or srcpackage.id == -1:
        print '<h1>No source package named "%s"</h1>' % escape(srcpackage_var)
    else:
        print '<h1>Information about %s</h1>' % escape(srcpackage_var)
        print '<pre>'
        #FIXME: print escape(str(srcpackage))
        print str(srcpackage)
        print '</pre>'
else:
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, ('GNOME:Factory',))
    row = db.cursor.fetchone()
    if row:
        project_id = row['id']
    else:
        project_id = -1

    db.cursor.execute('''SELECT COUNT(*) FROM %s WHERE project = ?;''' % SrcPackage.sql_table, (project_id,))
    row = db.cursor.fetchone()
    print '<h1>%s source packages</h1>' % escape(str(row[0]))
    db.cursor.execute('''SELECT name FROM %s WHERE project = ? ORDER BY name;''' % SrcPackage.sql_table, (project_id,))
    for row in db.cursor:
        print '<a href="%s?srcpackage=%s">%s</a><br />' % (escape(os.environ['SCRIPT_NAME']), escape(row['name']), escape(row['name']))

print_foot()
