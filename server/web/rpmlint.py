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

type_var = get_arg(form, 'type')
srcpackage_var = get_arg(form, 'srcpackage')
project_var = get_arg(form, 'project', 'GNOME:Factory')

print_html_header()

if srcpackage_var:
    title = 'Information about rpmlint errors in %s' % escape(srcpackage_var)
elif type_var:
    title = 'Information about rpmlint errors of type "%s"' % escape(type_var)
else:
    title = 'Query openSUSE rpmlint errors'
print_header(title)

db = PackageDB()

if srcpackage_var:
    srcpackage = SrcPackage.get_from_db(srcpackage_var, db.cursor, project = project_var)
    if not srcpackage or srcpackage.id == -1:
        print '<h1>No source package named "%s"</h1>' % escape(srcpackage_var)
    else:
        db.cursor.execute('''SELECT COUNT(*) FROM %s WHERE srcpackage = ?;''' % RpmlintReport.sql_table, (srcpackage.id,))
        row = db.cursor.fetchone()

        print '<h1>%s rpmlint errors in "%s"</h1>' % (escape(str(row[0])), escape(srcpackage_var))

        db.cursor.execute('''SELECT COUNT(*) AS c, type FROM %s WHERE srcpackage = ? GROUP BY type ORDER BY c DESC;''' % RpmlintReport.sql_table, (srcpackage.id,))
        for row in db.cursor:
            type = escape(row['type'])
            print '<a href="%s?type=%s">%s</a>: %s<br />' % (escape(os.environ['SCRIPT_NAME']), type, type, escape(str(row['c'])))

elif type_var:
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (project_var,))
    row = db.cursor.fetchone()
    if row:
        project_id = row['id']
    else:
        project_id = -1

    db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE type = ? AND %s.srcpackage = %s.id AND %s.project = ?;''' % (RpmlintReport.sql_table, SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (type_var, project_id))
    row = db.cursor.fetchone()
    print '<h1>%s rpmlint errors of type "%s"</h1>' % (escape(str(row[0])), type_var)
    db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND type = ? AND %s.project = ? GROUP BY srcpackage ORDER BY c DESC;''' % (SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (type_var, project_id))
    for row in db.cursor:
        srcpackage = escape(row['n'])
        print '<a href="%s?srcpackage=%s">%s</a>: %s<br />' % (escape(os.environ['SCRIPT_NAME']), srcpackage, srcpackage, escape(str(row['c'])))

else:
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (project_var,))
    row = db.cursor.fetchone()
    if row:
        project_id = row['id']
    else:
        project_id = -1

    db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ?;''' % (RpmlintReport.sql_table, SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    row = db.cursor.fetchone()
    print '<h1>%s rpmlint errors</h1>' % escape(str(row[0]))

    print '<h2>Order by type</h2>'
    print '<p>'
    db.cursor.execute('''SELECT COUNT(*) AS c, type FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY type ORDER BY c DESC;''' % (RpmlintReport.sql_table, SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    for row in db.cursor:
        type = escape(row['type'])
        print '<a href="%s?type=%s">%s</a>: %s<br />' % (escape(os.environ['SCRIPT_NAME']), type, type, escape(str(row['c'])))
    print '</p>'

    print '<h2>Order by source package</h2>'
    print '<p>'
    db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY srcpackage ORDER BY c DESC;''' % (SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, RpmlintReport.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    for row in db.cursor:
        srcpackage = escape(row['n'])
        print '<a href="%s?srcpackage=%s">%s</a>: %s<br />' % (escape(os.environ['SCRIPT_NAME']), srcpackage, srcpackage, escape(str(row['c'])))
    print '</p>'

print_foot()
