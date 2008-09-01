# TODO: put this in a common library -- it's used in the examples too
def _gnome_compare_versions_a_gt_b (self, a, b):
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


def _gnome_parse_reservation(self, line):
    try:
        (package, username, comment) = line[:-1].split(';')
        return (package, username, comment)
    except ValueError:
        print >>sys.stderr, 'Cannot parse reservation information: ' + line[:-1]
        return (None, None, None)

#######################################################################


def _gnome_todo(self, need_factory_sync):
    # helper functions
    def is_submitted (package, submitted_packages):
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


    # get the list of reserved package
    reserved_packages = []
    try:
        fd = urllib2.urlopen('http://tmp.vuntz.net/opensuse-packages/reserve.py?mode=getall')
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot get list of reserved packages: ' + e.msg

    lines = fd.readlines()
    fd.close()

    # it returns a status code on the first line, and then one package per line
    # if the status code is 200
    if lines[0][:3] != '200':
        print >>sys.stderr, 'Error while getting list of reserved packages: ' + lines[0][4:-1]
    else:
        del lines[0]
        for line in lines:
            (package, username, comment) = self._gnome_parse_reservation (line)
            if package:
                reserved_packages.append(package)

    # get the packages submitted to GNOME:Factory
    submitted_packages = get_submit_request_list(conf.config['apiurl'], 'GNOME:Factory', None)

    # get the current versions of packages
    try:
        fd = urllib2.urlopen('http://tmp.vuntz.net/opensuse-packages/obs.py?format=csv')
    except urllib2.HTTPError:
        # FIXME: do we want a custom message?
        raise

    lines = fd.readlines()
    fd.close()

    # print headers
    if need_factory_sync:
        print_package('Package', 'openSUSE:Factory', 'GNOME:Factory')
        print '---------------------------------+--------------+-------------'
    else:
        print_package('Package', 'openSUSE:Factory', 'GNOME:Factory', 'Upstream')
        print '---------------------------------+--------------+--------------+-------------'

    for line in lines:
        try:
            (package, oF_version, GF_version, upstream_version, empty) = line.split(';')
        except ValueError:
            print >>sys.stderr, 'Cannot parse line: ' + line[:-1]
            continue

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
                    upstream_version = upstream_version + '*'
                print_package(package, oF_version, GF_version, upstream_version)


#######################################################################


def _gnome_listreserved(self):
    url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
    try:
        fd = urllib2.urlopen(url + '?mode=getall')
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot list reserved packages: ' + e.msg
        return

    lines = fd.readlines()
    fd.close()

    if lines[0][:3] != '200':
        print >>sys.stderr, 'Cannot list reserved packages: ' + lines[0][4:-1]
        return

    del lines[0]

    print '%-32.32s | %-12.12s' % ('Package', 'Reserved by')
    print '---------------------------------+-------------'

    for line in lines:
        (package, username, comment) = self._gnome_parse_reservation (line)
        # FIXME 32 & 12 are arbitrary values. We should probably look at all
        # package names/versions and find the longer name/version
        if (package and username):
            print '%-32.32s | %-12.12s' % (package, username)


#######################################################################


def _gnome_isreserved(self, package):
    url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
    try:
        fd = urllib2.urlopen(url + '?mode=get&package=' + package)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot look if package ' + package + ' is reserved: ' + e.msg
        return

    line = fd.readline()
    fd.close()

    if line[:3] != '200':
        print >>sys.stderr, 'Cannot look if package ' + package + ' is reserved: ' + line[4:-1]
        return

    (package, username, comment) = self._gnome_parse_reservation (line[4:])
    if not username:
        return

    if username == '':
        print 'Package is not reserved.'
    else:
        print 'Package ' + package + ' is reserved by ' + username + '.'


#######################################################################


def _gnome_reserve(self, package, username):
    url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
    try:
        fd = urllib2.urlopen(url + '?mode=set&user=' + username + '&package=' + package)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot reserve package ' + package + ': ' + e.msg
        return

    line = fd.readline()
    fd.close()

    if line[:3] != '200':
        print >>sys.stderr, 'Cannot reserve package ' + package + ': ' + line[4:-1]
        return

    print 'Package ' + package + ' reserved for 36 hours.'
    print 'Do not forget to unreserve the package when done with it:'
    print '    osc gnome unreserve ' + package


#######################################################################


def _gnome_unreserve(self, package, username):
    url = 'http://tmp.vuntz.net/opensuse-packages/reserve.py'
    try:
        fd = urllib2.urlopen(url + '?mode=unset&user=' + username + '&package=' + package)
    except urllib2.HTTPError, e:
        print >>sys.stderr, 'Cannot unreserve package ' + package + ': ' + e.msg
        return

    line = fd.readline()
    fd.close()

    if line[:3] != '200':
        print >>sys.stderr, 'Cannot unreserve package ' + package + ': ' + line[4:-1]
        return

    print 'Package ' + package + ' unreserved.'


#######################################################################


@cmdln.option('-f', '--need-factory-sync', action='store_true',
              dest='factory_sync',
              help='show packages needing to be merged in openSUSE:Factory')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" will list the packages that need some action.

    "listreserved" will list the reserved packages.

    "isreserved" will look if a package is reserved.

    "reserve" will reserve a package so other people know you're working on it.

    "unreserve" will remove the reservation you had on a package.

    usage:
        osc gnome todo [--need-factory-sync|-f]
        osc gnome listreserved
        osc gnome isreserved PKG
        osc gnome reserve PKG
        osc gnome unreserve PKG
    ${cmd_option_list}
    """

    cmds = ['todo', 'listreserved', 'isreserved', 'reserve', 'unreserve']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['listreserved']:
        min_args, max_args = 0, 0
    elif cmd in ['todo']:
        min_args, max_args = 0, 1
    elif cmd in ['isreserved', 'reserve', 'unreserve']:
        min_args, max_args = 1, 1

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    # Do the command
    if cmd == 'todo':
        self._gnome_todo(opts.factory_sync)

    elif cmd == 'listreserved':
        self._gnome_listreserved()

    elif cmd == 'isreserved':
        package = args[1]
        self._gnome_isreserved(package)

    elif cmd == 'reserve':
        package = args[1]
        self._gnome_reserve(package, conf.config['user'])

    elif cmd == 'unreserve':
        package = args[1]
        self._gnome_unreserve(package, conf.config['user'])
