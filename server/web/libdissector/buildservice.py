# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2009, Novell, Inc.
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

import urllib2

from cgi import escape
from urllib import urlencode
from urlparse import urlsplit, urlunsplit

try:
    from lxml import etree as ET
except ImportError:
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

import config


#######################################################################


class BuildServiceException(Exception):

    def __init__(self, value):
        self.msg = value

    def __str__(self):
        return self.msg


#######################################################################


def get_source_url(project, package, file = None, rev = None, do_escape = False):
    if do_escape:
        project = escape(project)
        package = escape(package)
        if file:
            file = escape(file)

    (scheme, netloc) = urlsplit(config.apiurl)[0:2]
    path = '/'.join(('public', 'source', project, package))
    if file:
        path = '/'.join((path, file))
    if rev:
        query = urlencode({'rev': rev})
    else:
        query = None

    url = urlunsplit((scheme, netloc, path, query, ''))

    return url

def get_source_link(project, package, file = None, rev = None, do_escape = False, text = None, title = None):
    url = get_source_url(project, package, file, rev, do_escape)
    if title:
        title_attr = ' title="%s"' % escape(title)
    else:
        title_attr = ''

    if not text:
        text = file or package
    text = escape(text)

    return '<a href="%s"%s>%s</a>' % (url, title_attr, text)


#######################################################################


def fetch_package_content(project, package):
    url = get_source_url(project, package)
    url += '?expand=1'
    try:
        fd = urllib2.urlopen(url)
        directory = ET.parse(fd).getroot()

        linkinfo = directory.find('linkinfo')
        if linkinfo != None:
            srcmd5 = directory.get('srcmd5')
        else:
            srcmd5 = ''

        files = []
        for node in directory.findall('entry'):
            files.append(node.get('name'))

        fd.close()

        return (files, srcmd5)

    except urllib2.HTTPError, e:
        raise BuildServiceException('Error while fetching the content: %s' % (e.msg,))
    except urllib2.URLError, e:
        raise BuildServiceException('Error while fetching the content: %s' % (e,))
    except SyntaxError, e:
        raise BuildServiceException('Error while fetching the content: %s' % (e.msg,))

    return (None, None)
