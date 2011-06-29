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
tag_var = get_arg(form, 'tag')

print_html_header()

if srcpackage_var:
    if tag_var:
        title = 'Information about patches tagged "%s" in source package "%s"' % (escape(tag_var), escape(srcpackage_var))
    else:
        title = 'Information about patches in source package "%s"' % escape(srcpackage_var)
elif tag_var:
    title = 'Information about patches tagged "%s"' % escape(tag_var)
else:
    title = 'Query openSUSE patches'
print_header(title)

db = PackageDB()

if srcpackage_var:
    srcpackage = SrcPackage.get_from_db(srcpackage_var, db.cursor)
    if not srcpackage or srcpackage.id == -1:
        print '<h1>No source package named "%s"</h1>' % escape(srcpackage_var)
    else:
        if tag_var:
            print '<h1>Patches tagged "%s" in "%s"</h1>' % (escape(tag_var), escape(srcpackage_var))
        else:
            print '<h1>Patches in "%s"</h1>' % escape(srcpackage_var)

        if srcpackage.is_obs_link and srcpackage.srcmd5 != '':
            api_source_args = '?rev=' + srcpackage.srcmd5
        else:
            api_source_args = ''

        print '<pre>'
        for patch in srcpackage.patches:
            if not tag_var or tag_var == patch.tag or (tag_var == 'None' and patch.tag == ''):
                ret = "%s: <a href=\"https://api.opensuse.org/public/source/GNOME:Factory/%s/%s%s\">%s</a>" % (patch.number, srcpackage.name, patch.filename, api_source_args, patch.filename)
                if patch.disabled != 0:
                    ret = ret + " (not applied)"
                print ret
        print '</pre>'

elif tag_var:
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, ('GNOME:Factory',))
    row = db.cursor.fetchone()
    if row:
        project_id = row['id']
    else:
        project_id = -1

    if tag_var == 'None':
        tag_sql = ''
    else:
        tag_sql = tag_var
    db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE tag = ? AND %s.srcpackage = %s.id AND %s.project = ?;''' % (Patch.sql_table, SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (tag_sql, project_id))
    row = db.cursor.fetchone()
    print '<h1>%s patches tagged "%s"</h1>' % (escape(str(row[0])), tag_var)
    db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND tag = ? AND %s.project = ? GROUP BY srcpackage ORDER BY c DESC;''' % (SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (tag_sql, project_id))
    for row in db.cursor:
        print '<a href="./srcpackage.py?srcpackage=%s">%s</a>: <a href="%s?srcpackage=%s&amp;tag=%s">%s</a><br />' % (escape(row['n']), escape(row['n']), escape(os.environ['SCRIPT_NAME']), escape(row['n']), escape(tag_var), escape(str(row['c'])))

else:
    db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, ('GNOME:Factory',))
    row = db.cursor.fetchone()
    if row:
        project_id = row['id']
    else:
        project_id = -1

    db.cursor.execute('''SELECT COUNT(*) FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ?;''' % (Patch.sql_table, SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    row = db.cursor.fetchone()
    print '<h1>%s patches</h1>' % escape(str(row[0]))

    print '<h2>Order by tag</h2>'
    db.cursor.execute('''SELECT COUNT(*) AS c, tag FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY tag ORDER BY c DESC;''' % (Patch.sql_table, SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    for row in db.cursor:
        if row['tag'] == '':
            tag = 'None'
        else:
            tag = escape(row['tag'])
        print '<a href="%s?tag=%s">%s</a>: %s<br />' % (escape(os.environ['SCRIPT_NAME']), tag, tag, escape(str(row['c'])))

    print '<h2>Order by source package</h2>'
    db.cursor.execute('''SELECT COUNT(*) AS c, %s.name AS n FROM %s, %s WHERE %s.srcpackage = %s.id AND %s.project = ? GROUP BY srcpackage ORDER BY c DESC;''' % (SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, Patch.sql_table, SrcPackage.sql_table, SrcPackage.sql_table), (project_id,))
    for row in db.cursor:
        print '<a href="./srcpackage.py?srcpackage=%s">%s</a>: <a href="%s?srcpackage=%s">%s</a><br />' % (escape(row['n']), escape(row['n']), escape(os.environ['SCRIPT_NAME']), escape(row['n']), escape(str(row['c'])))

print_foot()
