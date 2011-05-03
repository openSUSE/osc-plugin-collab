# vim: set ts=4 sw=4 et: coding=UTF-8

#
# Copyright (c) 2008-2009, Novell, Inc.
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

import errno

def safe_mkdir(dir):
    if not dir:
        return

    try:
        os.mkdir(dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise e

def safe_mkdir_p(dir):
    if not dir:
        return

    try:
        os.makedirs(dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise e

def safe_unlink(filename):
    """ Unlink a file, but ignores the exception if the file doesn't exist. """
    try:
        os.unlink(filename)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise e


########################################################


# comes from convert-to-tarball.py
def _strict_bigger_version(a, b):
    a_nums = a.split('.')
    b_nums = b.split('.')
    num_fields = min(len(a_nums), len(b_nums))
    for i in range(0,num_fields):
        if   int(a_nums[i]) > int(b_nums[i]):
            return a
        elif int(a_nums[i]) < int(b_nums[i]):
            return b
    if   len(a_nums) > len(b_nums):
        return a
    elif len(a_nums) < len(b_nums):
        return b
    else:
        return None


def bigger_version(a, b):
    # We compare versions this way (with examples):
    #   + 0.3 and 0.3.1:
    #     0.3.1 wins: 0.3 == 0.3 and 0.3.1 has another digit
    #   + 0.3-1 and 0.3-2:
    #     0.3-2 wins: 0.3 == 0.3 and 1 < 2
    #   + 0.3.1-1 and 0.3-2:
    #     0.3.1-1 wins: 0.3.1 > 0.3
    a_nums = a.split('-')
    b_nums = b.split('-')
    num_fields = min(len(a_nums), len(b_nums))
    for i in range(0,num_fields):
        bigger = _strict_bigger_version(a_nums[i], b_nums[i])
        if   bigger == a_nums[i]:
            return a
        elif bigger == b_nums[i]:
            return b
    if len(a_nums) > len(b_nums):
        return a
    else:
        return b


def version_gt(a, b):
    if a == b:
        return False

    bigger = bigger_version(a, b)
    return a == bigger

def version_ge(a, b):
    if a == b:
        return True

    bigger = bigger_version(a, b)
    return a == bigger
