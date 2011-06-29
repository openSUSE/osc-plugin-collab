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
# Authors: Vincent Untz <vuntz@oepnsuse.org>
#

#
# The included HTML code here is the design from the openSUSE project.
# FIXME: find the right copyright/license for it.
#

import config
import libdbcore

def print_text_header():
    print 'Content-type: text/plain'
    print

def print_xml_header():
    print 'Content-type: text/xml'
    print

def print_html_header():
    print 'Content-type: text/html'
    print

def print_header_raw(title):
    print '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="MSSmartTagsPreventParsing" content="TRUE" />
    <title>%s</title>
    </head>

<body>
''' % title

def print_foot_raw():
    print '''
</body>
</html>'''

def print_header(title=''):
    print '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
 <head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <meta name="robots" content="index,follow" />

  <link rel="stylesheet" href="theme/css/style.css" type="text/css" media="screen" title="All" charset="utf-8" />
  <link rel="stylesheet" href="theme/css/print.css" type="text/css" media="print" charset="utf-8">

  <script src="theme/js/jquery.js" type="text/javascript" charset="utf-8"></script>
  <script src="theme/js/global-navigation-data-en_US.js" type="text/javascript" charset="utf-8"></script>
  <script src="theme/js/global-navigation.js" type="text/javascript" charset="utf-8"></script>

  <link rel="icon" type="image/png" href="theme/images/favicon.png" />
  <title>%s</title>
 </head>

<body>
  <!-- Start: Header -->
  <div id="header">
    <div id="header-content" class="container_12">
      <a id="header-logo" href="./"><img src="theme/images/header-logo.png" width="46" height="26" alt="Header Logo" /></a>
      <ul id="global-navigation">
        <li id="item-downloads"><a href="http://en.opensuse.org/openSUSE:Browse#downloads">Downloads</a></li>
        <li id="item-support"><a href="http://en.opensuse.org/openSUSE:Browse#support">Support</a></li>
        <li id="item-community"><a href="http://en.opensuse.org/openSUSE:Browse#community">Community</a></li>
        <li id="item-development"><a href="http://en.opensuse.org/openSUSE:Browse#development">Development</a></li>
      </ul>
    </div>
  </div>
  <!-- End: Header -->

  <!-- Start: Main Content Area -->
  <div id="content" class="container_16 content-wrapper">

    <div class="box box-shadow grid_12 alpha">

        <!-- Begin Content Area -->
''' % title

def print_foot(additional_box = ''):
    timestr = libdbcore.get_db_mtime()
    print '''
      <!-- End Content Area -->
    </div>

    <div class="column grid_4 omega">

      <div id="some_other_content" class=" box box-shadow alpha clear-both navigation">
        <h2 class="box-header">Navigation</h2>
          <ul class="navigation">
            <li><a href="./obs">Packages Status</a></li>
            <li><a href="./patch">Patches Status</a></li>
            <!--<li><a href="./rpmlint">Rpmlint Status</a></li>-->
          </ul>
      </div>

%s

    </div>

  </div>

  <!-- Start: included footer part -->
  <div id="footer" class="container_12">
    <!-- TODO: add content -->
    <div id="footer-legal" class="border-top grid_12">
      <p>
        This is still a prototype and is not officially endorsed by the openSUSE project.
        <br />
        Database last updated on %s
      </p>
    </div>
  </div>
 </body>
</html>''' % (additional_box, timestr)

# At some point we wanted to have this too:

'''
       <div class="green_box">
        <div class="box_top_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
        <div class="box_title_row">
         <div class="box_title">
          Statistics
         </div>
        </div>
        <div class="box_content">
         <ul class="navlist">
          <li>General stats</li>
          <li>Graphes</li>
         </ul>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <br />
'''

'''
       <div class="green_box">
        <div class="box_top_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
        <div class="box_title_row">
         <div class="box_title">
          Reports
         </div>
        </div>
        <div class="box_content">
         <ul class="navlist">
          <li>Build Failures</li>
          <li>Tagging Progress</li>
          <li>Rpmlint Progress</li>
          <li>Bug Filing Status</li>
          <li>Patch Rebase Status</li>
          <li>Patch SLE Status</li>
         </ul>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <br />
'''

def get_arg(form, name, default_value = None):
    if form.has_key(name):
        return form.getfirst(name)
    else:
        return default_value

def get_arg_bool(form, name, default_value = False):
    if default_value:
        default = '1'
    else:
        default = '0'

    value = get_arg(form, name, default)
    try:
        return (int(value) == 1)
    except ValueError:
        return default_value

def get_project(form):
    return get_arg(form, 'project', config.default_project)

def get_srcpackage(form):
    ret = get_arg(form, 'srcpackage')
    if not ret:
        ret = get_arg(form, 'package')
    return ret
