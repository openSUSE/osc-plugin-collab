# TODO: add a class to cache files that we download from the web

class OscGnomeError(Exception):
    def __init__(self, value):
        self.msg = value

    def __str__(self):
        return repr(self.msg)


class OscGnomeWebError(OscGnomeError):
    pass

class OscGnomeDownloadError(OscGnomeError):
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

    def __init__(self, exception):
        self.Error = exception


    def _parse_reservation(self, line):
        try:
            (package, username, comment) = line[:-1].split(';')
            return (package, username, comment)
        except ValueError:
            print >>sys.stderr, 'Cannot parse reservation information: ' + line[:-1]
            return (None, None, None)


    def get_packages_versions(self):
        packages_versions = []

        try:
            fd = urllib2.urlopen(self._csv_url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of packages: ' + e.msg)

        lines = fd.readlines()
        fd.close()

        for line in lines:
            try:
                (package, oF_version, GF_version, upstream_version, empty) = line.split(';')
                packages_versions.append((package, oF_version, GF_version, upstream_version))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: ' + line[:-1]
                continue

        return packages_versions


    def get_packages_with_delta(self):
        try:
            fd = urllib2.urlopen(self._admin_url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of packages with a delta: ' + e.msg)

        lines = fd.readlines()
        fd.close()

        return [ line[:-1] for line in lines ]


    def get_packages_with_error(self):
        errors = []

        try:
            fd = urllib2.urlopen(self._error_url)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of packages with an error: ' + e.msg)

        lines = fd.readlines()
        fd.close()

        for line in lines:
            try:
                (package, error, details) = line.split(';', 3)
                errors.append((package, error, details))
            except ValueError:
                print >>sys.stderr, 'Cannot parse line: ' + line[:-1]
                continue

        return errors


    def get_versions(self, package):
        try:
            fd = urllib2.urlopen(self._csv_url + '&package=' + package)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get versions of package ' + package + ': ' + e.msg)

        line = fd.readline()
        fd.close()

        try:
            (package, oF_version, GF_version, upstream_version, empty) = line.split(';')
        except ValueError:
            print >>sys.stderr, 'Cannot parse line: ' + line[:-1]
            return (None, None, None)

        return (oF_version, GF_version, upstream_version)


    def get_upstream_url(self, package):
        try:
            fd = urllib2.urlopen(self._upstream_url + '?package=' + package)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get upstream URL of package ' + package + ': ' + e.msg)

        line = fd.readline()
        fd.close()

        try:
            (package, upstream_version, upstream_url, empty) = line.split(';')
        except ValueError:
            print >>sys.stderr, 'Cannot parse line: ' + line[:-1]
            return None

        if empty and empty.strip() != '':
            raise self.Error('Upstream URL of package ' + package + ' probably contains a semi-colon. This is a bug in the server and the plugin.')

        return upstream_url


    def get_reserved_packages(self, return_package = True, return_username = True, return_comment = False):
        reserved_packages = []

        try:
            fd = urllib2.urlopen(self._reserve_url + '?mode=getall')
        except urllib2.HTTPError, e:
            raise self.Error('Cannot get list of reserved packages: ' + e.msg)

        lines = fd.readlines()
        fd.close()

        # it returns a status code on the first line, and then one package per
        # line
        # if the status code is 200, then everything is good
        if lines[0][:3] != '200':
            raise self.Error('Error while getting list of reserved packages: ' + lines[0][4:-1])
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
        try:
            fd = urllib2.urlopen(self._reserve_url + '?mode=get&package=' + package)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot look if package ' + package + ' is reserved: ' + e.msg)

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot look if package ' + package + ' is reserved: ' + line[4:-1])

        (package, username, comment) = self._parse_reservation(line[4:])

        if not username or username == '':
            return None
        else:
            return username


    def reserve_package(self, package, username):
        try:
            fd = urllib2.urlopen(self._reserve_url + '?mode=set&user=' + username + '&package=' + package)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot reserve package ' + package + ': ' + e.msg)

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot reserve package ' + package + ': ' + line[4:-1])


    def unreserve_package(self, package, username):
        try:
            fd = urllib2.urlopen(self._reserve_url + '?mode=unset&user=' + username + '&package=' + package)
        except urllib2.HTTPError, e:
            raise self.Error('Cannot unreserve package ' + package + ': ' + e.msg)

        line = fd.readline()
        fd.close()

        if line[:3] != '200':
            raise self.Error('Cannot unreserve package ' + package + ': ' + line[4:-1])


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


def _gnome_needs_update(self, oF_version, GF_version, upstream_version):
    return self._gnome_compare_versions_a_gt_b(upstream_version, oF_version) and self._gnome_compare_versions_a_gt_b(upstream_version, GF_version)


def _gnome_is_submitted(self, package, submitted_packages):
    for submitted in submitted_packages:
        if package == submitted.dst_package:
            return True


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

    very_long_dash = ('-------------------------------------------------',)
    dashes = ()
    for i in range(len(title)):
        dashes = dashes + very_long_dash

    print template % title
    print dash_template % dashes


#######################################################################


def _gnome_todo(self, exclude_reserved, exclude_submitted):
    # get all versions of packages
    try:
        packages_versions = self._gnome_web.get_packages_versions()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # get the list of reserved package
    try:
        reserved_packages = self._gnome_web.get_reserved_packages(return_username = False)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg

    # get the packages submitted to GNOME:Factory
    try:
        submitted_packages = get_submit_request_list(conf.config['apiurl'], 'GNOME:Factory', None)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot get list of submissions to GNOME:Factory: ' + e.msg

    lines = []

    for (package, oF_version, GF_version, upstream_version) in packages_versions:
        # empty upstream version or upstream version meaning openSUSE is
        # upstream
        if upstream_version == '' or upstream_version == '--':
            continue

        if self._gnome_needs_update(oF_version, GF_version, upstream_version):
            if self._gnome_is_submitted(package, submitted_packages):
                if exclude_submitted:
                    continue
                GF_version = GF_version + ' (s)'
                upstream_version = upstream_version + ' (s)'
            if package in reserved_packages:
                if exclude_reserved:
                    continue
                upstream_version = upstream_version + ' (r)'
            lines.append((package, oF_version, GF_version, upstream_version))

    if len(lines) == 0:
        print 'Nothing to do.'
        return

    # print headers
    title = ('Package', 'openSUSE:Factory', 'GNOME:Factory', 'Upstream')
    (max_package, max_oF, max_GF, max_upstream) = self._gnome_table_get_maxs(title, lines)
    # trim to a reasonable max
    max_package = min(max_package, 48)
    max_version = min(max(max(max_oF, max_GF), max_upstream), 20)

    print_line = self._gnome_table_get_template(max_package, max_version, max_version, max_version)
    self._gnome_table_print_header(print_line, title)
    for line in lines:
        print print_line % line


#######################################################################


def _gnome_todoadmin(self, exclude_submitted):
    def _insert_delta_package(lines, delta_package, submitted_packages):
        if self._gnome_is_submitted(delta_package, submitted_packages):
            if exclude_submitted:
                return
            message = 'Waits for approval in openSUSE:Factory queue'
        else:
            message = 'Needs to be submitted to openSUSE:Factory'
        lines.append((delta_package, message))


    # get packages with a delta
    try:
        packages_with_delta = self._gnome_web.get_packages_with_delta()
        packages_with_errors = self._gnome_web.get_packages_with_error()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # get the packages submitted to GNOME:Factory
    try:
        submitted_packages = get_submit_request_list(conf.config['apiurl'], 'openSUSE:Factory', None)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot get list of submissions to openSUSE:Factory: ' + e.msg

    lines = []
    delta_index = 0
    delta_max = len(packages_with_delta)

    # we won't enter in the for loop if there's no error
    if len(packages_with_errors) == 0:
        for delta_package in packages_with_delta:
            _insert_delta_package(lines, delta_package, submitted_packages)

    for (package, error, details) in packages_with_errors:
        # insert the packages with delta in the alphabetical order
        while delta_index < delta_max:
            delta_package = packages_with_delta[delta_index]
            if not delta_package:
                break
            if delta_package > package:
                break

            delta_index = delta_index + 1

            if delta_package == package:
                # we have an error and a delta: error is more important
                break

            _insert_delta_package(lines, delta_package, submitted_packages)

        if error == 'not-link':
            message = 'Is not a link to openSUSE:Factory'
        elif error == 'not-in-parent':
            message = 'Does not exist in openSUSE:Factory'
        elif error == 'need-merge-with-parent':
            message = 'Requires a manual merge with openSUSE:Factory'
        else:
            message = 'Unknown error'
            if details:
                message = message + ': ' + details
        lines.append((package, message))

    if len(lines) == 0:
        print 'Nothing to do.'
        return

    # print headers
    title = ('Package', 'Details')
    (max_package, max_details) = self._gnome_table_get_maxs(title, lines)
    # trim to a reasonable max
    max_package = min(max_package, 48)
    max_details = min(max_details, 50)

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
        print 'Package ' + package + ' is reserved by ' + username + '.'


#######################################################################


def _gnome_reserve(self, packages, username):
    for package in packages:
        try:
            self._gnome_web.reserve_package(package, username)
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            continue

        print 'Package ' + package + ' reserved for 36 hours.'
        print 'Do not forget to unreserve the package when done with it:'
        print '    osc gnome unreserve ' + package


#######################################################################


def _gnome_unreserve(self, packages, username):
    for package in packages:
        try:
            self._gnome_web.unreserve_package(package, username)
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            continue

        print 'Package ' + package + ' unreserved.'


#######################################################################


def _gnome_setup_internal(self, package, apiurl, username, reserve = False):
    # is it reserved?
    try:
        reserved_by = self._gnome_web.is_package_reserved(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return False

    if not reserve:
        # check that we already have reserved the package
        if not reserved_by:
            print 'Please reserve the package ' + package + ' first.'
            return False
        elif reserved_by != username:
            print 'Package ' + package + ' is already reserved by ' + reserved_by + '.'
            return False
    elif reserved_by and reserved_by != username:
        print 'Package ' + package + ' is already reserved by ' + reserved_by + '.'
        return False
    elif not reserved_by:
        # reserve the package
        try:
            self._gnome_web.reserve_package(package, username)
            print 'Package ' + package + ' has been reserved for 36 hours.'
            print 'Do not forget to unreserve the package when done with it:'
            print '    osc gnome unreserve ' + package
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            return False

    # look if we already have a branch, and if not branch the package
    try:
        expected_branch_project = 'home:' + username + ':branches:GNOME:Factory'
        show_package_meta(apiurl, expected_branch_project, package)
        branch_project = expected_branch_project
        # it worked, we already have the branch
    except urllib2.HTTPError, e:
        if e.code != 404:
            print >>sys.stderr, 'Error while checking if package ' + package + ' was already branched: ' + e.msg
            return False
        # We had a 404: it means the branched package doesn't exist yet
        try:
            branch_project = branch_pkg(apiurl, 'GNOME:Factory', package, nodevelproject = True)
            print 'Package ' + package + ' has been branched in project ' + branch_project + '.'
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Error while branching package ' + package + ': ' + e.msg
            return False

    # check out the branched package
    if os.path.exists(package):
        # maybe we already checked it out before?
        if not os.path.isdir(package):
            print >>sys.stderr, 'File ' + package + ' already exists but is not a directory.'
            return False
        elif not is_package_dir(package):
            print >>sys.stderr, 'Directory ' + package + ' already exists but is not a checkout of a Build Service package.'
            return False

        obs_package = filedir_to_pac(package)
        if obs_package.name != package or obs_package.prjname != branch_project:
            print >>sys.stderr, 'Directory ' + package + ' already exists but is a checkout of package ' + obs_package.name + ' from project ' + obs_package.prjname +'.'
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
            print 'Package ' + package + ' has been updated.'
        except Exception, e:
            message = 'Error while updating package ' + package + ': '
            self._gnome_exception_print(e, message)
            return False

    else:
        # check out the branched package
        try:
            checkout_package(apiurl, branch_project, package, expand_link=True)
            print 'Package ' + package + ' has been checked out.'
        except Exception, e:
            message = 'Error while checking out package ' + package + ': '
            self._gnome_exception_print(e, message)
            return False

    return True


#######################################################################


def _gnome_setup(self, package, apiurl, username, reserve = False):
    if not self._gnome_setup_internal(package, apiurl, username, reserve):
        return
    print 'Package ' + package + ' has been prepared for work.'


#######################################################################


def _gnome_download_internal(self, url, dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    urlparse = self.OscGnomeImport.m_import('urlparse')
    if not urlparse:
        raise self.OscGnomeDownloadError('Cannot download ' + url + ': incomplete python installation.')

    parsed_url = urlparse.urlparse(url)
    basename = os.path.basename(parsed_url.path)
    if basename == '':
        raise self.OscGnomeDownloadError('Cannot download ' + url + ': no basename in URL.')

    dest_file = os.path.join(dest_dir, basename)
    # we download the file again if it already exists. Maybe the upstream
    # tarball changed, eg. We could add an option to avoid this, but I feel
    # like it won't happen a lot anyway.
    if os.path.exists(dest_file):
        os.unlink(dest_file)

    try:
        fin = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        raise self.OscGnomeDownloadError('Cannot download ' + url + ': ' + e.msg)

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
            raise self.OscGnomeDownloadError('Error while downloading ' + url + ': ' + e.msg)

    fin.close()
    fout.close()

    return dest_file


#######################################################################


def _gnome_gz_to_bz2_internal(self, file):
    if not file.endswith('.gz'):
        raise self.OscGnomeCompressError('Cannot recompress ' + os.path.basename(file) + ' as bz2: filename not ending with .gz.')
    dest_file = file[:-3] + '.bz2'

    gzip = self.OscGnomeImport.m_import('gzip')
    bz2 = self.OscGnomeImport.m_import('bz2')

    if not gzip or not bz2:
        raise self.OscGnomeCompressError('Cannot recompress ' + os.path.basename(file) + ' as bz2: incomplete python installation.')

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
def _gnome_update_spec(self, spec_file, package, upstream_version):
    if not os.path.exists(spec_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': no such file.'
        return False
    elif not os.path.isfile(spec_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': not a regular file.'
        return False

    tempfile = self.OscGnomeImport.m_import('tempfile')
    re = self.OscGnomeImport.m_import('re')

    if not tempfile or not re:
        print >>sys.stderr, 'Cannot update ' + os.path.basename(spec_file) + ': incomplete python installation.'
        return False

    re_spec_header = re.compile('^(# spec file for package ' + package + ' \(Version )\S*(\).*)', re.IGNORECASE)
    re_spec_version = re.compile('^(Version:\s*)\S*', re.IGNORECASE)
    re_spec_release = re.compile('^(Release:\s*)\S*', re.IGNORECASE)
    re_spec_prep = re.compile('^%prep', re.IGNORECASE)

    fin = open(spec_file, 'r')
    (fdout, tmp) = tempfile.mkstemp(dir = os.path.dirname(spec_file))

    # replace version and reset release
    while True:
        line = fin.readline()
        match = re_spec_prep.match(line)
        if match:
            os.write(fdout, line)
            break

        match = re_spec_header.match(line)
        if match:
            os.write(fdout, match.group(1) + upstream_version + match.group(2) + '\n')
            continue

        match = re_spec_version.match(line)
        if match:
            os.write(fdout, match.group(1) + upstream_version + '\n')
            continue

        match = re_spec_release.match(line)
        if match:
            os.write(fdout, match.group(1) + '1\n')
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

    return True


#######################################################################


def _gnome_update_changes(self, changes_file, upstream_version, email):
    if not os.path.exists(changes_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': no such file.'
        return False
    elif not os.path.isfile(changes_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': not a regular file.'
        return False

    tempfile = self.OscGnomeImport.m_import('tempfile')
    time = self.OscGnomeImport.m_import('time')
    locale = self.OscGnomeImport.m_import('locale')

    if not tempfile or not time or not locale:
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': incomplete python installation.'
        return False

    (fdout, tmp) = tempfile.mkstemp(dir = os.path.dirname(changes_file))

    old_lc_time = locale.setlocale(locale.LC_TIME)
    locale.setlocale(locale.LC_TIME, 'C')

    os.write(fdout, '-------------------------------------------------------------------\n')
    os.write(fdout, time.strftime("%a %b %e %H:%M:%S %Z %Y") + ' - ' + email + '\n')
    os.write(fdout, '\n')
    os.write(fdout, '- Update to version ' + upstream_version + ':\n')
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


def _gnome_update(self, package, apiurl, username, email, reserve = False):
    try:
        (oF_version, GF_version, upstream_version) = self._gnome_web.get_versions(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # check that GNOME:Factory is up-to-date wrt openSUSE:Factory
    if self._gnome_compare_versions_a_gt_b(oF_version, GF_version):
        print 'Package ' + package + ' is more recent in openSUSE:Factory (' + oF_version + ') than in GNOME:Factory (' + GF_version + '). Please synchronize GNOME:Factory first.'
        return

    # check that an update is really needed
    if upstream_version == '':
        print 'No information about upstream version of package ' + package + ' is available. Assuming it is not up-to-date.'
    elif not self._gnome_needs_update(oF_version, GF_version, upstream_version):
        print 'Package ' + package + ' is already up-to-date.'
        return

    if not self._gnome_setup_internal(package, apiurl, username, reserve):
        return

    package_dir = package

    # edit the version tag in the .spec files
    # not fatal if fails
    spec_file = os.path.join(package_dir, package + '.spec')
    if self._gnome_update_spec(spec_file, package, upstream_version):
        print os.path.basename(spec_file) + ' has been prepared.'

    # warn if there are other spec files which might need an update
    for file in os.listdir(package_dir):
        if file.endswith('.spec') and file != os.path.basename(spec_file):
            print 'WARNING: ' + file + ' might need a manual update.'


    # start adding an entry to .changes
    # not fatal if fails
    changes_file = os.path.join(package_dir, package + '.changes')
    if self._gnome_update_changes(changes_file, upstream_version, email):
        print os.path.basename(changes_file) + ' has been prepared.'

    # warn if there are other spec files which might need an update
    for file in os.listdir(package_dir):
        if file.endswith('.changes') and file != os.path.basename(changes_file):
            print 'WARNING: ' + file + ' might need a manual update.'


    # download the upstream tarball
    # fatal if fails
    try:
        upstream_url = self._gnome_web.get_upstream_url(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    if not upstream_url:
        print >>sys.stderr, 'Cannot download latest upstream tarball for ' + package + ': no URL defined.'
        return

    print 'Looking for the upstream tarball...'
    try:
        upstream_tarball = self._gnome_download_internal(upstream_url, package_dir)
    except self.OscGnomeDownloadError, e:
        print >>sys.stderr, e.msg
        return

    if not upstream_tarball:
        print >>sys.stderr, 'No upstream tarball downloaded for ' + package + '.'
        return
    else:
        print os.path.basename(upstream_tarball) + ' has been downloaded.'

    # check integrity of the downloaded file
    # fatal if fails (only if md5 exists)
    # TODO

    # extract NEWS & ChangeLog from the old + new tarballs, and do a diff
    # see difflib python module
    # not fatal if fails
    # TODO


    # recompress as bz2
    # not fatal if fails
    if upstream_tarball.endswith('.gz'):
        try:
            upstream_tarball = self._gnome_gz_to_bz2_internal(upstream_tarball)
            print os.path.basename(upstream_tarball) + ' has been recompressed to bz2.'
        except self.OscGnomeCompressError, e:
            print >>sys.stderr, e.msg


    # 'osc add newfile.tar.bz2' and 'osc del oldfile.tar.bz2'
    # fatail if fails
    # TODO

    # try applying the patches with rpm quilt and start a build if it succeeds
    # not fatal if fails
    # TODO

    print 'Package ' + package + ' has been prepared for the update.'

    # TODO add a note about checking patches, buildrequires & requires


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


# TODO
# We could also check that all packages maintained by gnome-maintainers
# are in G:F.


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
            os.write(fdout, key + ' = ' + str(value) + '\n\n')
            added = True
        # the section/key already exists: we replace
        # 'not added': in case there are multiple sections with the same name
        elif in_section and not added and line.startswith(key):
            index = line.find('=')
            line = line[:index] + '= ' + str(value) + '\n'
            added = True

        os.write(fdout, line)

        empty_line = line.strip() == ''

    if not added:
        if not empty_line:
            os.write(fdout, '\n')
        os.write(fdout, '[' + section + ']' + '\n' + key + ' = ' + str(value) + '\n')

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
@cmdln.option('-r', '--reserve', action='store_true',
              dest='reserve',
              help='also reserve the package')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" (or "t") will list the packages that need some action.

    "todoadmin" (or "ta") will list the packages from GNOME:Factory that need
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

    Usage:
        osc gnome todo [--exclude-reserved|--xr] [--exclude-submitted|--xs]
        osc gnome todoadmin [--exclude-submitted|--xs]

        osc gnome listreserved
        osc gnome isreserved PKG
        osc gnome reserve PKG [...]
        osc gnome unreserve PKG [...]

        osc gnome setup [--reserve|-r] PKG
        osc gnome update [--reserve|-r] PKG
    ${cmd_option_list}
    """

    cmds = ['todo', 't', 'todoadmin', 'ta', 'listreserved', 'lr', 'isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u', 'setup', 's', 'update', 'up']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved', 'lr', 'todo', 't', 'todoadmin', 'ta']:
        min_args, max_args = 0, 0
    elif cmd in ['isreserved', 'ir', 'setup', 's', 'update', 'up']:
        min_args, max_args = 1, 1
    elif cmd in ['reserve', 'r', 'unreserve', 'u']:
        min_args = 1
        max_args = sys.maxint

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    self._gnome_web = self.OscGnomeWeb(self.OscGnomeWebError)

    email = self._gnome_ensure_email()

    # Do the command
    if cmd in ['todo', 't']:
        self._gnome_todo(opts.exclude_reserved, opts.exclude_submitted)

    elif cmd in ['todoadmin', 'ta']:
        self._gnome_todoadmin(opts.exclude_submitted)

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
        self._gnome_setup(package, conf.config['apiurl'], conf.config['user'], reserve = opts.reserve)

    elif cmd in ['update', 'up']:
        package = args[1]
        self._gnome_update(package, conf.config['apiurl'], conf.config['user'], email, reserve = opts.reserve)
