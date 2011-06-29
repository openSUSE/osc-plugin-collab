# vim: set ts=4 sw=4 et: coding=UTF-8

import os

import sqlite3
import time

from stat import *
from cgi import escape

DB_FILE = '/tmp/obs.db'
DB_FILE_FUTURE = '/tmp/obs-future.db'
db_major = None
db_minor = None

def get_db_mtime(use_future=False):
    if use_future:
        db_file = DB_FILE_FUTURE
    else:
        db_file = DB_FILE
    return time.gmtime(os.stat(db_file)[ST_MTIME])

class PackageDB:
    def __init__(self, use_future=False):
    	if use_future:
            db_file = DB_FILE_FUTURE
        else:
            db_file = DB_FILE
        self.db = sqlite3.connect(db_file)
        if self.db:
            self.db.row_factory = sqlite3.Row
            self.cursor = self.db.cursor()
            self.cursor.execute('''SELECT * FROM %s;''' % 'db_version')
            row = self.cursor.fetchone()
            if row:
                db_major = row['major']
                db_minor = row['minor']
    
    def __del__(self):
        if self.cursor:
            self.cursor.close()
        if self.db:
            self.db.close()

    def get_project_id(self, project_name):
        db.cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (name,))
        row = db.cursor.fetchone()
        if row:
            return row['id']
        else:
            return -1

class Base: 
    sql_table = 'undefined'

class File(Base):
    sql_table = 'file'

    def __init__(self, src):
        self.id = -1
        self.src_package_id = -1
        self.filename = ''
        self.src_package = src

    def fill_from_row(self, row):
        self.id = row['id']
        self.src_package_id = row['srcpackage']
        self.filename = row['filename']

class Source(File):
    sql_table = 'source'

class Patch(Base):
    sql_table = 'patch'

    def __init__(self, src):
        self.id = -1
        self.src_package_id = -1
        self.filename = ''
        self.number = -1
        self.apply_order = -1
        self.disabled = 0
        self.src_package = src
        self.tag = ''
        self.tag_filename = ''
        self.bnc = 0
        self.bgo = 0
        self.bmo = 0
        self.bln = 0
        self.brc = 0
        self.fate = 0
        self.cve = 0
        self.short_descr = ''
        self.descr = ''

    def fill_from_row(self, row):
        self.id = row['id']
        self.src_package_id = row['srcpackage']
        self.filename = row['filename']
        self.number = row['nb_in_pack']
        self.apply_order = row['apply_order']
        self.disabled = row['disabled']
        self.tag = row['tag']
        self.tag_filename = row['tag_filename']
        self.bnc = row['bnc']
        self.bgo = row['bgo']
        self.bmo = row['bmo']
        self.bln = row['bln']
        self.brc = row['brc']
        self.fate = row['fate']
        self.cve = row['cve']
        self.short_descr = row['short_descr']
        self.descr = row['descr']

class RpmlintReport(Base):
    sql_table = 'rpmlint'

    def __init__(self, srcpackage):
        self.id = -1
        self.srcpackage_id = -1
        self.srcpackage = srcpackage
        self.level = ''
        self.type = ''
        self.detail = ''
        self.descr = ''

    def fill_from_row(self, row):
        self.id = row['id']
        self.srcpackage_id = row['srcpackage']
        self.level = row['level']
        self.type = row['type']
        self.detail = row['detail']
        self.descr = row['descr']

class Package(Base):
    sql_table = 'package'

    def __init__(self, src):
        self.id = -1
        self.src_package_id = -1
        self.name = ''
        self.src_package = src
        self.summary = ''
        self.description = ''

    def fill_from_row(self, row):
        self.id = row['id']
        self.src_package_id = row['srcpackage']
        self.name = row['name']
        self.summary = row['summary']
        self.description = row['description']

