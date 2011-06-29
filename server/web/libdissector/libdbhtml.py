# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2009-2010, Novell, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#  * Neither the name of the <ORGANIZATION> nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#
# (Licensed under the simplified BSD license)
#
# Authors: Vincent Untz <vuntz@opensuse.org>
#

import os
from cgi import escape

import libdbcore

def get_project_selector(current_project = None, db = None, use_future = False):
    if not db:
        db = libdbcore.ObsDb(use_future)
    db.cursor.execute('''SELECT name FROM %s ORDER BY UPPER(name);''' % libdbcore.table_project)
    s = ''
    s += '<form action="%s">\n' % escape(os.environ['SCRIPT_NAME'])
    s += '<p>\n'
    s += 'Project:\n'
    s += '<select name="project">\n'
    for row in db.cursor:
        escaped_name = escape(row['name'])
        if row['name'] == current_project:
            selected = ' selected'
        else:
            selected = ''
        s += '<option value="%s"%s>%s</option>\n' % (escaped_name, selected, escaped_name)
    s += '</select>\n'
    s += '<input type="submit" value="choose">\n'
    s += '</p>\n'
    s += '</form>\n'

    return s
