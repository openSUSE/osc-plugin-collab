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


    def get_packages_versions(self, project):
        packages_versions = []

        data = urlencode({'project': project})
        url = self._append_data_to_url(self._csv_url, data)

        try:
            fd = self.Cache.get_url_fd_with_cache(url, 'db-obs-csv-%s' % project, 10)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of packages: %s' % e.msg)

        lines = fd.readlines()
        fd.close()

        for line in lines:
            try:
                (package, oF_version, devel_version, upstream_version, empty) = line.split(';')
                packages_versions.append((package, oF_version, devel_version, upstream_version))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
                continue

        return packages_versions


    def get_packages_with_delta(self, project):
        data = urlencode({'project': project})
        url = self._append_data_to_url(self._admin_url, data)

        try:
            fd = self.Cache.get_url_fd_with_cache(url, 'db-obs-admin-%s' % project, 10)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of packages with a delta: %s' % e.msg)

        lines = fd.readlines()
        fd.close()

        return [ line[:-1] for line in lines ]


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
            try:
                (package, error, details) = line.split(';', 3)
                errors.append((package, error, details))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
                continue

        return errors


    def get_versions(self, project, package):
        data = urlencode({'project': project, 'package': package})
        url = self._append_data_to_url(self._csv_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of package %s: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

        try:
            (package, oF_version, devel_version, upstream_version, empty) = line.split(';')
        except ValueError:
            print >>sys.stderr, 'Cannot parse line: %s' % line[:-1]
            return (None, None, None)

        return (oF_version, devel_version, upstream_version)


    def get_upstream_url(self, project, package):
        data = urlencode({'project': project, 'package': package})
        url = self._append_data_to_url(self._upstream_url, data)

        try:
            fd = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get upstream URL of package %s: %s' % (package, e.msg))

        line = fd.readline()
        fd.close()

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


# TODO add --no-cache
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
            url = makeurl(apiurl, ['search', 'package'], ['match=%s' % urllib.quote('@project=\'openSUSE:Factory\'')])
            fin = http_GET(url)
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Cannot get list of submissions to %s: %s' % (project, e.msg)
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
    def get_obs_submit_request_list(cls, apiurl, project):
        current_format = 1
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
                    (package, revision, empty) = line.split(';', 3)
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
            retval.append(submitted.dst_package)
            lines.append('%s;%s;' % (submitted.dst_package, submitted.src_md5))

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


def _gnome_needs_update(self, oF_version, devel_version, upstream_version):
    return self._gnome_compare_versions_a_gt_b(upstream_version, oF_version) and self._gnome_compare_versions_a_gt_b(upstream_version, devel_version)


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


def _gnome_todo(self, project, exclude_reserved, exclude_submitted):
    # get all versions of packages
    try:
        packages_versions = self._gnome_web.get_packages_versions(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # get the list of reserved package
    try:
        reserved_packages = self._gnome_web.get_reserved_packages(return_username = False)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg

    # get the packages submitted
    submitted_packages = self.GnomeCache.get_obs_submit_request_list(conf.config['apiurl'], project)

    lines = []

    for (package, oF_version, devel_version, upstream_version) in packages_versions:
        # empty upstream version or upstream version meaning openSUSE is
        # upstream
        if upstream_version == '' or upstream_version == '--':
            continue

        if self._gnome_needs_update(oF_version, devel_version, upstream_version):
            if self._gnome_is_submitted(package, submitted_packages):
                if exclude_submitted:
                    continue
                devel_version += ' (s)'
                upstream_version += ' (s)'
            if package in reserved_packages:
                if exclude_reserved:
                    continue
                upstream_version += ' (r)'
            lines.append((package, oF_version, devel_version, upstream_version))

    if len(lines) == 0:
        print 'Nothing to do.'
        return

    # print headers
    title = ('Package', 'openSUSE:Factory', project, 'Upstream')
    (max_package, max_oF, max_devel, max_upstream) = self._gnome_table_get_maxs(title, lines)
    # trim to a reasonable max
    max_package = min(max_package, 48)
    max_version = min(max(max(max_oF, max_devel), max_upstream), 20)

    print_line = self._gnome_table_get_template(max_package, max_version, max_version, max_version)
    self._gnome_table_print_header(print_line, title)
    for line in lines:
        print print_line % line


#######################################################################


def _gnome_get_packages_with_bad_meta(self, project):
    metafile = self.GnomeCache.get_obs_meta(conf.config['apiurl'], 'openSUSE:Factory')
    if not metafile:
        return (None, None)

    try:
        collection = ET.parse(metafile).getroot()
    except SyntaxError:
        print >>sys.stderr, 'Cannot parse %s: %s' % (metafile, e.msg)
        return (None, None)

    devel_dict = {}
    # list of packages that should exist in G:F but that don't
    bad_devel_packages = []
    # list of packages that exist in G:F but that shouldn't
    should_devel_packages = []

    # save all packages that should be in G:F and also create a db of
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

    # get the list of packages that are actually in G:F
    try:
        packages_versions = self._gnome_web.get_packages_versions(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return (None, None)

    # now really create the list of packages that should be in G:F and
    # create the list of packages that shouldn't stay in G:F
    for (package, oF_version, devel_version, upstream_version) in packages_versions:
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


def _gnome_min_package(self, *args):
    min_package = None
    for i in range(len(args)):
        if args[i]:
            if min_package:
                min_package = min(args[i], min_package)
            else:
                min_package = args[i]

    return min_package


def _gnome_todoadmin(self, project, exclude_submitted):
    def _insert_delta_package(lines, delta_package, submitted_packages):
        if self._gnome_is_submitted(delta_package, submitted_packages):
            if exclude_submitted:
                return
            message = 'Waits for approval in openSUSE:Factory queue'
        else:
            message = 'Needs to be submitted to openSUSE:Factory'
        lines.append((delta_package, message))

    def _insert_error_package(lines, error_package_tuple):
        (error_package, error, details) = error_package_tuple
        if error == 'not-link':
            message = 'Is not a link to openSUSE:Factory'
        elif error == 'not-in-parent':
            message = 'Does not exist in openSUSE:Factory'
        elif error == 'need-merge-with-parent':
            message = 'Requires a manual merge with openSUSE:Factory'
        else:
            if details:
                message = 'Unknown error: %s' % details
            else:
                message = 'Unknown error'
        lines.append((error_package, message))


    # get packages with a delta
    try:
        packages_with_delta = self._gnome_web.get_packages_with_delta(project)
        packages_with_errors = self._gnome_web.get_packages_with_error(project)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # get the packages submitted
    submitted_packages = self.GnomeCache.get_obs_submit_request_list(conf.config['apiurl'], 'openSUSE:Factory')
    (bad_devel_packages, should_devel_packages) = self._gnome_get_packages_with_bad_meta(project)

    lines = []
    delta_index = 0
    delta_max = len(packages_with_delta)
    error_index = 0
    error_max = len(packages_with_errors)
    bad_devel_index = 0
    bad_devel_max = len(bad_devel_packages)
    should_devel_index = 0
    should_devel_max = len(should_devel_packages)


    # This is an ugly loop to merge all the lists we have to get an output
    # in alphabetical order.
    while True:
        if delta_index < delta_max:
            delta_package = packages_with_delta[delta_index]
        else:
            delta_package = None
        if error_index < error_max:
            error_package_tuple = packages_with_errors[error_index]
            error_package = error_package_tuple[0]
        else:
            error_package = None
        if bad_devel_index < bad_devel_max:
            bad_devel_package_tuple = bad_devel_packages[bad_devel_index]
            bad_devel_package = bad_devel_package_tuple[0]
        else:
            bad_devel_package = None
        if should_devel_index < should_devel_max:
            should_devel_package = should_devel_packages[should_devel_index]
        else:
            should_devel_package = None

        package = self._gnome_min_package(delta_package, error_package, bad_devel_package, should_devel_package)

        if not package:
            break
        elif package == should_devel_package:
            lines.append((should_devel_package, 'Does not exist in %s while it should' % project))
            should_devel_index = should_devel_index + 1
            # this package cannot appear in other lists since it's unknown to
            # our scripts
        elif package == bad_devel_package:
            lines.append((bad_devel_package, 'Development project is not %s (%s)' % (project, bad_devel_package_tuple[1])))
            bad_devel_index = bad_devel_index + 1
            if package == error_package:
                error_index = error_index + 1
            if package == delta_package:
                delta_index = delta_index + 1
        elif package == error_package:
            _insert_error_package(lines, error_package_tuple)
            error_index = error_index + 1
            if package == delta_package:
                delta_index = delta_index + 1
        elif package == delta_package:
            _insert_delta_package(lines, delta_package, submitted_packages)
            delta_index = delta_index + 1


    if len(lines) == 0:
        print 'Nothing to do.'
        return

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


def _gnome_setup(self, apiurl, username, project, package, ignore_reserved = False, no_reserve = False):
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

    if old_tarball and os.path.exists(old_tarball):
        try:
            old = tarfile.open(old_tarball)
        except tarfile.TarError:
            old = None
    else:
        # this is not fatal: we can provide the NEWS/ChangeLog from the new
        # tarball without a diff
        old = None

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
    _extract_files (old, old_dir, ['NEWS', 'ChangeLog'])
    _extract_files (new, new_dir, ['NEWS', 'ChangeLog'])
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
    if not file.endswith('.gz'):
        raise self.OscGnomeCompressError('Cannot recompress %s as bz2: filename not ending with .gz.' % os.path.basename(file))
    dest_file = file[:-3] + '.bz2'

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


# TODO:
# Fixup the BuildRequires line (One requires per line, and sort them
# alphabetically)
# Also put Name/License/Group/BuildRequires/etc. in the right order
# Actually, create a class that fixes a spec file
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
    locale.setlocale(locale.LC_TIME, 'C')

    os.write(fdout, '-------------------------------------------------------------------\n')
    os.write(fdout, '%s - %s\n' % (time.strftime("%a %b %e %H:%M:%S %Z %Y"), email))
    os.write(fdout, '\n')
    os.write(fdout, '- Update to version %s:\n' % upstream_version)
    os.write(fdout, '  + \n')
    os.write(fdout, '\n')

    locale.setlocale(locale.LC_TIME, old_lc_time)

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


def _gnome_update(self, apiurl, username, email, project, package, ignore_reserved = False, no_reserve = False):
    try:
        (oF_version, devel_version, upstream_version) = self._gnome_web.get_versions(project, package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # check that the project is up-to-date wrt openSUSE:Factory
    if self._gnome_compare_versions_a_gt_b(oF_version, devel_version):
        # TODO, actually we can do a better check than that with the delta API
        print 'Package %s is more recent in openSUSE:Factory (%s) than in %s (%s). Please synchronize %s first.' % (package, oF_version, project, devel_version, project)
        return

    # check that an update is really needed
    if upstream_version == '':
        print 'No information about upstream version of package %s is available. Assuming it is not up-to-date.' % package
    elif not self._gnome_needs_update(oF_version, devel_version, upstream_version):
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
    if upstream_tarball.endswith('.gz'):
        try:
            upstream_tarball = self._gnome_gz_to_bz2_internal(upstream_tarball)
            upstream_tarball_basename = os.path.basename(upstream_tarball)
            print '%s has been recompressed to bz2.' % upstream_tarball_basename
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

    # TODO add a note about checking if patches are still needed, buildrequires
    # & requires
    # automatically start a build?


#######################################################################


def _gnome_forward(self, apiurl, project, request_id):
    request = get_submit_request(conf.config['apiurl'], request_id)

    if request.dst_project != project:
        print >>sys.stderr, 'Submission request %d is for %s and not %s.' % (request_id, request.dst_project, project)
        return

    if request.state.name != 'new':
        print >>sys.stderr, 'Submission request %d is not new.' % request_id
        return

    try:
        devel_project = show_develproject(apiurl, 'openSUSE:Factory', request.dst_package)
    except urllib2.HTTPError:
#FIXME
        return

    if devel_project != project:
#FIXME
        return

    result = change_submit_request_state(apiurl, request_id, 'accepted', 'Forwarding to openSUSE:Factory')
    root = ET.fromstring(result)
    if not 'code' in root.keys() or root.get('code') != 'ok':
        print >>sys.stderr, 'Cannot accept submission request %d: %s' % (request_id, result)
        return

    # TODO: cancel old requests from project to oS:F
    # TODO: create_submit_request

    print 'Submission request %d has been forwarded to openSUSE:Factory.' % request_id


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
@cmdln.option('--project', metavar='PROJECT',
              help='project to work on (default: GNOME:Factory')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" (or "t") will list the packages that need some action.

    "todoadmin" (or "ta") will list the packages from the project that need
    to be submitted to openSUSE:Factory.

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
    openSUSE:Factory. This includes the step of accepting the request first.

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
    ${cmd_option_list}
    """

    # uncomment this when profiling is needed
    #self.gtime = self.OscGnomeImport.m_import('time')
    #self.gref = self.gtime.time()
    #print "%.3f - %s" % (self.gtime.time()-self.gref, 'start')

    cmds = ['todo', 't', 'todoadmin', 'ta', 'listreserved', 'lr', 'isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u', 'setup', 's', 'update', 'up', 'forward', 'f']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved', 'lr', 'todo', 't', 'todoadmin', 'ta']:
        min_args, max_args = 0, 0
    elif cmd in ['isreserved', 'ir', 'setup', 's', 'update', 'up', 'forward', 'f']:
        min_args, max_args = 1, 1
    elif cmd in ['reserve', 'r', 'unreserve', 'u']:
        min_args = 1
        max_args = sys.maxint

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    if opts.project:
        project = opts.project
    elif conf.config.has_key('gnome_project'):
        project = conf.config['gnome_project']
    else:
        project = 'GNOME:Factory'

    email = self._gnome_ensure_email()

    self._gnome_web = self.OscGnomeWeb(self.OscGnomeWebError, self.GnomeCache)
    self.GnomeCache.init(self.OscGnomeImport.m_import)

    # Do the command
    if cmd in ['todo', 't']:
        self._gnome_todo(project, opts.exclude_reserved, opts.exclude_submitted)

    elif cmd in ['todoadmin', 'ta']:
        self._gnome_todoadmin(project, opts.exclude_submitted)

    elif cmd in ['listreserved', 'lr']:
        self._gnome_listreserved()

    elif cmd in ['isreserved', 'ir']:
        package = args[1]
        self._gnome_isreserved(package)

    elif cmd in ['reserve', 'r']:
        packages = args[1:]
        self._gnome_reserve(packages, conf.config['user'])

    elif cmd in ['unreserve', 'u']:
        packages = args[1:]
        self._gnome_unreserve(packages, conf.config['user'])

    elif cmd in ['setup', 's']:
        package = args[1]
        self._gnome_setup(conf.config['apiurl'], conf.config['user'], project, package, ignore_reserved = opts.ignore_reserved, no_reserve = opts.no_reserve)

    elif cmd in ['update', 'up']:
        package = args[1]
        self._gnome_update(conf.config['apiurl'], conf.config['user'], email, project, package, ignore_reserved = opts.ignore_reserved, no_reserve = opts.no_reserve)

    elif cmd in ['forward', 'f']:
        request_id = args[1]
        self._gnome_forward(conf.config['apiurl'], project, request_id)
