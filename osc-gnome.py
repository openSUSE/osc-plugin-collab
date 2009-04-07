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

# This is a hack to have osc ignore the file we create in a package directory.
exclude_stuff.append('osc-gnome.*')

class OscGnomeError(Exception):
    def __init__(self, value):
        self.msg = value

    def __str__(self):
        return repr(self.msg)


class OscGnomeWebError(OscGnomeError):
    pass

class OscGnomeDownloadError(OscGnomeError):
    pass

class OscGnomeNewsError(OscGnomeError):
    pass

class OscGnomeCompressError(OscGnomeError):
    pass


def _gnome_exception_print(self, e, message = ''):
    if message == None:
        message = ''

    if hasattr(e, 'msg'):
        print >>sys.stderr, message + e.msg
    elif str(e) != '':
        print >>sys.stderr, message + str(e)
    else:
        print >>sys.stderr, message + e.__class__.__name__


#######################################################################


class OscGnomeImport:

    _imported_modules = {}

    @classmethod
    def m_import(cls, module):
        if not cls._imported_modules.has_key(module):
            try:
                cls._imported_modules[module] = __import__(module)
            except ImportError:
                cls._imported_modules[module] = None

        return cls._imported_modules[module]


#######################################################################


class OscGnomeWeb:

    _reserve_url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
    _upstream_url = 'http://tmp.vuntz.net/opensuse-packages/upstream.py'
    _admin_url = 'http://tmp.vuntz.net/opensuse-packages/admin.py?mode=delta'
    _error_url = 'http://tmp.vuntz.net/opensuse-packages/admin.py?mode=error'
    _csv_url = 'http://tmp.vuntz.net/opensuse-packages/obs.py?format=csv'

    def __init__(self, exception, cache):
        self.Error = exception
        self.Cache = cache


    def _line_is_comment(self, line):
        return line.strip() == '' or line[0] == '#'

    def _append_data_to_url(self, url, data):
        if url.find('?') != -1:
            return '%s&%s' % (url, data)
        else:
            return '%s?%s' % (url, data)


    def _parse_reservation(self, line):
        try:
            (package, username, comment) = line[:-1].split(';')
            return (package, username, comment)
        except ValueError:
            print >>sys.stderr, 'Cannot parse reservation information: %s' % line[:-1]
            return (None, None, None)


    def _parse_project_package_details(self, fd):
        lines = fd.readlines()
        fd.close()

        packages_versions = []
        parent_project = ''

        for line in lines:
            # there's some meta-information hidden in comments :-)
            if line.startswith('#meta: '):
                meta = line[len('#meta: '):-1]
                if meta.startswith('parent='):
                    parent_project = meta[len('parent='):].strip()
                continue
            elif self._line_is_comment(line):
                continue
            try:
                (package, parent_version, devel_version, upstream_version, empty) = line.split(';')
                packages_versions.append((package, parent_version, devel_version, upstream_version))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
                continue

        return (parent_project, packages_versions)


    def get_project_details(self, project):
        data = urlencode({'project': project})
        url = self._append_data_to_url(self._csv_url, data)

        try:
            fd = self.Cache.get_url_fd_with_cache(url, 'db-obs-csv-%s' % project, 10)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of packages: %s' % e.msg)

        return self._parse_project_package_details(fd)


    def get_packages_with_delta(self, project):
        data = urlencode({'project': project})
        url = self._append_data_to_url(self._admin_url, data)

        try:
            fd = self.Cache.get_url_fd_with_cache(url, 'db-obs-admin-%s' % project, 10)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of packages with a delta: %s' % e.msg)

        lines = fd.readlines()
        fd.close()

        return [ line.strip() for line in lines if not self._line_is_comment(line) ]


    def get_packages_with_error(self, project):
        errors = []

        data = urlencode({'project': project})
        url = self._append_data_to_url(self._error_url, data)

        try:
            fd = self.Cache.get_url_fd_with_cache(url, 'db-obs-error-%s' % project, 10)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of packages with an error: %s' % e.msg)

        lines = fd.readlines()
        fd.close()

        for line in lines:
            if self._line_is_comment(line):
                continue
            try:
                (package, error, details) = line.split(';', 3)
                errors.append((package, error, details))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
                continue

        return errors


    def get_package_details(self, project, package):
        data = urlencode({'project': project, 'package': package})
        url = self._append_data_to_url(self._csv_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of package %s: %s' % (package, e.msg))

        (parent_project, packages_versions) = self._parse_project_package_details(fd)

        for (fd_package, parent_version, devel_version, upstream_version) in packages_versions:
            if fd_package == package:
                return (parent_project, parent_version, devel_version, upstream_version)

        # we didn't get the package we requested, oh well...
        return (parent_project, None, None, None)


    def get_project_parent(self, project):
        data = urlencode({'project': project, 'package': 'ignore-this'})
        url = self._append_data_to_url(self._csv_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get parent of project %s: %s' % (project, e.msg))

        (parent_project, packages_versions) = self._parse_project_package_details(fd)

        return parent_project


    def get_upstream_url(self, project, package):
        data = urlencode({'project': project, 'package': package})
        url = self._append_data_to_url(self._upstream_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get upstream URL of package %s: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

        if self._line_is_comment(line):
            return None

        try:
            (package, upstream_version, upstream_url, empty) = line.split(';')
        except ValueError:
            print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
            return None

        if empty and empty.strip() != '':
            raise self.Error('Upstream URL of package %s probably contains a semi-colon. This is a bug in the server and the plugin.' % package)

        return upstream_url


    def get_reserved_packages(self, return_package = True, return_username = True, return_comment = False):
        reserved_packages = []

        data = urlencode({'mode': 'getall'})
        url = self._append_data_to_url(self._reserve_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of reserved packages: %s' % e.msg)

        lines = fd.readlines()
        fd.close()

        # it returns a status code on the first line, and then one package per
        # line
        # if the status code is 200, then everything is good
        if lines[0][:3] != '200':
            raise self.Error('Error while getting list of reserved packages: %s' % lines[0][4:-1])
        else:
            del lines[0]
            for line in lines:
                if self._line_is_comment(line):
                    continue
                (package, username, comment) = self._parse_reservation(line)
                if package:
                    reserved_packages.append((package, username, comment))

        if return_package and return_username and return_comment:
            return reserved_packages
        elif return_package and return_username and not return_comment:
            retval = []
            for (package, username, comment) in reserved_packages:
                retval.append((package, username))
            return retval
        elif return_package and not return_username and not return_comment:
            retval = []
            for (package, username, comment) in reserved_packages:
                retval.append(package)
            return retval
        else:
            raise self.Error('Unsupported request for reserved packages. Please ask developers to implement it.')


    def is_package_reserved(self, package):
        data = urlencode({'mode': 'get', 'package': package})
        url = self._append_data_to_url(self._reserve_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot look if package %s is reserved: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot look if package %s is reserved: %s' % (package, line[4:-1]))

        (package, username, comment) = self._parse_reservation(line[4:])

        if not username or username == '':
            return None
        else:
            return username


    def reserve_package(self, package, username):
        data = urlencode({'mode': 'set', 'user': username, 'package': package})
        url = self._append_data_to_url(self._reserve_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot reserve package %s: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot reserve package %s: %s' % (package, line[4:-1]))


    def unreserve_package(self, package, username):
        data = urlencode({'mode': 'unset', 'user': username, 'package': package})
        url = self._append_data_to_url(self._reserve_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot unreserve package %s: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot unreserve package %s: %s' % (package, line[4:-1]))


#######################################################################


class GnomeCache:

    _cache_dir = None
    _format_str = '# osc-gnome-format: '
    _import = None
    _printed = False

    @classmethod
    def init(cls, import_function):
        cls._import = import_function

    @classmethod
    def _print_message(cls):
        if not cls._printed:
            cls._printed = True
            print 'Downloading data in a cache. It might take a few seconds...'

    @classmethod
    def _get_xdg_cache_dir(cls):
        if not cls._cache_dir:
            dir = None
            if os.environ.has_key('XDG_CACHE_HOME'):
                dir = os.environ['XDG_CACHE_HOME']
                if dir == '':
                    dir = None

            if not dir:
                dir = '~/.cache'

            cls._cache_dir = os.path.join(os.path.expanduser(dir), 'osc', 'gnome')

        return cls._cache_dir


    @classmethod
    def _need_update(cls, filename, maxage):
        cache = os.path.join(cls._get_xdg_cache_dir(), filename)

        if not os.path.exists(cache):
            return True

        if not os.path.isfile(cache):
            return True

        stats = os.stat(cache)
        time = cls._import('time')

        if time:
            now = time.time()
            if now - stats.st_mtime > maxage:
                return True
            # Back to the future?
            elif now < stats.st_mtime:
                return True
        else:
            return True

        return False


    @classmethod
    def get_url_fd_with_cache(cls, url, filename, max_age_minutes):
        if cls._need_update(filename, max_age_minutes * 60):
            # no cache available
            cls._print_message()
            fd = urllib2.urlopen(url)
            cls._write(filename, fin = fd)

        return open(os.path.join(cls._get_xdg_cache_dir(), filename))

    @classmethod
    def get_obs_meta(cls, apiurl, project):
        filename = 'meta-' + project
        cache = os.path.join(cls._get_xdg_cache_dir(), filename)

        # Only download if it's more than 2-days old
        if not cls._need_update(filename, 3600 * 24 * 2):
            return cache

        urllib = cls._import('urllib')
        if not urllib:
            print >>sys.stderr, 'Cannot get metadata of packages in %s: incomplete python installation.' % project
            return None

        # no cache available
        cls._print_message()

        # download the data
        try:
            url = makeurl(apiurl, ['search', 'package'], ['match=%s' % urllib.quote('@project=\'%s\'' % project)])
            fin = http_GET(url)
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Cannot get metadata of packages in %s: %s' % (project, e.msg)
            return None

        fout = open(cache, 'w')

        while True:
            try:
                bytes = fin.read(500 * 1024)
                if len(bytes) == 0:
                    break
                fout.write(bytes)
            except urllib2.HTTPError, e:
                fin.close()
                fout.close()
                os.unlink(cache)
                print >>sys.stderr, 'Error while downloading metadata: %s' % e.msg
                return None

        fin.close()
        fout.close()

        return cache


    @classmethod
    def get_obs_build_results(cls, apiurl, project):
        filename = 'build-results-' + project
        cache = os.path.join(cls._get_xdg_cache_dir(), filename)

        # Only download if it's more than 2-hours old
        if not cls._need_update(filename, 3600 * 2):
            return cache

        urllib = cls._import('urllib')
        if not urllib:
            print >>sys.stderr, 'Cannot get build results of packages in %s: incomplete python installation.' % project
            return None

        # no cache available
        cls._print_message()

        # download the data
        try:
            url = makeurl(apiurl, ['build', project, '_result'])
            fin = http_GET(url)
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Cannot get build results of packages in  %s: %s' % (project, e.msg)
            return None

        fout = open(cache, 'w')

        while True:
            try:
                bytes = fin.read(500 * 1024)
                if len(bytes) == 0:
                    break
                fout.write(bytes)
            except urllib2.HTTPError, e:
                fin.close()
                fout.close()
                os.unlink(cache)
                print >>sys.stderr, 'Error while downloading build results: %s' % e.msg
                return None

        fin.close()
        fout.close()

        return cache


    @classmethod
    def get_obs_submit_request_list(cls, apiurl, project, include_request_id = False):
        current_format = 2
        filename = 'submitted-' + project

        # Only download if it's more than 10-minutes old
        if not cls._need_update(filename, 60 * 10):
            fcache = open(os.path.join(cls._get_xdg_cache_dir(), filename))
            format_line = fcache.readline()

            if cls._is_same_format(format_line, current_format):
                # we can use the cache
                retval = []
                while True:
                    line = fcache.readline()
                    if len(line) == 0:
                        break
                    (request_id, package, revision, empty) = line.split(';', 4)

                    if include_request_id:
                        retval.append((request_id, package))
                    else:
                        retval.append(package)

                fcache.close()
                return retval
            else:
                fcache.close()
                # don't return: we'll download again

        # no cache available
        cls._print_message()

        # download the data
        try:
            submitted_packages = get_submit_request_list(apiurl, project, None)
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Cannot get list of submissions to %s: %s' % (project, e.msg)
            return []

        lines = []
        retval = []
        for submitted in submitted_packages:
            if submitted.state.name != 'new':
                continue

            if include_request_id:
                retval.append((submitted.reqid, submitted.dst_package))
            else:
                retval.append(submitted.dst_package)

            lines.append('%s;%s;%s;' % (submitted.reqid, submitted.dst_package, submitted.src_md5))

        # save the data in the cache
        cls._write(filename, format_nb = current_format, lines_no_cr = lines)

        return retval


    @classmethod
    def _is_same_format(cls, format_line, format_nb):
        return format_line == cls._format_str + str(format_nb) + '\n'


    @classmethod
    def _write(cls, filename, format_nb = None, fin = None, lines = None, lines_no_cr = None):
        cachedir = cls._get_xdg_cache_dir()
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)

        if not os.path.isdir(cachedir):
            print >>sys.stderr, 'Cache directory %s is not a directory.' % cachedir
            return False

        cache = os.path.join(cachedir, filename)
        if os.path.exists(cache):
            os.unlink(cache)
        fout = open(cache, 'w')

        if not fin and lines == None and lines_no_cr == None:
            print >>sys.stderr, 'Internal error when saving a cache: no data.'
            return False

        if format_nb:
            fout.write('%s%s\n' % (cls._format_str, format_nb))

        if fin:
            while True:
                try:
                    bytes = fin.read(500 * 1024)
                    if len(bytes) == 0:
                        break
                    fout.write(bytes)
                except urllib2.HTTPError, e:
                    fout.close()
                    os.unlink(cache)
                    raise e
            fout.close()
            return True

        if lines:
            for line in lines:
                fout.write(line)
            fout.close()
            return True

        if lines_no_cr:
            for line in lines_no_cr:
                fout.write('%s\n' % line)
            fout.close()
            return True


#######################################################################


def _gnome_is_program_in_path(self, program):
    if not os.environ.has_key('PATH'):
        return False

    for path in os.environ['PATH'].split(':'):
        if os.path.exists(os.path.join(path, program)):
            return True

    return False


#######################################################################


# TODO: put this in a common library -- it's used in the examples too
def _gnome_compare_versions_a_gt_b(self, a, b):
    rpm = self.OscGnomeImport.m_import('rpm')
    if rpm:
        # We're not really interested in the epoch or release parts of the
        # complete version because they're not relevant when comparing to
        # upstream version
        return rpm.labelCompare((None, a, '1'), (None, b, '1')) > 0

    split_a = a.split('.')
    split_b = b.split('.')

    # the two versions don't have the same format; we don't know how to handle
    # this
    if len(split_a) != len(split_b):
        return a > b

    for i in range(len(split_a)):
        try:
            int_a = int(split_a[i])
            int_b = int(split_b[i])
            if int_a > int_b:
                return True
        except ValueError:
            if split_a[i] > split_b[i]:
                return True

    return False


def _gnome_needs_update(self, parent_version, devel_version, upstream_version):
    return self._gnome_compare_versions_a_gt_b(upstream_version, parent_version) and self._gnome_compare_versions_a_gt_b(upstream_version, devel_version)


def _gnome_is_submitted(self, package, submitted_packages):
    return package in submitted_packages


#######################################################################


def _gnome_table_get_maxs(self, init, list):
    if len(list) == 0:
        return ()

    nb_maxs = len(init)
    maxs = []
    for i in range(nb_maxs):
        maxs.append(len(init[i]))

    for item in list:
        for i in range(nb_maxs):
            maxs[i] = max(maxs[i], len(item[i]))

    return tuple(maxs)


def _gnome_table_get_template(self, *args):
    if len(args) == 0:
        return ''

    template = '%%-%d.%ds' % (args[0], args[0])
    index = 1

    while index < len(args):
        template = template + (' | %%-%d.%ds' % (args[index], args[index]))
        index = index + 1

    return template


def _gnome_table_print_header(self, template, title):
    if len(title) == 0:
        return

    dash_template = template.replace(' | ', '-+-')

    very_long_dash = ('--------------------------------------------------------------------------------',)
    dashes = ()
    for i in range(len(title)):
        dashes = dashes + very_long_dash

    print template % title
    print dash_template % dashes


#######################################################################


def _gnome_todo_internal(self, apiurl, project, exclude_reserved, exclude_submitted):
    # get all versions of packages
    try:
        (parent_project, packages_versions) = self._gnome_web.get_project_details(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return ('', [])

    # get the list of reserved package
    try:
        reserved_packages = self._gnome_web.get_reserved_packages(return_username = False)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg

    # get the packages submitted
    submitted_packages = self.GnomeCache.get_obs_submit_request_list(apiurl, project)

    lines = []

    for (package, parent_version, devel_version, upstream_version) in packages_versions:
        # empty upstream version or upstream version meaning openSUSE is
        # upstream
        if upstream_version == '' or upstream_version == '--':
            continue

        if self._gnome_needs_update(parent_version, devel_version, upstream_version):
            if self._gnome_is_submitted(package, submitted_packages):
                if exclude_submitted:
                    continue
                devel_version += ' (s)'
                upstream_version += ' (s)'
            if package in reserved_packages:
                if exclude_reserved:
                    continue
                upstream_version += ' (r)'
            lines.append((package, parent_version, devel_version, upstream_version))


    return (parent_project, lines)


#######################################################################


def _gnome_todo(self, apiurl, projects, exclude_reserved, exclude_submitted):
    lines = []
    parent_project = None

    for project in projects:
        (new_parent_project, project_lines) = self._gnome_todo_internal(apiurl, project, exclude_reserved, exclude_submitted)
        lines.extend(project_lines)
        if parent_project == None:
            parent_project = new_parent_project
        elif parent_project != new_parent_project:
            parent_project = 'Parent Project'

    if len(lines) == 0:
        print 'Nothing to do.'
        return

    # the first element in the tuples is the package name, so it will sort
    # the lines the right way for what we want
    lines.sort()

    if len(projects) == 1:
        project_header = projects[0]
    else:
        project_header = "Devel Project"
    # print headers
    title = ('Package', parent_project, project_header, 'Upstream')
    (max_package, max_oF, max_devel, max_upstream) = self._gnome_table_get_maxs(title, lines)
    # trim to a reasonable max
    max_package = min(max_package, 48)
    max_version = min(max(max(max_oF, max_devel), max_upstream), 20)

    print_line = self._gnome_table_get_template(max_package, max_version, max_version, max_version)
    self._gnome_table_print_header(print_line, title)
    for line in lines:
        print print_line % line


#######################################################################


def _gnome_get_packages_with_bad_meta(self, apiurl, project):
    # get the list of packages that are actually in project
    try:
        (parent_project, packages_versions) = self._gnome_web.get_project_details(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return (None, None)

    # no parent, then no bad meta :-)
    if not parent_project:
        return (None, None)

    # get metadata from the parent project to be able to know if packages
    # shouldn't belong there
    metafile = self.GnomeCache.get_obs_meta(apiurl, parent_project)
    if not metafile:
        return (None, None)

    try:
        collection = ET.parse(metafile).getroot()
    except SyntaxError:
        print >>sys.stderr, 'Cannot parse %s: %s' % (metafile, e.msg)
        return (None, None)

    devel_dict = {}
    # list of packages that should exist in project but that don't
    bad_devel_packages = []
    # list of packages that exist in project but that shouldn't
    should_devel_packages = []

    # save all packages that should be in project and also create a db of
    # package->develproject
    for package in collection.findall('package'):
        name = package.get('name')
        devel = package.find('devel')
        if devel != None:
            devel_project = devel.get('project')
        else:
            devel_project = ''

        devel_dict[name] = devel_project
        if devel_project == project:
            should_devel_packages.append(name)

    # now really create the list of packages that should be in project and
    # create the list of packages that shouldn't stay in project
    for (package, parent_version, devel_version, upstream_version) in packages_versions:
        if package in should_devel_packages:
            should_devel_packages.remove(package)
        if not devel_dict.has_key(package):
            # FIXME: this should be not-in-parent error, in create-database
            # test-case right now: compiz-fusion-plugins-unsupported
            continue
        devel_project = devel_dict[package]
        if devel_project != project:
            bad_devel_packages.append((package, devel_project))

    bad_devel_packages.sort()
    should_devel_packages.sort()

    return (bad_devel_packages, should_devel_packages)


#######################################################################


def _gnome_min_package(self, packages):
    min_package = None
    for package in packages:
        if package:
            if min_package:
                min_package = min(package, min_package)
            else:
                min_package = package

    return min_package


def _gnome_todoadmin_internal(self, apiurl, project, exclude_submitted):
    def _message_delta_package(delta_package, submitted_from_packages, parent_project):
        if not parent_project:
            return None

        if self._gnome_is_submitted(delta_package, submitted_from_packages):
            if exclude_submitted:
                return None
            message = 'Waits for approval in %s queue' % parent_project
        else:
            message = 'Needs to be submitted to %s' % parent_project
        return message

    def _message_error_package(error_package_tuple, parent_project):
        (error_package, error, details) = error_package_tuple

        # we use this variable in cases where it should always be set, but to
        # be on the safe side, we fallback to a generic name
        if not parent_project:
            parent_project = 'parent project'

        if error == 'not-link':
            message = 'Is not a link to %s' % parent_project
        elif error == 'not-in-parent':
            message = 'Does not exist in %s' % parent_project
        elif error == 'need-merge-with-parent':
            message = 'Requires a manual merge with %s' % parent_project
        else:
            if details:
                message = 'Unknown error: %s' % details
            else:
                message = 'Unknown error'
        return message


    # get packages with a delta
    try:
        packages_with_delta = self._gnome_web.get_packages_with_delta(project)
        packages_with_errors = self._gnome_web.get_packages_with_error(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return []

    (parent_project, packages_versions) = self._gnome_web.get_project_details(project)

    # get the packages submitted from
    if parent_project:
        submitted_from_packages = self.GnomeCache.get_obs_submit_request_list(apiurl, parent_project)
    else:
        submitted_from_packages = []

    # get the packages with no upstream data
    no_upstream_packages = []
    for (package, parent_version, devel_version, upstream_version) in packages_versions:
        if upstream_version == '':
            no_upstream_packages.append(package)

    # get the packages submitted to, which need a review
    submitted_to_packages = self.GnomeCache.get_obs_submit_request_list(apiurl, project, include_request_id=True)
    # get errors
    (bad_devel_packages, should_devel_packages) = self._gnome_get_packages_with_bad_meta(apiurl, project)

    lines = []

    # We try to make the processing the the loop below more automatic, so it's
    # easy to add a new source of messages.
    # The items in this array contain:
    #  + name of the set,
    #  + array
    #  + current index in the array from this set,
    #  + length of the array of this set,
    #  + if the items in the array of this set are tuples and if yes, which
    #    item in the tuple is the package name
    #  + a function to generate the message for this package
    # Note that the order in this array also gives priority: if a package is
    # in two sets, the first set wins.
    package_data_sets = []
    package_data_sets.append(['should_devel', should_devel_packages, 0, len(should_devel_packages), -1,
                              lambda prj, pkg, tpl: 'Does not exist in %s while it should' % prj])
    package_data_sets.append(['bad_devel', bad_devel_packages, 0, len(bad_devel_packages), 0,
                              lambda prj, pkg, tpl: 'Development project is not %s (%s)' % (prj, tpl[1])])
    package_data_sets.append(['error', packages_with_errors, 0, len(packages_with_errors), 0,
                              lambda prj, pkg, tpl: _message_error_package(tpl, parent_project)])
    package_data_sets.append(['submitted_to', submitted_to_packages, 0, len(submitted_to_packages), 1,
                              lambda prj, pkg, tpl: 'Needs to be reviewed (submission id: %s)' % tpl[0]])
    package_data_sets.append(['delta', packages_with_delta, 0, len(packages_with_delta), -1,
                              lambda prj, pkg, tpl: _message_delta_package(pkg, submitted_from_packages, parent_project)])
    package_data_sets.append(['no_upstream_data', no_upstream_packages, 0, len(no_upstream_packages), -1,
                              lambda prj, pkg, tpl: 'No upstream data available'])

    # This is an ugly loop to merge all the lists we have to get an output
    # in alphabetical order AND also to not have more than one message for
    # one given package.
    while True:
        current_packages = {}
        current_tuples = {}
        for data_set in package_data_sets:
            name = data_set[0]
            array = data_set[1]
            index = data_set[2]
            max = data_set[3]
            tuple_index = data_set[4]

            if index >= max:
                current_packages[name] = None
            else:
                if tuple_index == -1:
                    current_packages[name] = array[index]
                    current_tuples[name] = None
                else:
                    current_packages[name] = array[index][tuple_index]
                    current_tuples[name] = array[index]

        package = self._gnome_min_package(current_packages.values())

        if not package:
            break

        line_added = False

        for data_set in package_data_sets:
            name = data_set[0]
            message_func = data_set[5]

            # the package is not from this data set
            if package != current_packages[name]:
                continue

            # we're done with this package in this set
            data_set[2] += 1

            # if we already added a line for this package,
            # just skip it in this data set
            if line_added:
                continue

            message = message_func(project, package, current_tuples[name])
            # sometime, we might ignore a specific message, depending on the
            # configuration (eg, do not show submitted packages)
            if not message:
                continue

            lines.append((package, message))
            line_added = True


    return lines


#######################################################################


def _gnome_todoadmin(self, apiurl, projects, exclude_submitted):
    lines = []

    for project in projects:
        project_lines = self._gnome_todoadmin_internal(apiurl, project, exclude_submitted)
        lines.extend(project_lines)

    if len(lines) == 0:
        print 'Nothing to do.'
        return

    # the first element in the tuples is the package name, so it will sort
    # the lines the right way for what we want
    lines.sort()

    # print headers
    title = ('Package', 'Details')
    (max_package, max_details) = self._gnome_table_get_maxs(title, lines)
    # trim to a reasonable max
    max_package = min(max_package, 48)
    max_details = min(max_details, 65)

    print_line = self._gnome_table_get_template(max_package, max_details)
    self._gnome_table_print_header(print_line, title)
    for line in lines:
        print print_line % line


#######################################################################


def _gnome_listreserved(self):
    try:
        reserved_packages = self._gnome_web.get_reserved_packages()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    if len(reserved_packages) == 0:
        print 'No package reserved.'
        return

    # print headers
    title = ('Package', 'Reserved by')
    (max_package, max_username) = self._gnome_table_get_maxs(title, reserved_packages)
    # trim to a reasonable max (less than 80 characters wide)
    max_package = min(max_package, 48)
    max_username = min(max_username, 28)

    print_line = self._gnome_table_get_template(max_package, max_username)
    self._gnome_table_print_header(print_line, title)

    for (package, username) in reserved_packages:
        if (package and username):
            print print_line % (package, username)


#######################################################################


def _gnome_isreserved(self, package):
    try:
        username = self._gnome_web.is_package_reserved(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    if not username:
        print 'Package is not reserved.'
    else:
        print 'Package %s is reserved by %s.' % (package, username)


#######################################################################


def _gnome_reserve(self, packages, username):
    for package in packages:
        try:
            self._gnome_web.reserve_package(package, username)
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            continue

        print 'Package %s reserved for 36 hours.' % package
        print 'Do not forget to unreserve the package when done with it:'
        print '    osc gnome unreserve %s' % package


#######################################################################


def _gnome_unreserve(self, packages, username):
    for package in packages:
        try:
            self._gnome_web.unreserve_package(package, username)
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            continue

        print 'Package %s unreserved.' % package


#######################################################################


def _gnome_setup_internal(self, apiurl, username, project, package, ignore_reserved = False, no_reserve = False):
    # is it reserved?
    try:
        reserved_by = self._gnome_web.is_package_reserved(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return False

    # package already reserved, but not by us
    if reserved_by and reserved_by != username:
        if not ignore_reserved:
            print 'Package %s is already reserved by %s.' % (package, reserved_by)
            return False
        else:
            print 'WARNING: package %s is already reserved by %s.' % (package, reserved_by)
    # package not reserved
    elif not reserved_by and not no_reserve:
        try:
            self._gnome_web.reserve_package(package, username)
            print 'Package %s has been reserved for 36 hours.' % package
            print 'Do not forget to unreserve the package when done with it:'
            print '    osc gnome unreserve %s' % package
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            if not ignore_reserved:
                return False

    # look if we already have a branch, and if not branch the package
    try:
        expected_branch_project = 'home:%s:branches:%s' % (username, project)
        show_package_meta(apiurl, expected_branch_project, package)
        branch_project = expected_branch_project
        # it worked, we already have the branch
    except urllib2.HTTPError, e:
        if e.code != 404:
            print >>sys.stderr, 'Error while checking if package %s was already branched: %s' % (package, e.msg)
            return False
        # We had a 404: it means the branched package doesn't exist yet
        try:
            branch_project = branch_pkg(apiurl, project, package, nodevelproject = True)
            print 'Package %s has been branched in project %s.' % (package, branch_project)
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Error while branching package %s: %s' % (package, e.msg)
            return False

    # check out the branched package
    if os.path.exists(package):
        # maybe we already checked it out before?
        if not os.path.isdir(package):
            print >>sys.stderr, 'File %s already exists but is not a directory.' % package
            return False
        elif not is_package_dir(package):
            print >>sys.stderr, 'Directory %s already exists but is not a checkout of a Build Service package.' % package
            return False

        obs_package = filedir_to_pac(package)
        if obs_package.name != package or obs_package.prjname != branch_project:
            print >>sys.stderr, 'Directory %s already exists but is a checkout of package %s from project %s.' % (package, obs_package.name, obs_package.prjname)
            return False

        if self._gnome_osc_package_pending_commit(obs_package):
            print >>sys.stderr, 'Directory %s contains some uncommitted changes.' % (package,)
            return False

        # update the package
        try:
            # we specify the revision so that it gets expanded
            # the logic comes from do_update in commandline.py
            rev = None
            if obs_package.islink() and not obs_package.isexpanded():
                rev = obs_package.linkinfo.xsrcmd5
            elif obs_package.islink() and obs_package.isexpanded():
                rev = show_upstream_xsrcmd5(apiurl, branch_project, package)

            obs_package.update(rev)
            print 'Package %s has been updated.' % package
        except Exception, e:
            message = 'Error while updating package %s: ' % package
            self._gnome_exception_print(e, message)
            return False

    else:
        # check out the branched package
        try:
            checkout_package(apiurl, branch_project, package, expand_link=True)
            print 'Package %s has been checked out.' % package
        except Exception, e:
            message = 'Error while checking out package %s: ' % package
            self._gnome_exception_print(e, message)
            return False

    return True


#######################################################################


def _gnome_get_project_for_package(self, apiurl, projects, package, return_all = False):
    # first check the database: this check should be faster than checking
    # via the build service
    for project in projects:
        try:
            (parent_project, parent_version, devel_version, upstream_version) = self._gnome_web.get_package_details(project, package)
            # if we get a result, then package exists in project
            if parent_version != None:
                if return_all:
                    return (parent_project, project, parent_version, devel_version, upstream_version)
                else:
                    return project
        except self.OscGnomeWebError, e:
            continue

    # if we need all info, the build service can't help us, so we can fail now
    if return_all:
        return (None, None, '', '', '')

    # no result via the database, so go directly to the build service
    for project in projects:
        try:
            show_package_meta(apiurl, project, package)
            # no exception means no 404, and therefore "okay"
            return project
        except urllib2.HTTPError, e:
            continue

    return None


#######################################################################


def _gnome_setup(self, apiurl, username, projects, package, ignore_reserved = False, no_reserve = False):
    if len(projects) == 1:
        project = projects[0]
    else:
        project = self._gnome_get_project_for_package(apiurl, projects, package)
        if project == None:
            print >>sys.stderr, 'Cannot find an appropriate project containing %s. You can use --project to override your project settings.' % package
            return

    if not self._gnome_setup_internal(apiurl, username, project, package, ignore_reserved, no_reserve):
        return
    print 'Package %s has been prepared for work.' % package


#######################################################################


def _gnome_download_internal(self, url, dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    urlparse = self.OscGnomeImport.m_import('urlparse')
    if not urlparse:
        raise self.OscGnomeDownloadError('Cannot download %s: incomplete python installation.' % url)

    parsed_url = urlparse.urlparse(url)
    basename = os.path.basename(parsed_url.path)
    if basename == '':
        raise self.OscGnomeDownloadError('Cannot download %s: no basename in URL.' % url)

    dest_file = os.path.join(dest_dir, basename)
    # we download the file again if it already exists. Maybe the upstream
    # tarball changed, eg. We could add an option to avoid this, but I feel
    # like it won't happen a lot anyway.
    if os.path.exists(dest_file):
        os.unlink(dest_file)

    try:
        fin = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        raise self.OscGnomeDownloadError('Cannot download %s: %s' % (url, e.msg))

    fout = open(dest_file, 'wb')

    while True:
        try:
            bytes = fin.read(500 * 1024)
            if len(bytes) == 0:
                break
            fout.write(bytes)
        except urllib2.HTTPError, e:
            fin.close()
            fout.close()
            os.unlink(dest_file)
            raise self.OscGnomeDownloadError('Error while downloading %s: %s' % (url, e.msg))

    fin.close()
    fout.close()

    return dest_file


#######################################################################


def _gnome_extract_news_internal(self, directory, old_tarball, new_tarball):
    def _cleanup(old, new, tmpdir):
        if old:
            old.close()
        if new:
            new.close()
        shutil.rmtree(tmpdir)

    # we need to make sure it's safe to extract the file
    # see the warning in http://www.python.org/doc/lib/tarfile-objects.html
    def _can_extract_with_trust(name):
        if not name:
            return False
        if name[0] == '/':
            return False
        if name[0] == '.':
            # only accept ./ if the first character is a dot
            if len(name) == 1 or name[1] != '/':
                return False

        return True

    def _extract_files(tar, path, whitelist):
        if not tar or not path or not whitelist:
            return

        for tarinfo in tar:
            if not _can_extract_with_trust(tarinfo.name):
                continue
            # we won't accept symlinks or hard links. It sounds weird to have
            # this for the files we're interested in.
            if not tarinfo.isfile():
                continue
            basename = os.path.basename(tarinfo.name)
            if not basename in whitelist:
                continue
            tar.extract(tarinfo, path)

    def _diff_files(old, new, dest):
        difflib = self.OscGnomeImport.m_import('difflib')
        shutil = self.OscGnomeImport.m_import('shutil')

        if not new:
            return (False, False)
        if not old:
            shutil.copyfile(new, dest)
            return (True, False)

        old_f = open(old)
        old_lines = old_f.readlines()
        old_f.close()
        new_f = open(new)
        new_lines = new_f.readlines()
        new_f.close()

        diff = difflib.unified_diff(old_lines, new_lines)

        dest_f = open(dest, 'w')

        # We first write what we consider useful and then write the complete
        # diff for reference.
        # This works because a well-formed NEWS/ChangeLog will only have new
        # items added at the top, and therefore the useful diff is the addition
        # at the top.
        # We need to cache the first lines, though, since diff is a generator
        # and we don't have direct access to lines.

        i = 0
        pass_one_done = False
        cached = []

        for line in diff:
            # we skip the first three lines of the diff
            if not pass_one_done and i == 0 and line[:3] == '---':
                cached.append(line)
                i = 1
            elif not pass_one_done and i == 1 and line[:3] == '+++':
                cached.append(line)
                i = 2
            elif not pass_one_done and i == 2 and line[:2] == '@@':
                cached.append(line)
                i = 3
            elif not pass_one_done and i == 3 and line[0] == '+':
                cached.append(line)
                dest_f.write(line[1:])
            elif not pass_one_done:
                # end of pass one: we write a note to help the user, and then
                # write the cache
                pass_one_done = True
                dest_f.write('\n')
                dest_f.write('#############################################################\n')
                dest_f.write('# Note by osc gnome: here is the complete diff for reference.\n')
                dest_f.write('#############################################################\n')
                dest_f.write('\n')
                for cached_line in cached:
                    dest_f.write(cached_line)
                dest_f.write(line)
            else:
                dest_f.write(line)

        dest_f.close()

        return (True, True)


    tempfile = self.OscGnomeImport.m_import('tempfile')
    shutil = self.OscGnomeImport.m_import('shutil')
    tarfile = self.OscGnomeImport.m_import('tarfile')
    difflib = self.OscGnomeImport.m_import('difflib')

    if not tempfile or not shutil or not tarfile or not difflib:
        raise self.OscGnomeNewsError('Cannot extract NEWS information: incomplete python installation.')

    tmpdir = tempfile.mkdtemp(prefix = 'osc-gnome-')

    old = None
    new = None

    if old_tarball and os.path.exists(old_tarball):
        try:
            old = tarfile.open(old_tarball)
        except tarfile.TarError:
            pass
    else:
        # this is not fatal: we can provide the NEWS/ChangeLog from the new
        # tarball without a diff
        pass

    if new_tarball and os.path.exists(new_tarball):
        new_tarball_basename = os.path.basename(new_tarball)
        try:
            new = tarfile.open(new_tarball)
        except tarfile.TarError, e:
            _cleanup(old, new, tmpdir)
            raise self.OscGnomeNewsError('Error when opening %s: %s' % (new_tarball_basename, e))
    else:
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: no new tarball.')

    # make sure we have at least a subdirectory in tmpdir, since we'll extract
    # files from two tarballs that might conflict
    old_dir = os.path.join(tmpdir, 'old')
    new_dir = os.path.join(tmpdir, 'new')

    try:
        if old:
            err_tarball = os.path.basename(old_tarball)
            _extract_files (old, old_dir, ['NEWS', 'ChangeLog'])

        err_tarball = new_tarball_basename
        _extract_files (new, new_dir, ['NEWS', 'ChangeLog'])
    except (tarfile.ReadError, EOFError):
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: %s is not a valid tarball.' % err_tarball)

    if old:
        old.close()
        old = None
    if new:
        new.close()
        new = None

    # find toplevel NEWS & ChangeLog in the new tarball
    if not os.path.exists(new_dir):
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: no relevant files found in %s.' % new_tarball_basename)

    new_dir_files = os.listdir(new_dir)
    if len(new_dir_files) != 1:
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: unexpected file hierarchy in %s.' % new_tarball_basename)

    new_subdir = os.path.join(new_dir, new_dir_files[0])
    if not os.path.isdir(new_subdir):
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: unexpected file hierarchy in %s.' % new_tarball_basename)

    new_news = os.path.join(new_subdir, 'NEWS')
    if not os.path.exists(new_news) or not os.path.isfile(new_news):
        new_news = None
    new_changelog = os.path.join(new_subdir, 'ChangeLog')
    if not os.path.exists(new_changelog) or not os.path.isfile(new_changelog):
        new_changelog = None

    if not new_news and not new_changelog:
        _cleanup(old, new, tmpdir)
        raise self.OscGnomeNewsError('Cannot extract NEWS information: no relevant files found in %s.' % new_tarball_basename)

    # find toplevel NEWS & ChangeLog in the old tarball
    # not fatal
    old_news = None
    old_changelog = None

    if os.path.exists(old_dir):
        old_dir_files = os.listdir(old_dir)
    else:
        old_dir_files = []

    if len(old_dir_files) == 1:
        old_subdir = os.path.join(old_dir, old_dir_files[0])
        if os.path.isdir(old_subdir):
            old_news = os.path.join(old_subdir, 'NEWS')
            if not os.path.exists(old_news) or not os.path.isfile(old_news):
                old_news = None
            old_changelog = os.path.join(old_subdir, 'ChangeLog')
            if not os.path.exists(old_changelog) or not os.path.isfile(old_changelog):
                old_changelog = None

    # do the diff
    news = os.path.join(directory, 'osc-gnome.NEWS')
    (news_created, news_is_diff) = _diff_files(old_news, new_news, news)
    changelog = os.path.join(directory, 'osc-gnome.ChangeLog')
    (changelog_created, changelog_is_diff) = _diff_files(old_changelog, new_changelog, changelog)

    # Note: we make osc ignore those osc-gnome.* file we created by modifying
    # the exclude list of osc.core. See the top of this file.

    _cleanup(old, new, tmpdir)

    return (news, news_created, news_is_diff, changelog, changelog_created, changelog_is_diff)


#######################################################################


def _gnome_gz_to_bz2_internal(self, file):
    if file.endswith('.gz'):
        dest_file = file[:-3] + '.bz2'
    elif file.endswith('.tgz'):
        dest_file = file[:-4] + '.tar.bz2'
    else:
        raise self.OscGnomeCompressError('Cannot recompress %s as bz2: filename not ending with .gz.' % os.path.basename(file))

    gzip = self.OscGnomeImport.m_import('gzip')
    bz2 = self.OscGnomeImport.m_import('bz2')

    if not gzip or not bz2:
        raise self.OscGnomeCompressError('Cannot recompress %s as bz2: incomplete python installation.' % os.path.basename(file))

    if os.path.exists(dest_file):
        os.unlink(dest_file)

    fin = gzip.open(file)
    fout = bz2.BZ2File(dest_file, 'wb')

    while True:
        bytes = fin.read(500 * 1024)
        if len(bytes) == 0:
            break
        fout.write(bytes)

    fin.close()
    fout.close()

    os.unlink(file)
    return dest_file


#######################################################################


def _gnome_update_spec(self, spec_file, upstream_version):
    if not os.path.exists(spec_file):
        print >>sys.stderr, 'Cannot update %s: no such file.' % os.path.basename(spec_file)
        return (False, None)
    elif not os.path.isfile(spec_file):
        print >>sys.stderr, 'Cannot update %s: not a regular file.' % os.path.basename(spec_file)
        return (False, None)

    tempfile = self.OscGnomeImport.m_import('tempfile')
    re = self.OscGnomeImport.m_import('re')

    if not tempfile or not re:
        print >>sys.stderr, 'Cannot update %s: incomplete python installation.' % os.path.basename(spec_file)
        return (False, None)

    re_spec_header = re.compile('^(# spec file for package \S* \(Version )\S*(\).*)', re.IGNORECASE)
    re_spec_name = re.compile('^Name:\s*(\S*)', re.IGNORECASE)
    re_spec__name = re.compile('^%define\s+_name\s+(\S*)', re.IGNORECASE)
    re_spec_version = re.compile('^(Version:\s*)(\S*)', re.IGNORECASE)
    re_spec_release = re.compile('^(Release:\s*)\S*', re.IGNORECASE)
    re_spec_source = re.compile('^Source0?:\s*(\S*)', re.IGNORECASE)
    re_spec_prep = re.compile('^%prep', re.IGNORECASE)

    name = None
    _name = None
    old_version = None
    old_source = None

    fin = open(spec_file, 'r')
    (fdout, tmp) = tempfile.mkstemp(dir = os.path.dirname(spec_file))

    # replace version and reset release
    while True:
        line = fin.readline()
        if len(line) == 0:
            break

        match = re_spec_prep.match(line)
        if match:
            os.write(fdout, line)
            break

        match = re_spec_header.match(line)
        if match:
            os.write(fdout, '%s%s%s\n' % (match.group(1), upstream_version, match.group(2)))
            continue

        match = re_spec_name.match(line)
        if match:
            name = os.path.basename(match.group(1))
            os.write(fdout, line)
            continue

        match = re_spec__name.match(line)
        if match:
            _name = os.path.basename(match.group(1))
            os.write(fdout, line)
            continue

        match = re_spec_version.match(line)
        if match:
            old_version = match.group(2)
            os.write(fdout, '%s%s\n' % (match.group(1), upstream_version))
            continue

        match = re_spec_release.match(line)
        if match:
            os.write(fdout, '%s1\n' % match.group(1))
            continue

        match = re_spec_source.match(line)
        if match:
            old_source = os.path.basename(match.group(1))
            os.write(fdout, line)
            continue

        os.write(fdout, line)

    # wild read/write to finish quickly
    while True:
        bytes = fin.read(10 * 1024)
        if len(bytes) == 0:
            break
        os.write(fdout, bytes)

    fin.close()
    os.close(fdout)

    os.rename(tmp, spec_file)

    if old_version == upstream_version:
        old_source = None
    elif old_source:
        if name:
            old_source = old_source.replace('%{name}', name)
            old_source = old_source.replace('%name', name)
        if _name:
            old_source = old_source.replace('%{_name}', _name)
            old_source = old_source.replace('%_name', _name)
        if old_version:
            old_source = old_source.replace('%{version}', old_version)
            old_source = old_source.replace('%version', old_version)

    return (True, old_source)


#######################################################################


def _gnome_update_changes(self, changes_file, upstream_version, email):
    if not os.path.exists(changes_file):
        print >>sys.stderr, 'Cannot update %s: no such file.' % os.path.basename(changes_file)
        return False
    elif not os.path.isfile(changes_file):
        print >>sys.stderr, 'Cannot update %s: not a regular file.' % os.path.basename(changes_file)
        return False

    tempfile = self.OscGnomeImport.m_import('tempfile')
    time = self.OscGnomeImport.m_import('time')
    locale = self.OscGnomeImport.m_import('locale')

    if not tempfile or not time or not locale:
        print >>sys.stderr, 'Cannot update %s: incomplete python installation.' % os.path.basename(changes_file)
        return False

    (fdout, tmp) = tempfile.mkstemp(dir = os.path.dirname(changes_file))

    old_lc_time = locale.setlocale(locale.LC_TIME)
    old_tz = os.getenv('TZ')
    locale.setlocale(locale.LC_TIME, 'C')
    os.putenv('TZ', 'Europe/Paris')

    os.write(fdout, '-------------------------------------------------------------------\n')
    os.write(fdout, '%s - %s\n' % (time.strftime("%a %b %e %H:%M:%S %Z %Y"), email))
    os.write(fdout, '\n')
    os.write(fdout, '- Update to version %s:\n' % upstream_version)
    os.write(fdout, '  + \n')
    os.write(fdout, '\n')

    locale.setlocale(locale.LC_TIME, old_lc_time)
    if old_tz:
        os.putenv('TZ', old_tz)
    else:
        os.unsetenv('TZ')

    fin = open(changes_file, 'r')
    while True:
        bytes = fin.read(10 * 1024)
        if len(bytes) == 0:
            break
        os.write(fdout, bytes)
    fin.close()
    os.close(fdout)

    os.rename(tmp, changes_file)

    return True


#######################################################################


def _gnome_quilt_package(self, package, spec_file):
    def _cleanup(null, tmpdir):
        null.close()
        shutil.rmtree(tmpdir)

    subprocess = self.OscGnomeImport.m_import('subprocess')
    shutil = self.OscGnomeImport.m_import('shutil')
    tempfile = self.OscGnomeImport.m_import('tempfile')

    if not subprocess or not shutil or not tempfile:
        print >>sys.stderr, 'Cannot try to apply patches: incomplete python installation.'
        return False

    null = open('/dev/null', 'w')
    tmpdir = tempfile.mkdtemp(prefix = 'osc-gnome-')


    # setup with quilt
    sourcedir = os.path.dirname(os.path.realpath(spec_file))
    popen = subprocess.Popen(['quilt', 'setup', '-d', tmpdir, '--sourcedir', sourcedir, spec_file], stdout = null, stderr = null)
    retval = popen.wait()

    if retval != 0:
        _cleanup(null, tmpdir)
        print >>sys.stderr, 'Cannot apply patches: \'quilt setup\' failed.'
        return False


    # apply patches for all subdirectories
    for directory in os.listdir(tmpdir):
        dir = os.path.join(tmpdir, directory)

        if not os.path.isdir(dir):
            continue

        # there's no patch, so just continue
        if not os.path.exists(os.path.join(dir, 'patches')):
            continue

        popen = subprocess.Popen(['quilt', 'push', '-a', '-q'], cwd = dir, stdout = null, stderr = null)
        retval = popen.wait()

        if retval != 0:
            _cleanup(null, tmpdir)
            print >>sys.stderr, 'Cannot apply patches: \'quilt push -a\' failed.'
            return False


    _cleanup(null, tmpdir)

    return True


#######################################################################


def _gnome_update(self, apiurl, username, email, projects, package, ignore_reserved = False, no_reserve = False):
    if len(projects) == 1:
        project = projects[0]

        try:
            (parent_project, parent_version, devel_version, upstream_version) = self._gnome_web.get_package_details(project, package)
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            return
    else:
        (parent_project, project, parent_version, devel_version, upstream_version) = self._gnome_get_project_for_package(apiurl, projects, package, return_all = True)
        if project == None:
            print >>sys.stderr, 'Cannot find an appropriate project containing %s. You can use --project to override your project settings.' % package
            return


    if parent_project:
        # check that the project is up-to-date wrt parent project
        if self._gnome_compare_versions_a_gt_b(parent_version, devel_version):
            # TODO, actually we can do a better check than that with the delta API
            print 'Package %s is more recent in %s (%s) than in %s (%s). Please synchronize %s first.' % (package, parent_project, parent_version, project, devel_version, project)
            return

    # check that an update is really needed
    if upstream_version == '':
        print 'No information about upstream version of package %s is available. Assuming it is not up-to-date.' % package
    elif not self._gnome_needs_update(parent_version, devel_version, upstream_version):
        print 'Package %s is already up-to-date.' % package
        return

    if not self._gnome_setup_internal(apiurl, username, project, package, ignore_reserved, no_reserve):
        return

    package_dir = package

    # edit the version tag in the .spec files
    # not fatal if fails
    spec_file = os.path.join(package_dir, package + '.spec')
    (updated, old_tarball) = self._gnome_update_spec(spec_file, upstream_version)
    if old_tarball:
        old_tarball_with_dir = os.path.join(package_dir, old_tarball)
    else:
        old_tarball_with_dir = None

    if updated:
        print '%s has been prepared.' % os.path.basename(spec_file)

    # warn if there are other spec files which might need an update
    for file in os.listdir(package_dir):
        if file.endswith('.spec') and file != os.path.basename(spec_file):
            print 'WARNING: %s might need a manual update.' % file


    # start adding an entry to .changes
    # not fatal if fails
    changes_file = os.path.join(package_dir, package + '.changes')
    if self._gnome_update_changes(changes_file, upstream_version, email):
        print '%s has been prepared.' % os.path.basename(changes_file)

    # warn if there are other spec files which might need an update
    for file in os.listdir(package_dir):
        if file.endswith('.changes') and file != os.path.basename(changes_file):
            print 'WARNING: %s might need a manual update.' % file


    # download the upstream tarball
    # fatal if fails
    try:
        upstream_url = self._gnome_web.get_upstream_url(project, package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    if not upstream_url:
        print >>sys.stderr, 'Cannot download latest upstream tarball for %s: no URL defined.' % package
        return

    print 'Looking for the upstream tarball...'
    try:
        upstream_tarball = self._gnome_download_internal(upstream_url, package_dir)
    except self.OscGnomeDownloadError, e:
        print >>sys.stderr, e.msg
        return

    if not upstream_tarball:
        print >>sys.stderr, 'No upstream tarball downloaded for %s.' % package
        return
    else:
        upstream_tarball_basename = os.path.basename(upstream_tarball)
        print '%s has been downloaded.' % upstream_tarball_basename


    # check integrity of the downloaded file
    # fatal if fails (only if md5 exists)
    # TODO


    # extract NEWS & ChangeLog from the old + new tarballs, and do a diff
    # not fatal if fails
    print 'Finding NEWS and ChangeLog information...'
    try:
        (news, news_created, news_is_diff, changelog, changelog_created, changelog_is_diff) = self._gnome_extract_news_internal(package_dir, old_tarball_with_dir, upstream_tarball)
    except self.OscGnomeNewsError, e:
        print >>sys.stderr, e.msg
    else:
        if news_created:
            news_basename = os.path.basename(news)
            if news_is_diff:
                print 'NEWS between %s and %s is available in %s' % (old_tarball, upstream_tarball_basename, news_basename)
            else:
                print 'Complete NEWS of %s is available in %s' % (upstream_tarball_basename, news_basename)
        else:
            print 'No NEWS information found.'

        if changelog_created:
            changelog_basename = os.path.basename(changelog)
            if changelog_is_diff:
                print 'ChangeLog between %s and %s is available in %s' % (old_tarball, upstream_tarball_basename, changelog_basename)
            else:
                print 'Complete ChangeLog of %s is available in %s' % (upstream_tarball_basename, changelog_basename)
        else:
            print 'No ChangeLog information found.'


    # recompress as bz2
    # not fatal if fails
    if upstream_tarball.endswith('.gz') or upstream_tarball.endswith('.tgz'):
        try:
            old_upstream_tarball_basename = os.path.basename(upstream_tarball)
            upstream_tarball = self._gnome_gz_to_bz2_internal(upstream_tarball)
            print '%s has been recompressed to bz2.' % old_upstream_tarball_basename
            upstream_tarball_basename = os.path.basename(upstream_tarball)
        except self.OscGnomeCompressError, e:
            print >>sys.stderr, e.msg


    # try applying the patches with rpm quilt
    # not fatal if fails
    if self._gnome_is_program_in_path('quilt'):
        print 'Running quilt...'
        if self._gnome_quilt_package(package, spec_file):
            print 'Patches still apply.'
        else:
            print 'WARNING: make sure that all patches apply before submitting.'
    else:
        print 'quilt is not available.'
        print 'WARNING: make sure that all patches apply before submitting.'


    # 'osc add newfile.tar.bz2' and 'osc del oldfile.tar.bz2'
    # not fatal if fails
    osc_package = filedir_to_pac(package_dir)

    if old_tarball_with_dir:
        if os.path.exists(old_tarball_with_dir):
            osc_package.put_on_deletelist(old_tarball)
            osc_package.write_deletelist()
            osc_package.delete_source_file(old_tarball)
            print '%s has been removed from the package.' % old_tarball
        else:
            print 'WARNING: the previous tarball could not be found. Please manually remove it.'
    else:
        print 'WARNING: the previous tarball could not be found. Please manually remove it.'

    osc_package.addfile(upstream_tarball_basename)
    print '%s has been added to the package.' % upstream_tarball_basename


    print 'Package %s has been prepared for the update.' % package
    print 'After having updated %s, you can use \'osc build\' to start a local build or \'osc gnome build\' to start a build on the build service.' % os.path.basename(changes_file)

    # TODO add a note about checking if patches are still needed, buildrequires
    # & requires


#######################################################################


def _gnome_forward(self, apiurl, projects, request_id):
    try:
        int_request_id = int(request_id)
    except ValueError:
        print >>sys.stderr, '%s is not a valid submission request id.' % (request_id)
        return

    try:
        request = get_submit_request(apiurl, request_id)
    except urllib2.HTTPError:
        print >>sys.stderr, 'Cannot get submission request %s: %s' % (request_id, e.msg)

    if request.dst_project not in projects:
        if len(projects) == 1:
            print >>sys.stderr, 'Submission request %s is for %s and not %s. You can use --project to override your project settings.' % (request_id, request.dst_project, projects[0])
        else:
            print >>sys.stderr, 'Submission request %s is for %s. You can use --project to override your project settings.' % (request_id, request.dst_project)
        return

    if request.state.name != 'new':
        print >>sys.stderr, 'Submission request %s is not new.' % request_id
        return

    try:
        parent_project = self._gnome_web.get_project_parent(request.dst_project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, 'Cannot get parent project of %s.' % request.dst_project
        return

    try:
        devel_project = show_develproject(apiurl, parent_project, request.dst_package)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot get development project for %s: %s' % (request.dst_package, e.msg)
        return

    if devel_project != request.dst_project:
        print >>sys.stderr, 'Development project for %s is %s, but package has been submitted to %s' % (request.dst_package, request.dst_project, devel_project)
        return

    result = change_submit_request_state(apiurl, request_id, 'accepted', 'Forwarding to %s' % parent_project)
    root = ET.fromstring(result)
    if not 'code' in root.keys() or root.get('code') != 'ok':
        print >>sys.stderr, 'Cannot accept submission request %s: %s' % (request_id, result)
        return

    # TODO: cancel old requests from request.dst_project to parent project

    result = create_submit_request(apiurl,
                                   request.dst_project, request.dst_package,
                                   parent_project, request.dst_package,
                                   request.descr)

    print 'Submission request %s has been forwarded to %s (request id: %s).' % (request_id, parent_project, result)


#######################################################################


def _gnome_osc_package_pending_commit(self, osc_package):
    # ideally, we could use osc_package.todo, but it's not set by default.
    # So we just look at all files.
    for filename in osc_package.filenamelist + osc_package.filenamelist_unvers:
        status = osc_package.status(filename)
        if status in ['A', 'M', 'D']:
            return True

    return False


def _gnome_osc_package_commit(self, osc_package, msg):
    osc_package.commit(msg)
    # See bug #436932: Package.commit() leads to outdated internal data.
    osc_package.update_datastructs()


#######################################################################


def _gnome_package_set_meta(self, apiurl, project, package, meta, error_msg_prefix = ''):
    if error_msg_prefix:
        error_str = error_msg_prefix + ': %s'
    else:
        error_str = 'Cannot set metadata for %s in %s: %%s' % (package, project)

    tempfile = self.OscGnomeImport.m_import('tempfile')
    if not tempfile:
        print >>sys.stderr, error_str % 'incomplete python installation.'
        return False

    (fdout, tmp) = tempfile.mkstemp()
    os.write(fdout, meta)
    os.close(fdout)

    meta_url = make_meta_url('pkg', (quote_plus(project), quote_plus(package)), apiurl)

    failed = False
    try:
        http_PUT(meta_url, file=tmp)
    except urllib2.HTTPError, e:
        print >>sys.stderr, error_str % e.msg
        failed = True

    os.unlink(tmp)
    return not failed


def _gnome_enable_build(self, apiurl, project, package, meta, repo, archs):
    if len(archs) == 0:
        return (True, False)

    package_node = ET.XML(meta)
    meta_xml = ET.ElementTree(package_node)

    build_node = package_node.find('build')
    if not build_node:
        build_node = ET.Element('build')
        package_node.append(build_node)

    enable_found = {}
    for arch in archs:
        enable_found[arch] = False

    # remove disable before adding enable
    for node in build_node.findall('disable'):
        arch = node.get('arch')
        if arch in archs:
            build_node.remove(node)

    for node in build_node.findall('enable'):
        arch = node.get('arch')
        if enable_found.has_key(arch):
            enable_found[arch] = True

    for arch in archs:
        if not enable_found[arch]:
            node = ET.Element('enable', { 'repository': repo, 'arch': arch})
            build_node.append(node)

    all_true = True
    for value in enable_found.values():
        if not value:
            all_true = False
            break

    if all_true:
        return (True, False)

    buf = StringIO()
    meta_xml.write(buf)
    meta = buf.getvalue()

    if self._gnome_package_set_meta(apiurl, project, package, meta, 'Error while enabling build of package on the build service'):
        return (True, True)
    else:
        return (False, False)


def _gnome_get_latest_package_rev_built(self, apiurl, project, repo, arch, package, verbose_error = True):
    url = makeurl(apiurl, ['build', project, repo, arch, package, '_history'])

    try:
        history = http_GET(url)
    except urllib2.HTTPError, e:
        if verbose_error:
            print >>sys.stderr, 'Cannot get build history: %s' % e.msg
        return (False, None, None)

    root = ET.parse(history).getroot()

    max_time = 0
    rev = None
    srcmd5 = None

    for node in root.findall('entry'):
        t = int(node.get('time'))
        if t <= max_time:
            continue

        srcmd5 = node.get('srcmd5')
        rev = node.get('rev')

    return (True, srcmd5, rev)


def _gnome_print_build_status(self, repo, build_state, header, error_line, hint = False):
    print '%s:' % header

    keys = build_state.keys()
    if not keys or len(keys) == 0:
        print '  %s' % error_line
        return

    show_hint = False
    keys.sort()

    max_len = 0
    for key in keys:
        if len(key) > max_len:
            max_len = len(key)

    # 4: because we also have a few other characters (see left variable)
    format = '%-' + str(max_len + 4) + 's%s'
    for key in keys:
        if build_state[key]['result'] in ['failed']:
            show_hint = True

        left = '  %s: ' % key
        print format % (left, build_state[key]['result'])

    if show_hint and hint:
        for key in keys:
            if build_state[key]['result'] == 'failed':
                print 'You can see the log of the failed build with: osc buildlog %s %s' % (repo, key)


def _gnome_build_get_results(self, apiurl, project, repo, package, archs, srcmd5, rev, state, ignore_initial_errors, error_counter, verbose_error):
    time = self.OscGnomeImport.m_import('time')

    try:
        results = show_results_meta(apiurl, project, package=package)
        if len(results) == 0:
            if verbose_error:
                print >>sys.stderr, 'Error while getting build results of package on the build service: empty results'
            error_counter += 1
            return (True, False, error_counter, state)

        # reset the error counter
        error_counter = 0
    except urllib2.HTTPError, e:
        if verbose_error:
            print >>sys.stderr, 'Error while getting build results of package on the build service: %s' % e.msg
        error_counter += 1
        return (True, False, error_counter, state)

    res_root = ET.XML(''.join(results))
    results_per_arch = {}

    for node in res_root.findall('result'):

        buildrepo = node.get('repository')
        # ignore the repo if it's not the one we explicitly use
        if not buildrepo == repo:
           continue

        arch = node.get('arch')
        # ignore the archs we didn't explicitly enabled: this ensures we care
        # only about what is really important to us
        if not arch in archs:
            continue

        status_node = node.find('status')
        try:
            status = status_node.get('code')
        except:
            # code can be missing when package is too new:
            status = 'unknown'

        results_per_arch[arch] = status

    # evaluate the status: do we need to give more time to the build service?
    # Was the build successful?
    bs_not_ready = False
    do_not_wait_for_bs = False
    build_successful = True

    # A bit paranoid, but it seems it happened to me once...
    if len(results_per_arch) == 0:
        bs_not_ready = True
        build_successful = False
        if verbose_error:
            print >>sys.stderr, 'Build service did not return any information.'
        error_counter += 1

    for key in results_per_arch.keys():
        arch_need_rebuild = False
        arch = key
        value = results_per_arch[key]

        # the result has changed since last time, so we won't trigger a rebuild
        if state[arch]['result'] != value:
            state[arch]['rebuild'] = -1

        # build is done, but not successful
        if value not in ['succeeded', 'excluded']:
            build_successful = False

        # build is happening or will happen soon
        if value in ['scheduled', 'building', 'dispatching', 'finished']:
            bs_not_ready = True

        # sometimes, the scheduler forgets about a package in 'blocked' state,
        # so we have to force a rebuild
        if value in ['blocked']:
            bs_not_ready = True
            arch_need_rebuild = True

        # build has failed for an architecture: no need to wait for other
        # architectures to know that there's a problem
        elif value in ['failed', 'expansion error', 'broken']:
            # special case (see long comment in the caller of this function)
            if not ignore_initial_errors:
                do_not_wait_for_bs = True
            else:
                bs_not_ready = True
                results_per_arch[key] = 'rebuild needed'

        # 'disabled' => the build service didn't take into account
        # the change we did to the meta yet (eg).
        elif value in ['unknown', 'disabled']:
            bs_not_ready = True
            arch_need_rebuild = True

        # build is done, but is it for the latest version?
        elif value in ['succeeded']:
            # check that the build is for the version we have
            (success, built_srcmd5, built_rev) = self._gnome_get_latest_package_rev_built(apiurl, project, repo, arch, package, verbose_error)

            if not success:
                results_per_arch[key] = 'succeeded, but maybe not up-to-date'
                error_counter += 1
                # we don't know what's going on, so we'll contact the build
                # service again
                bs_not_ready = True
            else:
                # reset the error counter
                error_counter = 0

                #FIXME: "revision" seems to not have the same meaning for the
                # build history and for the local package. See bug #436781
                # (bnc). So, we just ignore the revision for now.
                #if (built_srcmd5, built_rev) != (srcmd5, rev):
                if built_srcmd5 != srcmd5:
                    arch_need_rebuild = True
                    results_per_arch[key] = 'rebuild needed'

        if arch_need_rebuild and state[arch]['rebuild'] == 0:
            bs_not_ready = True

            if not time:
                print 'Triggering rebuild for %s' % (arch,)
            else:
                print 'Triggering rebuild for %s as of %s' % (arch, time.strftime('%X (%x)', time.localtime()))

            try:
                rebuild(apiurl, project, package, repo, arch)
                # reset the error counter
                error_counter = 0
            except urllib2.HTTPError, e:
                if verbose_error:
                    print >>sys.stderr, 'Cannot trigger rebuild for %s: %s' % (arch, e.msg)
                error_counter += 1

        state[arch]['result'] = results_per_arch[key]

        if state[arch]['result'] in ['blocked']:
            # if we're blocked, maybe the scheduler forgot about us, so
            # schedule a rebuild every 60 minutes. The main use case is when
            # you leave the plugin running for a whole night.
            if state[arch]['rebuild'] <= 0:
                state[arch]['rebuild-timeout'] = 60
                state[arch]['rebuild'] = state[arch]['rebuild-timeout']

            # note: it's correct to decrement even if we start with a new value
            # of timeout, since if we don't, it adds 1 minute (ie, 5 minutes
            # instead of 4, eg)
            state[arch]['rebuild'] = state[arch]['rebuild'] - 1
        elif state[arch]['result'] in ['unknown', 'disabled', 'rebuild needed']:
            # if we're in this unexpected state, force the scheduler to do
            # something
            if state[arch]['rebuild'] <= 0:
                # we do some exponential timeout until 60 minutes. We skip
                # timeouts of 1 and 2 minutes since they're quite short.
                if state[arch]['rebuild-timeout'] > 0:
                    state[arch]['rebuild-timeout'] = min(60, state[arch]['rebuild-timeout'] * 2)
                else:
                    state[arch]['rebuild-timeout'] = 4
                state[arch]['rebuild'] = state[arch]['rebuild-timeout']

            # note: it's correct to decrement even if we start with a new value
            # of timeout, since if we don't, it adds 1 minute (ie, 5 minutes
            # instead of 4, eg)
            state[arch]['rebuild'] = state[arch]['rebuild'] - 1
        else:
            # else, we make sure we won't manually trigger a rebuild
            state[arch]['rebuild'] = -1
            state[arch]['rebuild-timeout'] = -1

    if do_not_wait_for_bs:
        bs_not_ready = False

    return (bs_not_ready, build_successful, error_counter, state)


def _gnome_build_wait_loop(self, apiurl, project, repo, package, archs, srcmd5, rev, recently_changed):
    # seconds we wait before looking at the results on the build service
    check_frequency = 60
    max_errors = 10

    select = self.OscGnomeImport.m_import('select')
    time = self.OscGnomeImport.m_import('time')
    if not select or not time:
        print >>sys.stderr, 'Cannot monitor build for package in the build service: incomplete python installation.'
        return (False, {})


    build_successful = False
    print_status = False
    error_counter = 0
    last_check = 0

    state = {}
    # When we want to trigger a rebuild for this arch.
    # The initial value is 1 since we don't want to trigger a rebuild the first
    # time when the state is 'disabled' since the state might have changed very
    # recently (if we updated the metadata ourselves), and the build service
    # might have an old build that it can re-use instead of building again.
    for arch in archs:
        state[arch] = {}
        state[arch]['rebuild'] = -1
        state[arch]['rebuild-timeout'] = -1
        state[arch]['result'] = 'unknown'

    # if we just committed a change, we want to ignore the first error to let
    # the build service reevaluate the situation
    ignore_initial_errors = recently_changed

    print "Waiting for the build to finish..."
    print "You can press enter to get the current status of the build."

    # It's important to start the loop by downloading results since we might
    # already have successful builds, and we don't want to wait to know that.

    try:

        while True:
            # get build status if we don't have a recent status
            now = time.time()
            if now - last_check >= 58:
                # 58s since sleep() is not 100% precise and we don't want to miss
                # one turn
                last_check = now

                (need_to_continue, build_successful, error_counter, state) = self._gnome_build_get_results(apiurl, project, repo, package, archs, srcmd5, rev, state, ignore_initial_errors, error_counter, print_status)
                # make sure we don't ignore errors anymore
                ignore_initial_errors = False

                # just stop if there are too many errors
                if error_counter > max_errors:
                    print >>sys.stderr, 'Giving up: too many consecutive errors when contacting the build service.'
                    break

            else:
                # we didn't download the results, so we want to continue anyway
                need_to_continue = True

            if print_status:
                header = 'Status as of %s [checking the status every %d seconds]' % (time.strftime('%X (%x)', time.localtime(last_check)), check_frequency)
                self._gnome_print_build_status(repo, state, header, 'no results returned by the build service')

            if not need_to_continue:
                break


            # and now wait for input/timeout
            print_status = False

            # wait check_frequency seconds or for user input
            now = time.time()
            if now - last_check < check_frequency:
                wait = check_frequency - (now - last_check)
            else:
                wait = check_frequency

            res = select.select([sys.stdin], [], [], wait)

            # we have user input
            if len(res[0]) > 0:
                print_status = True
                # empty sys.stdin
                sys.stdin.readline()


    # we catch this exception here since we might need to revert some metadata
    except KeyboardInterrupt:
        print ''
        print 'Interrupted: not waiting for the build to finish. Cleaning up...'

    return (build_successful, state)


#######################################################################


def _gnome_build_internal(self, apiurl, osc_package, repo, archs, recently_changed):
    project = osc_package.prjname
    package = osc_package.name

    # check that build is enabled for this package in this project, and if this
    # is not the case, enable it
    try:
        meta_lines = show_package_meta(apiurl, project, package)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Error while checking if package is set to build: %s' % e.msg
        return False

    meta = ''.join(meta_lines)
    (success, changed_meta) = self._gnome_enable_build(apiurl, project, package, meta, repo, archs)
    if not success:
        return False

    # loop to periodically check the status of the build (and eventually
    # trigger rebuilds if necessary)
    (build_success, build_state) = self._gnome_build_wait_loop(apiurl, project, repo, package, archs, osc_package.srcmd5, osc_package.rev, recently_changed)

    if not build_success:
        self._gnome_print_build_status(repo, build_state, 'Status', 'no status known: osc got interrupted?', hint=True)

    # disable build for package in this project if we manually enabled it
    # (we just reset to the old settings)
    if changed_meta:
        self._gnome_package_set_meta(apiurl, project, package, meta, 'Error while resetting build settings of package on the build service')

    return build_success


#######################################################################


def _gnome_build(self, apiurl, user, projects, msg, repo, archs):
    try:
        osc_package = filedir_to_pac('.')
    except oscerr.NoWorkingCopy, e:
        print >>sys.stderr, e
        return

    project = osc_package.prjname
    package = osc_package.name

    committed = False

    # commit if there are local changes
    if self._gnome_osc_package_pending_commit(osc_package):
        if not msg:
            msg = edit_message()
        self._gnome_osc_package_commit(osc_package, msg)
        committed = True

    build_success = self._gnome_build_internal(apiurl, osc_package, repo, archs, committed)

    if build_success:
        print 'Package successfully built on the build service.'


#######################################################################


def _gnome_build_submit(self, apiurl, user, projects, msg, repo, archs, forward = False):
    try:
        osc_package = filedir_to_pac('.')
    except oscerr.NoWorkingCopy, e:
        print >>sys.stderr, e
        return

    project = osc_package.prjname
    package = osc_package.name

    # do some preliminary checks on the package/project: it has to be
    # a branch of a development project
    if not osc_package.islink():
        print >>sys.stderr, 'Package is not a link.'
        return

    parent_project = osc_package.linkinfo.project
    if not parent_project in projects:
        if len(projects) == 1:
            print >>sys.stderr, 'Package links to project %s and not %s. You can use --project to override your project settings.' % (parent_project, projects[0])
        else:
            print >>sys.stderr, 'Package links to project %s. You can use --project to override your project settings.' % parent_project
        return

    if not project.startswith('home:%s:branches' % user):
        print >>sys.stderr, 'Package belongs to project %s which does not look like a branch project.' % project
        return

    if project != 'home:%s:branches:%s' % (user, parent_project):
        print >>sys.stderr, 'Package belongs to project %s which does not look like a branch project for %s.' % (project, parent_project)
        return


    # get the message that will be used for commit & submitreq
    if not msg:
        msg = edit_message(footer='This message will be used for commit (if necessary) and submitreq.\n')

    committed = False

    # commit if there are local changes
    if self._gnome_osc_package_pending_commit(osc_package):
        self._gnome_osc_package_commit(osc_package, msg)
        committed = True

    build_success = self._gnome_build_internal(apiurl, osc_package, repo, archs, committed)

    # if build successful, submit
    if build_success:
        result = create_submit_request(apiurl,
                                       project, package,
                                       parent_project, package,
                                       msg)

        print 'Package submitted to %s (request id: %s).' % (parent_project, result)
        if forward:
            # we volunteerly restrict the project list to parent_project for
            # self-consistency and more safety
            self._gnome_forward(apiurl, [ parent_project ], result)
    else:
        print 'Package was not submitted to %s' % parent_project


#######################################################################


# TODO
# Add a commit method.
# This will make some additional checks:
#   + if we used update, we can initialize a list of patches/sources
#     before any change. This way, on the commit, we can look if the
#     remaining files are still referenced in the .spec, and if not
#     complain if the file hasn't been removed from the directory.
#     We can also complain if a file hasn't been added with osc add,
#     while it's referenced.
#   + complain if the lines in .changes are too long


#######################################################################


# Unfortunately, as of Python 2.5, ConfigParser does not know how to
# preserve a config file: it removes comments and reorders stuff.
# This is a dumb function to append a value to a section in a config file.
def _gnome_add_config_option(self, section, key, value):
    tempfile = self.OscGnomeImport.m_import('tempfile')
    if not tempfile:
        print >>sys.stderr, 'Cannot update your configuration: incomplete python installation.'
        return

    # See get_config() in osc/conf.py and postoptparse() in
    # osc/commandline.py
    conffile = self.options.conffile or os.environ.get('OSC_CONFIG', '~/.oscrc')
    conffile = os.path.expanduser(conffile)

    if not os.path.exists(conffile):
        lines = [ ]
    else:
        fin = open(conffile, 'r')
        lines = fin.readlines()
        fin.close()

    (fdout, tmp) = tempfile.mkstemp(prefix = os.path.basename(conffile), dir = os.path.dirname(conffile))

    in_section = False
    added = False
    empty_line = False

    for line in lines:
        if line.rstrip() == '[' + section + ']':
            in_section = True
        # key was not in the section: let's add it
        elif line[0] == '[' and in_section and not added:
            if not empty_line:
                os.write(fdout, '\n')
            os.write(fdout, '%s = %s\n\n' % (key, value))
            added = True
            in_section = False
        elif line[0] == '[' and in_section:
            in_section = False
        # the section/key already exists: we replace
        # 'not added': in case there are multiple sections with the same name
        elif in_section and not added and line.startswith(key):
            index = line.find('=')
            if line[:index].rstrip() == key:
                line = '%s= %s\n' % (line[:index], value)
                added = True

        os.write(fdout, line)

        empty_line = line.strip() == ''

    if not added:
        if not empty_line:
            os.write(fdout, '\n')
        os.write(fdout, '[%s]\n%s = %s\n' % (section, key, value))

    os.close(fdout)
    os.rename(tmp, conffile)


#######################################################################


def _gnome_ensure_email(self):
    if not conf.config.has_key('gnome_email'):
        conf.config['gnome_email'] = raw_input('E-mail address to use for .changes entries: ')
        if conf.config['gnome_email'] == '':
            return 'EMAIL@DOMAIN'

        self._gnome_add_config_option('general', 'gnome_email', conf.config['gnome_email'])

    return conf.config['gnome_email']


#######################################################################


@cmdln.option('--xs', '--exclude-submitted', action='store_true',
              dest='exclude_submitted',
              help='do not show submitted packages in the output')
@cmdln.option('--xr', '--exclude-reserved', action='store_true',
              dest='exclude_reserved',
              help='do not show reserved packages in the output')
@cmdln.option('--ir', '--ignore-reserved', action='store_true',
              dest='ignore_reserved',
              help='ignore the reservation state of the package if necessary')
@cmdln.option('--nr', '--no-reserve', action='store_true',
              dest='no_reserve',
              help='do not reserve the package')
@cmdln.option('-m', '--message', metavar='TEXT',
              dest='msg',
              help='specify log message TEXT')
@cmdln.option('-f', '--forward', action='store_true',
              dest='forward',
              help='automatically forward to parent project if successful')
@cmdln.option('--project', metavar='PROJECT', action='append',
              dest='projects', default=[],
              help='project to work on (default: GNOME:Factory)')
@cmdln.option('--repo', metavar='REPOSITORY',
              dest='repo',
              help='build repository to build on (default: openSUSE_Factory)')
@cmdln.option('--arch', metavar='ARCH', action='append',
              dest='archs', default=[],
              help='architectures to build on (default: i586 and x86_64)')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" (or "t") will list the packages that need some action.

    "todoadmin" (or "ta") will list the packages from the project that need
    to be submitted to the parent project, and various other errors or tasks.

    "listreserved" (or "lr") will list the reserved packages.

    "isreserved" (or "ir") will look if a package is reserved.

    "reserve" (or "r") will reserve a package so other people know you're
    working on it.

    "unreserve" (or "u") will remove the reservation you had on a package.

    "setup" (or "s") will prepare a package for work (possibly reservation,
    branch, checking out, etc.). The package will be checked out in the current
    directory.

    "update" (or "up") will prepare a package for update (possibly reservation,
    branch, checking out, download of the latest upstream tarball, .spec
    edition, etc.). The package will be checked out in the current directory.

    "forward" (or "f") will forward a submission request to the project to
    parent project. This includes the step of accepting the request first.

    "build" (or "b") will commit the local changes of the package in
    the current directory and wait for the build to succeed on the build
    service.

    "buildsubmit" (or "bs") will commit the local changes of the package in
    the current directory, wait for the build to succeed on the build service
    and if the build succeeds, submit the package to the development project.

    Usage:
        osc gnome todo [--exclude-submitted|--xs] [--exclude-reserved|--xr] [--project=PROJECT]
        osc gnome todoadmin [--exclude-submitted|--xs] [--project=PROJECT]

        osc gnome listreserved
        osc gnome isreserved PKG
        osc gnome reserve PKG [...]
        osc gnome unreserve PKG [...]

        osc gnome setup [--ignore-reserved|--ir] [--no-reserve|--nr] [--project=PROJECT] PKG
        osc gnome update [--ignore-reserved|--ir] [--no-reserve|--nr] [--project=PROJECT] PKG

        osc gnome forward [--project=PROJECT] ID

        osc gnome build [--message=TEXT|-m=TEXT] [--repo=REPOSITORY] [--arch=ARCH]
        osc gnome buildsubmit [--forward|-f] [--message=TEXT|-m=TEXT] [--repo=REPOSITORY] [--arch=ARCH]
    ${cmd_option_list}
    """

    # uncomment this when profiling is needed
    #self.gtime = self.OscGnomeImport.m_import('time')
    #self.gref = self.gtime.time()
    #print "%.3f - %s" % (self.gtime.time()-self.gref, 'start')

    cmds = ['todo', 't', 'todoadmin', 'ta', 'listreserved', 'lr', 'isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u', 'setup', 's', 'update', 'up', 'forward', 'f', 'build', 'b', 'buildsubmit', 'bs']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved', 'lr', 'todo', 't', 'todoadmin', 'ta', 'build', 'b', 'buildsubmit', 'bs']:
        min_args, max_args = 0, 0
    elif cmd in ['isreserved', 'ir', 'setup', 's', 'update', 'up', 'forward', 'f']:
        min_args, max_args = 1, 1
    elif cmd in ['reserve', 'r', 'unreserve', 'u']:
        min_args = 1
        max_args = sys.maxint
    else:
        raise RuntimeError('Unknown command: %s' % cmd)

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    if len(opts.projects) != 0:
        projects = opts.projects
    elif conf.config.has_key('gnome_projects'):
        projects_line = conf.config['gnome_projects']
        projects = projects_line.split(';')
        # remove all empty projects
        while True:
            try:
                projects.remove('')
            except ValueError:
                break
    else:
        projects = ['GNOME:Factory']

    if opts.repo:
        repo = opts.repo
    elif conf.config.has_key('gnome_repo'):
        repo = conf.config['gnome_repo']
    else:
        repo = 'openSUSE_Factory'

    if len(opts.archs) != 0:
        archs = opts.archs
    elif conf.config.has_key('gnome_archs'):
        archs_line = conf.config['gnome_archs']
        archs = projects_line.split(';')
        # remove all empty architectures
        while True:
            try:
                archs.remove('')
            except ValueError:
                break
    else:
        archs = ['i586', 'x86_64']

    apiurl = conf.config['apiurl']
    user = conf.config['user']
    email = self._gnome_ensure_email()

    self._gnome_web = self.OscGnomeWeb(self.OscGnomeWebError, self.GnomeCache)
    self.GnomeCache.init(self.OscGnomeImport.m_import)

    # Do the command
    if cmd in ['todo', 't']:
        self._gnome_todo(apiurl, projects, opts.exclude_reserved, opts.exclude_submitted)

    elif cmd in ['todoadmin', 'ta']:
        self._gnome_todoadmin(apiurl, projects, opts.exclude_submitted)

    elif cmd in ['listreserved', 'lr']:
        self._gnome_listreserved()

    elif cmd in ['isreserved', 'ir']:
        package = args[1]
        self._gnome_isreserved(package)

    elif cmd in ['reserve', 'r']:
        packages = args[1:]
        self._gnome_reserve(packages, user)

    elif cmd in ['unreserve', 'u']:
        packages = args[1:]
        self._gnome_unreserve(packages, user)

    elif cmd in ['setup', 's']:
        package = args[1]
        self._gnome_setup(apiurl, user, projects, package, ignore_reserved = opts.ignore_reserved, no_reserve = opts.no_reserve)

    elif cmd in ['update', 'up']:
        package = args[1]
        self._gnome_update(apiurl, user, email, projects, package, ignore_reserved = opts.ignore_reserved, no_reserve = opts.no_reserve)

    elif cmd in ['forward', 'f']:
        request_id = args[1]
        self._gnome_forward(apiurl, projects, request_id)

    elif cmd in ['build', 'b']:
        self._gnome_build(apiurl, user, projects, opts.msg, repo, archs)

    elif cmd in ['buildsubmit', 'bs']:
        self._gnome_build_submit(apiurl, user, projects, opts.msg, repo, archs, forward = opts.forward)

    else:
        raise RuntimeError('Unknown command: %s' % cmd)
