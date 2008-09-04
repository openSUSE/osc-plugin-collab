class OscGnomeWebError(Exception):
    def __init__(self, value):
        self.msg = value

    def __str__(self):
        return repr(self.msg)


#######################################################################


class OscGnomeWeb:

    _reserve_url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
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
            return

        return (oF_version, GF_version, upstream_version)


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
    if not self._gnome_rpm_tried:
        self._gnome_rpm_tried = True
        try:
            self._gnome_rpm_module = __import__('rpm')
        except ImportError:
            self._gnome_rpm_module = None

    if self._gnome_rpm_module:
        # We're not really interested in the epoch or release parts of the
        # complete version because they're not relevant when comparing to
        # upstream version
        return self._gnome_rpm_module.labelCompare((None, a, '1'), (None, b, '1')) > 0

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


#######################################################################


def _gnome_todo(self, need_factory_sync, exclude_reserved, exclude_submitted):
    # helper functions
    def is_submitted(package, submitted_packages):
        for submitted in submitted_packages:
            if package == submitted.dst_package:
                return True

    def print_package(package, oF_version, GF_version, upstream_version = None):
        # FIXME 32 & 20 (no better than the old choices of 32 & 12) are arbitrary
        # values. We should probably look at all package names/versions and find
        # the longer name/version
        if upstream_version:
            print '%-32.32s | %-20.20s | %-20.20s | %-20.20s' % (package, oF_version, GF_version, upstream_version)
        else:
            print '%-32.32s | %-20.20s | %-20.20s' % (package, oF_version, GF_version)


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
    if need_factory_sync:
        print_package('Package', 'openSUSE:Factory', 'GNOME:Factory')
        print '---------------------------------+--------------+-------------'
    else:
        print_package('Package', 'openSUSE:Factory', 'GNOME:Factory', 'Upstream')
        print '---------------------------------+--------------+--------------+-------------'

    for (package, oF_version, GF_version, upstream_version) in packages_versions:
        if need_factory_sync:
            if self._gnome_compare_versions_a_gt_b(GF_version, oF_version):
                print_package(package, oF_version, GF_version)
        else:
            # empty upstream version
            if upstream_version == '':
                continue

            if self._gnome_needs_update(oF_version, GF_version, upstream_version):
                if is_submitted(package, submitted_packages):
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


