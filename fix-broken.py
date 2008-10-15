#!/usr/bin/python
# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2008, Novell, Inc.
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
# Authors: Vincent Untz <vuntz@novell.com>
#

import os
import sys

import optparse
import shutil
import subprocess
import tempfile

try:
    from xml.etree import cElementTree as ET
except ImportError:
    import cElementTree as ET

from osc import conf
from osc import core

def cleanup(dirs):
    for dir in dirs:
        shutil.rmtree(dir)

def exception_print(self, e, message = ''):
    if message == None:
        message = ''

    if hasattr(e, 'msg'):
        print >>sys.stderr, message + e.msg
    elif str(e) != '':
        print >>sys.stderr, message + str(e)
    else:
        print >>sys.stderr, message + e.__class__.__name__

def main(args):
    parser = optparse.OptionParser()

    parser.add_option('--project', dest='project',
                      default='GNOME:Factory', help='project containing the package (default: GNOME:Factory)')

    (options, args) = parser.parse_args()

    if len(args) != 1:
        print >>sys.stderr, 'Wrong number of arguments'
        sys.exit(1)

    package = args[0]

    try:
        conf.get_config()
    except oscerr.NoConfigfile, e:
        print >>sys.stderr, e.msg
        sys.exit(1)

    apiurl = conf.config['apiurl']
    project = options.project

    tmpdir_oSF = tempfile.mkdtemp(prefix = 'osc-fix-apply-')
    tmpdir_project = tempfile.mkdtemp(prefix = 'osc-fix-apply-')
    cleanup_arg = [tmpdir_oSF, tmpdir_project]

    try:
        core.checkout_package(apiurl, project, package, prj_dir=tmpdir_project, expand_link=False)
    except Exception, e:
        message = 'Cannot check out %s from %s: ' % (package, project)
        exception_print(message, e)
        cleanup(cleanup_arg)
        sys.exit(1)

    linkfile = os.path.join(tmpdir_project, package, '_link')
    if not os.path.exists(linkfile):
        print >>sys.stderr, '%s from %s is not a link' % (package, project)
        cleanup(cleanup_arg)
        sys.exit(1)

    link_xml = ET.parse(linkfile)
    root = link_xml.getroot()
    link_to_project = root.get('project')
    if link_to_project != 'openSUSE:Factory':
        print >>sys.stderr, '%s from %s does not link to openSUSE:Factory' % (package, project)
        cleanup(cleanup_arg)
        sys.exit(1)

    link_to_package = root.get('package')
    if package != link_to_package:
        print >>sys.stderr, '%s from %s links to a package with another name: %s' % (package, project, link_to_package)
        cleanup(cleanup_arg)
        sys.exit(1)

    patches_nb = len(root.findall('patches'))
    if patches_nb == 0:
        print '%s from %s does not have any change' % (package, project)
        cleanup(cleanup_arg)
        sys.exit(0)
    if patches_nb != 1:
        print >>sys.stderr, '%s from %s contains _link with two many <patches> node' % (package, project)
        cleanup(cleanup_arg)
        sys.exit(1)

    patches = root.find('patches')
    deletes = patches.findall('delete')
    applies = patches.findall('apply')
    if len(deletes) + len(applies) == 0:
        print '%s from %s does not have any change' % (package, project)
        cleanup(cleanup_arg)
        sys.exit(0)

    try:
        core.checkout_package(apiurl, 'openSUSE:Factory', package, prj_dir=tmpdir_oSF, expand_link=True)
    except Exception, e:
        message = 'Cannot check out %s from %s: ' % (package, 'openSUSE:Factory')
        exception_print(message, e)
        cleanup(cleanup_arg)
        sys.exit(1)

    package_oSF_dir = os.path.join(tmpdir_oSF, package)
    package_project_dir = os.path.join(tmpdir_project, package)

    osc_package = core.filedir_to_pac(package_project_dir)

    for delete in deletes:
        file = delete.get('name')
        oS_file = os.path.join(package_oSF_dir, file)
        if os.path.exists(oS_file):
            print >>sys.stderr, '%s from %s needs a manual merge: %s still exists in %s' % (package, project, file, 'openSUSE:Factory')
            cleanup(cleanup_arg)
            sys.exit(1)

        patches.remove(delete)

    # change order from last-to-first: that's the order to revert patches
    applies.reverse()
    for apply in applies:
        patch = apply.get('name')
        patch_file = os.path.join(package_project_dir, patch)
        patch_stdin = open(patch_file)

        popen = subprocess.Popen(['patch', '--reverse', '--quiet', '--no-backup-if-mismatch', '-p0'], cwd = package_oSF_dir, stdin = patch_stdin)
        retval = popen.wait()

        patch_stdin.close()

        if retval != 0:
            print >>sys.stderr, '%s from %s needs a manual merge: %s does not apply in %s' % (package, project, patch, 'openSUSE:Factory')
            cleanup(cleanup_arg)
            sys.exit(1)

        osc_package.put_on_deletelist(patch)
        osc_package.write_deletelist()
        osc_package.delete_source_file(patch)
        patches.remove(apply)

    for file in os.listdir(package_project_dir):
        if file in ['_link', '.osc']:
            continue

        project_file = os.path.join(package_project_dir, file)
        if os.path.isdir(project_file):
            print >>sys.stderr, '%s from %s needs a manual merge: %s is a directory' % (package, project, file)
            cleanup(cleanup_arg)
            sys.exit(1)

        oSF_file = os.path.join(package_oSF_dir, file)
        if not os.path.exists(oSF_file):
            print >>sys.stderr, '%s from %s needs a manual merge: %s does not exist in %s' % (package, project, file, 'openSUSE:Factory')
            cleanup(cleanup_arg)
            sys.exit(1)

        popen = subprocess.Popen(['cmp', '--silent', project_file, oSF_file])
        retval = popen.wait()

        if retval != 0:
            print >>sys.stderr, '%s from %s needs a manual merge: %s is different in %s' % (package, project, file, 'openSUSE:Factory')
            cleanup(cleanup_arg)
            sys.exit(1)

        osc_package.put_on_deletelist(file)
        osc_package.write_deletelist()
        osc_package.delete_source_file(file)


    # Bad hack to have good indentation
    patches.text = root.text

    link_xml.write(linkfile)

    osc_package.commit(msg='Automatic fix for broken link')

    print '%s in %s has been fixed.' % (package, project)
    cleanup(cleanup_arg)

if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
