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
libhttp.print_header("Some playground for openSUSE")

print '''
<h2>Some playground for openSUSE</h2>
<p>You can find here some playground where the GNOME team put some scripts related to openSUSE. The original idea was to analyze our packages to know what kind of work is needed, but this has evolved in various things.
It's now a good place to get some data about openSUSE. And foremost, it hosts a service that makes it easier to collaborate within the openSUSE GNOME team, via <a href="http://en.opensuse.org/GNOME/OscGnome">osc gnome</a>. This service is available for all other teams: you can use it, it's already working for your projects!</p>

<p>On the left side, you can find a few links that are, hopefully, self-explanatory :-)</p>
'''

libhttp.print_foot()
