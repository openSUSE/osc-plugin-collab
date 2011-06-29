#!/usr/bin/python2.5
# vim: set ts=4 sw=4 et: coding=UTF-8

# Was used to upload a database based on autobuild data. Deprecated by OBS data.

import base64
import cgi
import os

# deactivate completely
print 'Unauthorized access'

UPLOAD_DIR = '/tmp'
UPLOAD_BASENAME = 'opensuse.db'

def save_uploaded_file (form_field, upload_dir, filename):
    form = cgi.FieldStorage()
    if not form.has_key(form_field):
        return

    fileitem = form[form_field]
    if not fileitem.file:
        return

    # force the filename where we save, so we're not remote exploitable
    tmpfilename = os.path.join(upload_dir, filename + '.tmp')
    destname = os.path.join(upload_dir, filename)
    fout = file (tmpfilename, 'wb')

    size = 0
    complete = False

    while 1:
        chunk = fileitem.file.read(100000)
        if not chunk:
            complete = True
            break
        size = size + 100000
        # if bigger than 3MB, we give up. This way, it's not possible to fill
        # the disk
        # FWIW: when there's was 8000 rpmlint errors for the lang %doc problem,
        # the db size was 1385472
        if size > 1024*1024*3:
            break
        fout.write (chunk)
    fout.close()

    if complete:
        os.rename(tmpfilename, destname)
    else:
        print 'File upload canceled: file is too big'

    if os.path.exists(tmpfilename):
        os.unlink(tmpfilename)

print 'content-type: text/html\n'

if os.environ['REMOTE_ADDR'] == 'XXX.XXX.XXX.XXX':
    save_uploaded_file ('dbfile', UPLOAD_DIR, UPLOAD_BASENAME)
else:
    print 'Unauthorized access'
