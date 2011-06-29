# vim: set ts=4 sw=4 et: coding=UTF-8

from cgi import escape
import os
import time

import libdb as db

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

def print_header(title='', secondary_title=''):
    print '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" dir="ltr">
 <head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <meta name="robots" content="index,follow" />
  <title>%s</title>
  <link href="./css/local/include.css" rel="stylesheet" type="text/css" />
 </head>

<body>
  <div id="page_margins">
   <div id="page" class="hold_floats">
    <!-- Begin 2 column main part -->
    <div id="main">
     <!-- Begin left column -->
     <div id="col1">
      <div id="col1_content" class="clearfix">
       <!-- Begin Logo -->
       <div class="grey_box" id="logo">
        <div class="box_content_row">
         <div class="box_content" id="logo_content">
          <a href="./"><img src="./images/common/geeko.jpg" alt="openSUSE" /></a>
         </div>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <!-- End Logo -->
       <!-- Begin openSUSE navigation -->
       <div class="grey_box">
        <div class="box_top_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
        <div class="box_title_row">
         <div class="box_title">
          openSUSE
         </div>
        </div>
        <div class="box_content">
         <ul class="navlist">
          <li style="list-style-image: url(css/common/images/liDot_download.png)"><a href="http://software.opensuse.org/">Get Software</a></li>
          <li style="list-style-image: url(css/common/images/liDot_wiki.png)"><a href="http://en.opensuse.org/">Wiki</a></li>
          <li style="list-style-image: url(css/common/images/liDot_build.png)"><a href="http://build.opensuse.org/">Build Software</a></li>
          <li style="list-style-image: url(css/common/images/liDot_community.png)"><a href="http://users.opensuse.org/">User Directory</a></li>          
          <li style="list-style-image: url(css/common/images/liDot_wiki.png)"><a href="http://news.opensuse.org/">News</a></li>
          <li style="list-style-image: url(css/common/images/liDot_wiki.png)"><a href="http://shop.opensuse.org/">Shop</a></li>
         </ul>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <br />
       <!-- End openSUSE navigation -->
       <!-- Begin custom navigation -->
       <div class="green_box">
        <div class="box_top_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
        <div class="box_title_row">
         <div class="box_title">
          Queries
         </div>
        </div>
        <div class="box_content">
         <ul class="navlist">
          <li><a href="./browse.py">Browse openSUSE Source</a></li>
          <li><a href="./obs.py">GNOME:Factory Status</a></li>
          <li><a href="./srcpackage.py">G:F Source Packages</a></li>
          <li><a href="./patch.py">G:F Patches</a></li>
          <li><a href="./rpmlint.py">G:F Rpmlint</a></li>
         </ul>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <br />
       <!-- End custom navigation -->
      </div>
     </div>
     <!-- End left column -->
     <!-- Begin right cloumn -->
     <div id="col3">
      <div id="col3_content" class="clearfix">
       <div class="green_box_double" id="banner_green">
        <div class="box_content_row">
         <div class="box_content" id="banner_content">
          <div id="slogan">
       <img src="./images/local/analyze.png" alt="Analyze it (prototype, GNOME-related packages)" />
          </div>
         </div>
        </div>
        <div class="box_bottom_row">
         <div class="box_left"></div>
         <div class="box_right"></div>
        </div>
       </div>
       <br style="clear: right;" />
       <div id="contentarea">
        <div class="grey_box_double">
         <div class="box_top_row">
          <div class="box_left"></div>
          <div class="box_right"></div>
         </div>
         <div class="box_title_row">
          <div class="box_title">
           <div id="page_actions">
            <b style="font-size:120%%">%s</b>
           </div>
          </div>
         </div>
         <div class="box_content" id="bodyContent">
           <!-- Begin Content area-->
''' % (title, secondary_title)

def print_foot():
    timestr = time.strftime('%d/%m/%Y (%H:%M UTC)', db.get_db_mtime())
    print '''
<!-- End Content Area -->
          <div style="clear:both;"></div>
         </div>
         <div class="box_footer_row">
          <div id="page_footer" class="box_footer">
           <!-- Begin Footer -->
           This is still a prototype and is not officially endorsed by the openSUSE project.
           <br />
           Database last updated on %s
           <br />
           This site uses the <a href="http://www.yaml.de">YAML</a> CSS framework.
           <br />
           <a href="http://en.opensuse.org/openSUSE:About" title="openSUSE:About">About openSUSE</a>
           <br />
           <a href="http://www.novell.com/linux/"><img src="./images/common/founded_novell.gif" alt="Founded by Novell" /></a>
           <!-- End Footer -->
          </div>
         </div>
         <div class="box_bottom_row">
          <div class="box_left"></div>
          <div class="box_right"></div>
         </div>
        </div>
       </div>
      </div>
      <!-- IE Column Clearing -->
      <div id="ie_clearing">&nbsp;</div>
      <!-- Ende: IE Column Clearing -->
     </div>
     <!-- End right column -->
    </div>
    <!-- End 2 cloumn main part -->
   </div>
  </div>
 </body>
</html>''' % timestr

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

def print_project_selector(cursor, project):
    cursor.execute('''SELECT name FROM %s ORDER BY UPPER(name);''' % db.Project.sql_table)
    print '<form action="%s">' % escape(os.environ['SCRIPT_NAME'])
    print 'Project:'
    print '<select name="project">'
    for row in cursor:
        escaped_name = escape(row['name'])
        if row['name'] == project:
            selected = ' selected'
        else:
            selected = ''
        print '<option value="%s"%s>%s</option>' % (escaped_name, selected, escaped_name)
    print '</select>'
    print '<input type="submit" value="choose">'
    print '</form>'
