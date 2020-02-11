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


from libdissector import config
from libdissector import libhttp

if config.cgitb:
    import cgitb; cgitb.enable()


#######################################################################


libhttp.print_html_header()
libhttp.print_header("Our playground for openSUSE")

print '''
<h2>Our playground for openSUSE</h2>

<p>If you're simply interested in browsing the openSUSE source, head to the <a href="http://build.opensuse.org/">openSUSE instance</a> of the <a href="http://open-build-service.org/">Open Build Service</a>! No need to login, just browse the packages; the most interesting projects are the ones starting with "openSUSE:", like <a href="https://build.opensuse.org/project/show?project=openSUSE%3AFactory">openSUSE:Factory</a>.</p>

<p>The original idea behind this playground was to analyze the packages of the GNOME team to know what kind of work is needed, but it has evolved and it's now a good place to get some data about all packages in openSUSE.</a>

<p>This playground also hosts a service that makes it easier to collaborate within the openSUSE community, via <a href="http://en.opensuse.org/openSUSE:Osc_Collab">osc collab</a>. This service works for all packages part of <a href="https://build.opensuse.org/project/show?project=openSUSE%3AFactory">openSUSE:Factory</a>!</p>

<p>On the right side, you can find a few links that are, hopefully, self-explanatory :-)</p>
'''

libhttp.print_foot()
