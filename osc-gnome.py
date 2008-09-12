# TODO: add a class to cache files that we download from the web

# TODO:
# Fixup the BuildRequires line (One requires per line, and sort them
# alphabetically)
# Actually, create a class that fixes a spec file

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
    _admin_url = 'http://tmp.vuntz.net/opensuse-packages/admin.py'
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


def _gnome_todo(self, exclude_reserved, exclude_submitted):
    def print_package(package, oF_version, GF_version, upstream_version):
        # FIXME 32 & 18 are arbitrary values. We should probably look at all
        # package names/versions and find the longer name/version
        print '%-32.32s | %-18.18s | %-18.18s | %-18.18s' % (package, oF_version, GF_version, upstream_version)


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

    # print headers
    print_package('Package', 'openSUSE:Factory', 'GNOME:Factory', 'Upstream')
    print '---------------------------------+--------------------+--------------------+-------------------'

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
            print_package(package, oF_version, GF_version, upstream_version)


#######################################################################


def _gnome_todoadmin(self, exclude_submitted):
    def print_package(package):
        # FIXME 32 & 18 are arbitrary values. We should probably look at all
        # package names/versions and find the longer name/version
        print '%-32.32s' % package


    # get packages with a delta
    try:
        packages_with_delta = self._gnome_web.get_packages_with_delta()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    # get the packages submitted to GNOME:Factory
    try:
        submitted_packages = get_submit_request_list(conf.config['apiurl'], 'openSUSE:Factory', None)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot get list of submissions to openSUSE:Factory: ' + e.msg

    # print headers
    print_package('Package')
    print '--------------------------------'

    for package in packages_with_delta:
        if self._gnome_is_submitted(package, submitted_packages):
            if exclude_submitted:
                continue
            package = package + ' (s)'
        print_package(package)

#######################################################################


def _gnome_listreserved(self):
    try:
        reserved_packages = self._gnome_web.get_reserved_packages()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    print '%-32.32s | %-12.12s' % ('Package', 'Reserved by')
    print '---------------------------------+-------------'

    for (package, username) in reserved_packages:
        # FIXME 32 & 12 are arbitrary values. We should probably look at all
        # package names/versions and find the longer name/version
        if (package and username):
            print '%-32.32s | %-12.12s' % (package, username)


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
        except:
            print >>sys.stderr, 'Error while updating package ' + package + ': ' + e.msg
            return False

    else:
        # check out the branched package
        try:
            checkout_package(apiurl, branch_project, package, expand_link=True)
            print 'Package ' + package + ' has been checked out.'
        except:
            print >>sys.stderr, 'Error while checking out package ' + package + ': ' + e.msg
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


def _gnome_update(self, package, apiurl, username, reserve = False):
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
    # TODO
    # sed -i "s/^\(Version: *\)[^ ]*/\1$VERSION/" $PACKAGE.spec
    # Maybe warn if there are other spec files? They might need an update too.

    # start adding an entry to .changes
    # not fatal if fails
    changes_file = os.path.join(package_dir, package + '.changes')
    if not os.path.exists(changes_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': no such file.'
    elif not os.path.isfile(changes_file):
        print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': not a regular file.'
    else:
        tempfile = self.OscGnomeImport.m_import('tempfile')
        time = self.OscGnomeImport.m_import('time')
        locale = self.OscGnomeImport.m_import('locale')

        if not tempfile or not time or not locale:
            print >>sys.stderr, 'Cannot update ' + os.path.basename(changes_file) + ': incomplete python installation.'
        else:
            (fdout, tmp) = tempfile.mkstemp(dir = package_dir)

            old_lc_time = locale.setlocale(locale.LC_TIME)
            locale.setlocale(locale.LC_TIME, 'C')

            os.write(fdout, '-------------------------------------------------------------------\n')
            # FIXME email address
            os.write(fdout, time.strftime("%a %b %e %H:%M:%S %Z %Y") + ' - EMAIL@ADDRESS\n')
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

            print os.path.basename(changes_file) + ' has been prepared.'


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
# Add a sanitycheck command that checks that all packages in G:F
# are valid links to o:F stuff.
# We could also check that all packages maintained by gnome-maintainers
# are in G:F.


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
        osc gnome reserve PKG
        osc gnome unreserve PKG

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
        self._gnome_update(package, conf.config['apiurl'], conf.config['user'], reserve = opts.reserve)
