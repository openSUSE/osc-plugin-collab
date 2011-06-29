#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

import cgi
from cgi import escape
import cgitb; cgitb.enable()
import os
import sys
import sqlite3

form = cgi.FieldStorage()

if form.has_key('future'):
    use_future = True
else:
    use_future = False

if use_future:
    DATABASE = '/tmp/obs-reserve-future.db'
    DATABASE_READ = '/tmp/obs-future.db'
else:
    DATABASE = '/tmp/obs-reserve.db'
    DATABASE_READ = '/tmp/obs.db'

print 'Content-type: text/plain'
print

if not form.has_key('mode'):
    print '400 No mode specified'
    sys.exit(0)

mode = form.getfirst('mode')
if mode != 'get' and mode != 'getall' and mode != 'set' and mode != 'unset':
    print '400 Unknown specified mode: ' + mode
    sys.exit(0)

projects = form.getlist('project')
for project in projects:
    if project in ['']:
        projects.remove(project)

if not projects:
    print '400 No project specified'
    sys.exit(0)

if mode != 'getall':
    if not form.has_key('package'):
        print '400 No package specified'
        sys.exit(0)

    package = form.getfirst('package')
    if package in ['']:
        print '400 Empty package'
        sys.exit(0)

if mode == 'set' or mode == 'unset':
    if not form.has_key('user'):
        print '400 No user specified'
        sys.exit(0)
    user = form.getfirst('user')
else:
    user = None

if os.path.exists(DATABASE):
   create_db = False
   if not os.access(DATABASE, os.W_OK):
        print '500 Read-only database'
        sys.exit(0)
else:
    create_db = True

db = sqlite3.connect(DATABASE)
if not db:
    print '500 No database'
    sys.exit(0)

db.row_factory = sqlite3.Row
cursor = db.cursor()

if create_db:
    cursor.execute('''CREATE TABLE reserve (date TEXT, user TEXT, package TEXT, project TEXT);''')

# automatically remove old reservations
cursor.execute('''DELETE FROM reserve WHERE datetime(date, '+36 hours') < datetime('now');''')

# just don't do anything if we have more than 100 reservations (we're getting
# spammed)
cursor.execute('''SELECT COUNT(*) FROM reserve;''')
row = cursor.fetchone()
if not row or row[0] > 100:
    cursor.close()
    db.close()
    print '500 Database unavailable'
    sys.exit(0)

if mode == 'getall':
    projects_where = ' OR '.join(['project = ?' for project in projects])
    cursor.execute('''SELECT * FROM reserve WHERE %s ORDER BY project, package;''' % projects_where, projects)
    rows = cursor.fetchall()
    print '200'
    for row in rows:
        print row['project'] + ';' + row['package'] + ';' + row['user'] + ';'
else:
    # get read-only cursor for the obs database
    if not os.path.exists(DATABASE_READ):
        print '500 No package database'
        sys.exit(0)

    db_r = sqlite3.connect(DATABASE_READ)
    if not db_r:
        print '500 No package database'
        sys.exit(0)

    cursor_r = db_r.cursor()

    found = False
    for project in projects:
        cursor_r.execute('''SELECT COUNT(*) FROM project, srcpackage WHERE project.name = ? AND srcpackage.name = ? AND srcpackage.project = project.id;''', (project, package,))
        row_r = cursor_r.fetchone()
        if row_r[0] != 0:
            found = True
            break
    if not found:
        print '404 Non existing package: ' + package
        sys.exit(0)


    cursor.execute('''SELECT * FROM reserve WHERE project = ? AND package = ?;''', (project, package,))
    row = cursor.fetchone()
    if mode == 'get':
        if row:
            print '200 ' + project + ';' + package + ';' + row['user'] + ';'
        else:
            print '200 ' + project + ';' + package + ';;Package not reserved'

    elif mode == 'set':
        if row:
            print '403 Package already reserved by ' + row['user']
        else:
            cursor.execute('''INSERT INTO reserve VALUES (datetime('now'), ?, ?, ?);''', (user, package, project))
            print '200'

    elif mode == 'unset':
        if row:
            if row['user'] == user:
                cursor.execute('''DELETE FROM reserve WHERE user = ? AND project = ? AND package = ?''', (user, project, package))
                print '200'
            else:
                print '403 Package reserved by ' + row['user']
        else:
            print '404 Package not reserved'

cursor.close()
db.commit()
db.close()