class SrcPackage(Base):
    sql_table = 'srcpackage'

    def __init__(self):
        self.id = -1
        self.name = ''
        self.project_id = -1
        self.upstream_name = ''
        self.version = ''
        self.upstream_version = ''
        self.upstream_url = ''
        self.srcmd5 = ''
        self.is_obs_link = 0
        self.packages = []
        self.sources = []
        self.patches = []
        self.files = []
        self.rpmlint_reports = []

    @classmethod
    def get_from_db(cls, name, cursor, project = 'GNOME:Factory'):
        cursor.execute('''SELECT id FROM %s WHERE name = ?;''' % Project.sql_table, (project,))
        row = cursor.fetchone()
        if row:
            project_id = row['id']
        else:
            return None

        cursor.execute('''SELECT * FROM %s WHERE name = ? and project = ?;''' % SrcPackage.sql_table,
                       (name, project_id))
        row = cursor.fetchone()
        if not row:
            return None

        srcpackage = SrcPackage()
        srcpackage.id = row['id']
        srcpackage.name = row['name']
        if db_major >= 2:
            srcpackage.project_id = row['project']
        srcpackage.upstream_name = row['upstream_name']
        srcpackage.version = row['version']
        srcpackage.upstream_version = row['upstream_version']
        srcpackage.upstream_url = row['upstream_url']
        srcpackage.srcmd5 = row['srcmd5']
        srcpackage.is_obs_link = row['is_obs_link']

        cursor.execute('''SELECT * FROM %s WHERE srcpackage = ?;''' % Package.sql_table,
                       (srcpackage.id,))
        for row in cursor:
            package = Package(srcpackage.name)
            package.fill_from_row(row)
            srcpackage.packages.append(package)

        cursor.execute('''SELECT * FROM %s WHERE srcpackage = ?;''' % RpmlintReport.sql_table,
                       (srcpackage.id,))
        for row in cursor:
            rpmlint = RpmlintReport(srcpackage.name)
            rpmlint.fill_from_row(row)
            srcpackage.rpmlint_reports.append(rpmlint)

        cursor.execute('''SELECT * FROM %s WHERE srcpackage = ?;''' % Source.sql_table,
                       (srcpackage.id,))
        for row in cursor:
            source = Source(srcpackage.name)
            source.fill_from_row(row)
            srcpackage.sources.append(source)

        cursor.execute('''SELECT * FROM %s WHERE srcpackage = ?;''' % Patch.sql_table,
                       (srcpackage.id,))
        for row in cursor:
            patch = Patch(srcpackage.name)
            patch.fill_from_row(row)
            srcpackage.patches.append(patch)

        cursor.execute('''SELECT * FROM %s WHERE srcpackage = ?;''' % File.sql_table,
                       (srcpackage.id,))
        for row in cursor:
            file = File(srcpackage.name)
            file.fill_from_row(row)
            srcpackage.files.append(file)

        return srcpackage

    def __str__(self):
        if self.is_obs_link and self.srcmd5 != '':
            api_source_args = '?rev=' + self.srcmd5
        else:
            api_source_args = ''
        ret = ''
        ret = ret + "Name: %s\n" % self.name
        ret = ret + "Upstream name: %s\n" % self.upstream_name
        ret = ret + "Packaged version: %s\n" % self.version
        if self.upstream_url and self.upstream_url != '':
            ret = ret + "Upstream version: <a href=\"%s\">%s</a>\n" %  (escape(self.upstream_url), self.upstream_version)
        else:
            ret = ret + "Upstream version: %s\n" % self.upstream_version
        ret = ret + "Sources:\n"
        for source in self.sources:
            if source.filename.find('/'):
                source.filename = source.filename[source.filename.rfind('/') + 1:]
            ret = ret + "  <a href=\"https://api.opensuse.org/public/source/GNOME:Factory/%s/%s%s\">%s</a>\n" % (self.name, source.filename, api_source_args, source.filename)
        ret = ret + "<a href=\"./patch.py?srcpackage=%s\">Patches</a>:\n" % escape(self.name)
        for patch in self.patches:
            ret = ret + "  %s: <a href=\"https://api.opensuse.org/public/source/GNOME:Factory/%s/%s%s\">%s</a>" % (patch.number, self.name, patch.filename, api_source_args, patch.filename)
            if patch.disabled != 0:
                ret = ret + " (not applied)\n"
            else:
                ret = ret + "\n"
        ret = ret + "Packages:\n"
        for package in self.packages:
            ret = ret + "  %s\n" % package.name
        ret = ret + "<a href=\"./rpmlint.py?srcpackage=%s\">%d rpmlint errors</a>\n" % (escape(self.name), len(self.rpmlint_reports))
        return ret

class Project(Base):
    sql_table = 'project'

    def __init__(self, db, name):
        self.db = db
        self.id = -1
        self.parent = None
        self.name = name
        self.ignore_upstream = False

        if name:
            db.execute('''SELECT * FROM %s WHERE name = ?;''' % Project.sql_table, (name,))
        else:
            return

        row = db.fetchone()
        if row:
            self.id = row['id']
            self.parent = row['parent']
            self.name = row['name']
            self.ignore_upstream = row['ignore_upstream'] != 0
