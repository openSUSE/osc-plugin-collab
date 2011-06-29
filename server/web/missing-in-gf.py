#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

# Was used to list packages in the database that are not in G:F. We have other projects there now, so deprecated.

from common import *
from commonhttp import *
import cgi
from cgi import escape
import cgitb; cgitb.enable()
import os
import sys

print 'Content-type: text/plain'
print

db_internal = PackageDB()
db = PackageDB('/tmp/obs.db')

db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, ('GNOME:Factory',))
row = db.cursor.fetchone()
if row:
    GF = row['id']
else:
    GF = -1

db_internal.cursor.execute('''SELECT name FROM %s ORDER BY name;''' % SrcPackage.sql_table)
db.cursor.execute('''SELECT name FROM %s WHERE project = ? ORDER BY name;''' % SrcPackage.sql_table, (GF,))

GF_packages = []

for row in db.cursor:
    GF_packages.append(row['name'])
for row in db_internal.cursor:
    if not row['name'] in GF_packages:
        print row['name']
