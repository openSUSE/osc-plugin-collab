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

import os
import sys

import errno
import optparse
import socket

import config
import util


#######################################################################


class ShellException(Exception):
    pass


#######################################################################


def get_conf(args, parser = None):
    if not parser:
        parser = optparse.OptionParser()

    parser.add_option('--config', dest='config',
                      help='configuration file to use')
    parser.add_option('--opensuse', dest='opensuse',
                      action='store_true', default=False,
                      help='use the openSUSE config as a basis')
    parser.add_option('--log', dest='log',
                      help='log file to use (default: stderr)')

    (options, args) = parser.parse_args()

    if options.log:
        path = os.path.realpath(options.log)
        util.safe_mkdir_p(os.path.dirname(path))
        sys.stderr = open(options.log, 'a')

    try:
        conf = config.Config(options.config, use_opensuse = options.opensuse)
    except config.ConfigException, e:
        print >>sys.stderr, e
        return (args, options, None)

    if conf.sockettimeout > 0:
        # we have a setting for the default socket timeout to not hang forever
        socket.setdefaulttimeout(conf.sockettimeout)

    try:
        os.makedirs(conf.cache_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            print >>sys.stderr, 'Cannot create cache directory.'
            return (args, options, None)

    return (args, options, conf)


#######################################################################


def read_status(filename, template):
    """ Read the last known status of the script. """
    result = template.copy()

    if not os.path.exists(filename):
        return result

    file = open(filename)
    lines = file.readlines()
    file.close()

    for line in lines:
        line = line[:-1]
        handled = False

        for key in result.keys():
            if line.startswith(key + '='):
                value = line[len(key + '='):]
                try:
                    result[key] = int(value)
                except ValueError:
                    raise ShellException('Cannot parse status value for %s: %s' % (key, value))

            handled = True

        if not handled:
            raise ShellException('Unknown status line: %s' % (line,))

    return result


def write_status(filename, status_dict):
    """ Save the last known status of the script. """
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    tmpfilename = filename + '.new'

    # it's always better to have things sorted, since it'll be predictable
    # (so better for human eyes ;-))
    items = status_dict.items()
    items.sort()

    file = open(tmpfilename, 'w')
    for (key, value) in items:
        file.write('%s=%d\n' % (key, value))
    file.close()

    os.rename(tmpfilename, filename)


#######################################################################


def lock_run(conf, name = None):
    # FIXME: this is racy, we need a real lock file. Or use an atomic operation
    # like mkdir instead
    if name:
        running_file = os.path.join(conf.cache_dir, 'running-' + name)
    else:
        running_file = os.path.join(conf.cache_dir, 'running')

    if os.path.exists(running_file):
        print >>sys.stderr, 'Another instance of the script is running.'
        return False

    open(running_file, 'w').write('')

    return True


def unlock_run(conf, name = None):
    if name:
        running_file = os.path.join(conf.cache_dir, 'running-' + name)
    else:
        running_file = os.path.join(conf.cache_dir, 'running')

    os.unlink(running_file)


#######################################################################
