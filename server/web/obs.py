#!/usr/bin/env python
# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2008-2010, Novell, Inc.
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
import sys

import cgi
from cgi import escape

from libdissector import config
from libdissector import libdbhtml
from libdissector import libhttp
from libdissector import libinfoxml

if config.cgitb:
    import cgitb; cgitb.enable()


#######################################################################


def compare_versions_a_gt_b (a, b):
    split_a = a.split('.')
    split_b = b.split('.')
    if len(split_a) != len(split_b):
        return a > b
    for i in range(len(split_a)):
        try:
            int_a = int(split_a[i])
            int_b = int(split_b[i])
            if int_a > int_b:
                return True
            if int_b > int_a:
                return False
        except ValueError:
            if split_a[i] > split_b[i]:
                return True
            if split_b[i] > split_a[i]:
                return False

    return False


#######################################################################


def colortype_to_style(colortype):
    if colortype is None:
        return ''

    colors = {
        'not-in-parent': ('#75507b', 'white'),
        'delta':         ('#3465a4', 'white'),
        'no-upstream':   ('#fce94f', None),
        'new-upstream':  ('#a40000', 'white')
    }

    (bg, text) = colors[colortype]

    if bg or text:
        style = ' style="'
        if bg:
            style += 'background: %s;' % bg
        if text:
            style += 'color: %s;' % text
        style += '"'
    else:
        style = ''

    return style


#######################################################################


def get_legend_box():
    s = ''
    s += '<div id="some_other_content" class="box box-shadow alpha clear-both">\n'
    s += '<h2 class="box-header">Legend</h2>\n'
    s += '<table>\n'
    s += '<tr><td>Package is perfect!</td></tr>\n'
    s += '<tr><td%s>Does not exist in parent</td></tr>\n' % colortype_to_style('not-in-parent')
    s += '<tr><td%s>Has delta with parent</td></tr>\n' % colortype_to_style('delta')
    s += '<tr><td%s>No upstream data</td></tr>\n' % colortype_to_style('no-upstream')
    s += '<tr><td%s>Upstream has a new version</td></tr>\n' % colortype_to_style('new-upstream')
    s += '</table>\n'
    s += '</div>\n'

    return s


#######################################################################


class Package:

    def __init__(self, node):
        self.name = None
        self.parent_project = None
        self.version = None
        self.upstream_version = None
        self.parent_version = None
        self.upstream_url = None
        self.has_delta = False

        if node is not None:
            self.name = node.get('name')

            parent = node.find('parent')
            if parent is not None:
                self.parent_project = parent.get('project')

            version = node.find('version')
            if version is not None:
                self.version = version.get('current')
                self.upstream_version = version.get('upstream')
                self.parent_version = version.get('parent')

            upstream = node.find('upstream')
            if upstream is not None:
                url = upstream.find('url')
                if url is not None:
                    self.upstream_url = url.text

            link = node.find('link')
            if link is not None:
                if link.get('delta') == 'true':
                    self.has_delta = True

            delta = node.find('delta')
            if delta is not None:
                self.has_delta = True

            if not self.version:
                self.version = ''
            if not self.upstream_version:
                self.upstream_version = ''
            if not self.parent_version:
                self.parent_version = '--'
            if not self.upstream_url:
                self.upstream_url = ''

#######################################################################


def get_colortype(package, parent, use_upstream):
    color = None

    if parent and package.has_delta:
        color = 'delta'
    elif parent and package.parent_version == '--':
        color = 'not-in-parent'

    if use_upstream:
        if package.upstream_version not in [ '', '--' ]:
            newer_than_parent = package.parent_version == '--' or compare_versions_a_gt_b(package.upstream_version, package.parent_version)
            newer = compare_versions_a_gt_b(package.upstream_version, package.version)
            if newer and newer_than_parent:
                color = 'new-upstream'

        elif color is None and package.upstream_version != '--':
            color = 'no-upstream'

    return color


#######################################################################


def get_table_for_project(project, only_missing_upstream, only_missing_parent, use_future):
    info = libinfoxml.InfoXml(use_future = use_future)
    try:
        node = info.get_project_node(project)
    except libinfoxml.InfoXmlException, e:
        return 'Error: %s' % e.msg

    parent = node.get('parent')
    use_upstream = node.get('ignore_upstream') != 'true'

    packages = []
    for subnode in node.findall('package'):
        package = Package(subnode)

        if only_missing_upstream and use_upstream:
            if package.upstream_url:
                continue
            if package.upstream_version == '--':
                continue
        elif only_missing_parent and parent:
            if package.parent_version != '--':
                continue

        packages.append(package)

    if len(packages) == 0:
        return 'No package in %s.' % escape(project)

    if parent:
        same_parent = True
        for package in packages:
            if package.parent_project and package.parent_project != project and package.parent_project != parent:
                same_parent = False
                break

    s = ''
    s += '<h2>%s source packages in %s</h2>\n' % (len(packages), escape(project))
    s += '<table>\n'

    s += '<tr>\n'
    s += '<th>Package</th>\n'
    if parent:
        if same_parent:
            s += '<th>%s</th>\n' % escape(parent)
        else:
            s += '<th>%s</th>\n' % 'Parent project'

    s += '<th>%s</th>\n' % escape(project)
    if use_upstream:
        s += '<th>Upstream</th>\n'
    s += '</tr>\n'

    for package in packages:
        colortype = get_colortype(package, parent, use_upstream)
        style = colortype_to_style(colortype)

        row = '<tr><td%s>%s</td>' % (style, escape(package.name))
        if parent:
            row += '<td>%s</td>' % (escape(package.parent_version),)
        row += '<td>%s</td>' % escape(package.version)
        if use_upstream:
            if package.upstream_url and package.upstream_url != '':
                version_cell = '<a href="' + escape(package.upstream_url) + '">' + escape(package.upstream_version) + '</a>'
            else:
                version_cell = escape(package.upstream_version)
            row += '<td>%s</td>' % version_cell
        row += '</tr>'

        s += row
        s += '\n'

    s += '</table>\n'

    return s


#######################################################################


form = cgi.FieldStorage()

# Be a little bit nice to old osc gnome versions by not sending them stuff they
# won't understand
if form.has_key('format') and form.getfirst('format') == 'csv':
    print 'Content-type: text/plain'
    print

    print '# Please update osc gnome (osc-plugins-gnome package in openSUSE:Tools project)'
    sys.exit(0)

if form.has_key('future'):
    use_future = True
else:
    use_future = False

only_missing_upstream = libhttp.get_arg_bool(form, 'missing-upstream', False)
only_missing_parent = libhttp.get_arg_bool(form, 'missing-parent', False)

libhttp.print_html_header()

project = libhttp.get_project(form)
table = get_table_for_project(project, only_missing_upstream, only_missing_parent, use_future)

libhttp.print_header('Versions of packages in the Build Service for project %s' % escape(project))

print libdbhtml.get_project_selector(current_project = project, use_future = use_future)
print table

libhttp.print_foot(additional_box = get_legend_box())
