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
        except urllib2.HTTPError:
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


#######################################################################


def _gnome_todo(self, need_factory_sync, exclude_reserved):
    try:
        self._gnome_rpm_module = __import__('rpm')
    except ImportError:
        self._gnome_rpm_module = None

    # helper functions
    def is_submitted(package, submitted_packages):
        for submitted in submitted_packages:
            if package == submitted.dst_package:
                return True

    def print_package(package, oF_version, GF_version, upstream_version = None):
        # FIXME 32 & 12 are arbitrary values. We should probably look at all
        # package names/versions and find the longer name/version
        if upstream_version:
            print '%-32.32s | %-12.12s | %-12.12s | %-12.12s' % (package, oF_version, GF_version, upstream_version)
        else:
            print '%-32.32s | %-12.12s | %-12.12s' % (package, oF_version, GF_version)


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
    submitted_packages = get_submit_request_list(conf.config['apiurl'], 'GNOME:Factory', None)

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

            if self._gnome_compare_versions_a_gt_b(upstream_version, oF_version) and self._gnome_compare_versions_a_gt_b(upstream_version, GF_version):
                if is_submitted(package, submitted_packages):
                    GF_version = GF_version + '*'
                    upstream_version = upstream_version + '*'
                if package in reserved_packages:
                    if exclude_reserved:
                        continue
                    upstream_version = upstream_version + '*'
                print_package(package, oF_version, GF_version, upstream_version)


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


def _gnome_reserve(self, package, username):
    try:
        self._gnome_web.reserve_package(package, username)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    print 'Package ' + package + ' reserved for 36 hours.'
    print 'Do not forget to unreserve the package when done with it:'
    print '    osc gnome unreserve ' + package


#######################################################################


def _gnome_unreserve(self, package, username):
    try:
        self._gnome_web.unreserve_package(package, username)
    except self.OscGnomeWebError, e:
        print >>sys.stderr, e.msg
        return

    print 'Package ' + package + ' unreserved.'


#######################################################################


@cmdln.option('-x', '--exclude-reserved', action='store_true',
              dest='exclude_reserved',
              help='do not show reserved packages in the output')
@cmdln.option('-f', '--need-factory-sync', action='store_true',
              dest='factory_sync',
              help='show packages needing to be merged in openSUSE:Factory')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" (or "t") will list the packages that need some action.

    "listreserved" (or "lr") will list the reserved packages.

    "isreserved" (or "ir") will look if a package is reserved.

    "reserve" (or "r") will reserve a package so other people know you're
    working on it.

    "unreserve" (or "u") will remove the reservation you had on a package.

    Usage:
        osc gnome todo [--need-factory-sync|-f] [--exclude-reserved|-x]
        osc gnome listreserved
        osc gnome isreserved PKG
        osc gnome reserve PKG
        osc gnome unreserve PKG
    ${cmd_option_list}
    """

    cmds = ['todo', 't', 'listreserved', 'lr', 'isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved', 'lr', 'todo', 't']:
        min_args, max_args = 0, 0
    elif cmd in ['isreserved', 'ir', 'reserve', 'r', 'unreserve', 'u']:
        min_args, max_args = 1, 1

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    self._gnome_web = self.OscGnomeWeb(self.OscGnomeWebError)

    # Do the command
    if cmd in ['todo', 't']:
        self._gnome_todo(opts.factory_sync, opts.exclude_reserved)

    elif cmd in ['listreserved', 'lr']:
        self._gnome_listreserved()

    elif cmd in ['isreserved', 'ir']:
        package = args[1]
        self._gnome_isreserved(package)

    elif cmd in ['reserve', 'r']:
        package = args[1]
        self._gnome_reserve(package, conf.config['user'])

    elif cmd in ['unreserve', 'u']:
        package = args[1]
        self._gnome_unreserve(package, conf.config['user'])
