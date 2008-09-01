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


def _gnome_todo(self, need_factory_sync):
    # helper functions
    def is_submitted (package, submitteds):
        for submitted in submitteds:
            if package == submitted.dst_package:
                return True

    def print_package(package, oF_version, GF_version, upstream_version = None):
        if upstream_version:
            print '%-32.32s | %-12.12s | %-12.12s | %-12.12s' % (package, oF_version, GF_version, upstream_version)
        else:
            print '%-32.32s | %-12.12s | %-12.12s' % (package, oF_version, GF_version)


    # get the packages submitted to GNOME:Factory
    submitteds = get_submit_request_list(conf.config['apiurl'], 'GNOME:Factory', None)

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
                if is_submitted(package, submitteds):
                    GF_version = GF_version + '*'
                    upstream_version = upstream_version + '*'
                print_package(package, oF_version, GF_version, upstream_version)


def _gnome_reserve(self, package, username):
    print >>sys.stderr, 'Not implemented yet.'
    pass


@cmdln.option('-f', '--need-factory-sync', action='store_true',
              dest='factory_sync',
              help='show packages needing to be merged in openSUSE:Factory')
def do_gnome(self, subcmd, opts, *args):
    """${cmd_name}: Various commands to ease collaboration within the openSUSE GNOME Team.

    "todo" will list the packages that need some action.

    "reserve" will reserve a package so other people know you're working on it.

    usage:
        osc gnome todo [--need-factory-sync|-f]
        osc gnome reserve PKG
    ${cmd_option_list}
    """

    cmds = ['todo', 'reserve']
    if not args or args[0] not in cmds:
        raise oscerr.WrongArgs('Unknown gnome action. Choose one of %s.' \
                                           % ', '.join(cmds))

    cmd = args[0]

    # Check arguments validity
    if cmd in ['todo']:
        min_args, max_args = 0, 1
    elif cmd in ['reserve']:
        min_args, max_args = 1, 1

    if len(args) - 1 < min_args:
        raise oscerr.WrongArgs('Too few arguments.')
    if len(args) - 1 > max_args:
        raise oscerr.WrongArgs('Too many arguments.')

    # Do the command
    if cmd == 'todo':
        self._gnome_todo(opts.factory_sync)

    elif cmd == 'reserve':
        package = args[1]
        self._gnome_reserve(package, conf.config['user'])