def _gnome_listreserved(self):
    try:
        reserved_packages = self._gnome_web.get_reserved_packages()
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    print '%-32.32s | %-20.20s' % ('Package', 'Reserved by')
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

    # is it reserved?
    try:
        reserved_by = self._gnome_web.is_package_reserved(package)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    if not reserve:
        # check that we already have reserved the package
        if not reserved_by:
            print 'Please reserve the package ' + package + ' first.'
            return
        elif reserved_by != username:
            print 'Package ' + package + ' is already reserved by ' + reserved_by + '.'
            return
    elif reserved_by and reserved_by != username:
        print 'Package ' + package + ' is already reserved by ' + reserved_by + '.'
        return
    elif not reserved_by:
        # reserve the package
        try:
            self._gnome_web.reserve_package(package, username)
            print 'Package ' + package + ' has been reserved for 36 hours.'
            print 'Do not forget to unreserve the package when done with it:'
            print '    osc gnome unreserve ' + package
        except self.OscGnomeWebError, e:
            print >>sys.stderr, e.msg
            return

    # look if we already have a branch, and if not branch the package
    try:
        expected_branch_project = 'home:' + username + ':branches:GNOME:Factory'
        show_package_meta(apiurl, expected_branch_project, package)
        branch_project = expected_branch_project
        # it worked, we already have the branch
    except urllib2.HTTPError, e:
        if e.code != 404:
            print >>sys.stderr, 'Error while checking if package ' + package + ' was already branched: ' + e.msg
            return
        # We had a 404: it means the branched package doesn't exist yet
        try:
            branch_project = branch_pkg(apiurl, 'GNOME:Factory', package, nodevelproject = True)
            print 'Package ' + package + ' has been branched in project ' + branch_project + '.'
        except urllib2.HTTPError, e:
            print >>sys.stderr, 'Error while branching package ' + package + ': ' + e.msg
            return

    # check out the branched package
    if os.path.exists(package):
        # maybe we already checked it out before?
        if not os.path.isdir(package):
            print >>sys.stderr, 'File ' + package + ' already exists but is not a directory.'
            return
        elif not is_package_dir(package):
            print >>sys.stderr, 'Directory ' + package + ' already exists but is not a checkout of a Build Service package.'
            return

        obs_package = filedir_to_pac(package)
        if obs_package.name != package or obs_package.prjname != branch_project:
            print >>sys.stderr, 'Directory ' + package + ' already exists but is a checkout of package ' + obs_package.name + ' from project ' + obs_package.prjname +'.'
            return

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
            return

    else:
        # check out the branched package
        try:
            checkout_package(apiurl, branch_project, package, expand_link=True)
            print 'Package ' + package + ' has been checked out.'
        except:
            print >>sys.stderr, 'Error while checking out package ' + package + ': ' + e.msg
            return

    # TODO
    # edit the version tag in the .spec files
    # sed -i "s/^\(Version: *\)[^ ]*/\1$VERSION/" $PACKAGE.spec
    # Maybe warn if there are other spec files? They might need an update too.

    # start adding an entry to .changes
    changes_file = os.path.join(package, package + '.changes')
    if not os.path.exists(changes_file):
        print >>sys.stderr, 'Cannot update ' + package + '.changes: no such file.'
    elif not os.path.isfile(changes_file):
        print >>sys.stderr, 'Cannot update ' + package + '.changes: not a regular file.'
    else:
        try:
            tempfile = __import__('tempfile')
            time = __import__('time')
            locale = __import__('locale')

            (fdout, tmp) = tempfile.mkstemp(dir = package)

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
                os.write(fdout, bytes)
                if len(bytes) == 0:
                    break
            fin.close()
            os.close(fdout)

            os.rename(tmp, changes_file)

            print changes_file + ' has been prepared.'
        except ImportError:
            print >>sys.stderr, 'Cannot update ' + package + '.changes: incomplete python installation.'


    # TODO
    # download the updated tarball and md5/sha1

    # TODO
    # extract NEWS & ChangeLog from the new tarball

    # TODO
    # 'osc add newfile.tar.bz2' and 'osc del oldfile.tar.bz2'

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
@cmdln.option('-f', '--need-factory-sync', action='store_true',
              dest='factory_sync',
              help='show packages needing to be merged in openSUSE:Factory')
@cmdln.option('-r', '--reserve', action='store_true',
              dest='reserve',
              help='also reserve the package')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" (or "t") will list the packages that need some action.

    "listreserved" (or "lr") will list the reserved packages.

    "isreserved" (or "ir") will look if a package is reserved.

    "reserve" (or "r") will reserve a package so other people know you're
    working on it.

    "unreserve" (or "u") will remove the reservation you had on a package.

    "update" (or "up") will prepare a package for update (possibly reservation,
    branch, checking out, etc.). The package will be checked out in the current
    directory.

    Usage:
        osc gnome todo [--need-factory-sync|-f] [--exclude-reserved|--xr] [--exclude-submitted|--xs]
        osc gnome listreserved
        osc gnome isreserved PKG
        osc gnome reserve PKG
        osc gnome unreserve PKG
        osc gnome update [--reserve|-r] PKG
    ${cmd_option_list}
    """

    cmds = ['todo', 't', 'listreserved', 'lr', 'isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u', 'update', 'up']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved', 'lr', 'todo', 't']:
        min_args, max_args = 0, 0
    elif cmd in ['isreserved', 'ir', 'update', 'up']:
        min_args, max_args = 1, 1
    elif cmd in ['reserve', 'r', 'unreserve', 'u']:
        min_args = 1

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if not cmd in ['reserve', 'r', 'unreserve', 'u']:
        if len(args) - 1 > max_args:
            raise oscerr.WrongArgs('Too many arguments.')

    self._gnome_web = self.OscGnomeWeb(self.OscGnomeWebError)
    self._gnome_rpm_tried = False

    # Do the command
    if cmd in ['todo', 't']:
        self._gnome_todo(opts.factory_sync, opts.exclude_reserved, opts.exclude_submitted)

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

    elif cmd in ['update', 'up']:
        package = args[1]
        self._gnome_update(package, conf.config['apiurl'], conf.config['user'], reserve = opts.reserve)

