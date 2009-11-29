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
import traceback

import buildservice
import config
import database
import hermes
import infoxml
import upstream


#######################################################################


class RunnerException(Exception):
    pass


#######################################################################


class Runner:

    def __init__(self, conf):
        """ Arguments:
            config -- a config object

        """
        self.conf = conf
        self.hermes = None
        self.obs = None
        self.upstream = None
        self.db = None
        self.xml = None

        self._status_dir = os.path.join(self.conf.cache_dir, 'status')
        self._status_file = os.path.join(self._status_dir, 'last')
        self._mirror_dir = os.path.join(self.conf.cache_dir, 'obs-mirror')
        self._upstream_dir = os.path.join(self.conf.cache_dir, 'upstream')
        self._db_dir = os.path.join(self.conf.cache_dir, 'db')
        self._xml_dir = os.path.join(self.conf.cache_dir, 'xml')

        self._status = {}
        # Last hermes event handled by mirror
        self._status['mirror'] = -1
        # Last hermes event handled by db
        self._status['db'] = -1
        # Last hermes event recorded in xml (it cannot be greater than the db one)
        self._status['xml'] = -1
        # mtime of the configuration that was last known
        self._status['conf-mtime'] = -1
        # mtime of the openSUSE configuration that was last known
        self._status['opensuse-mtime'] = -1
        # mtime of the upstream database
        self._status['upstream-mtime'] = -1


    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self.conf.debug:
            print 'Main: %s' % s


    def _read_status(self):
        """ Read the last known status of the script. """
        if not os.path.exists(self._status_file):
            return

        file = open(self._status_file)
        lines = file.readlines()
        file.close()

        for line in lines:
            line = line[:-1]
            handled = False

            for key in self._status.keys():
                if line.startswith(key + '='):
                    value = line[len(key + '='):]
                    try:
                        self._status[key] = int(value)
                    except ValueError:
                        raise RunnnerException('Cannot parse status value for %s: %s' % (key, value))

                handled = True

            if not handled:
                raise RunnnerException('Unknown status line: %s' % (line,))


    def _write_status(self):
        """ Save the last known status of the script. """
        if not os.path.exists(self._status_dir):
            os.makedirs(self._status_dir)

        tmpfilename = self._status_file + '.new'

        # it's always better to have things sorted, since it'll be predictable
        # (so better for human eyes ;-))
        items = self._status.items()
        items.sort()

        file = open(tmpfilename, 'w')
        for (key, value) in items:
            file.write('%s=%d\n' % (key, self._status[key]))
        file.close()

        os.rename(tmpfilename, self._status_file)


    def _run_mirror(self, conf_changed):
        if not os.path.exists(self._mirror_dir):
            os.makedirs(self._mirror_dir)

        if self.conf.skip_mirror:
            return

        if not self.conf.force_hermes and (self._status['mirror'] == -1 or conf_changed):
            # we don't know how old our mirror is, or the configuration has
            # changed

            # get a max id from hermes feeds
            self.hermes.fetch_last_known_id()

            # checkout the projects (or look if we need to update them)
            for name in self.conf.projects.keys():
                if self.conf.mirror_only_new:
                    if os.path.exists(os.path.join(self._mirror_dir, name)):
                        continue

                self.obs.queue_checkout_project(name)

        else:
            # update the relevant part of the mirror

            # get events from hermes
            self.hermes.read()

            # reverse to have chronological order
            events = self.hermes.get_events(self._status['mirror'], reverse = True)

            for event in events:
                # ignore events that belong to a project we do not monitor
                # (ie, there's no checkout)
                project_dir = os.path.join(self._mirror_dir, event.project)
                if not os.path.exists(project_dir):
                    continue

                if isinstance(event, hermes.HermesEventCommit):
                    self.obs.queue_checkout_package(event.project, event.package)

                elif isinstance(event, hermes.HermesEventProjectDeleted):
                    # Even if there's a later commit to the same project (which
                    # is unlikely), we wouldn't know which packages are still
                    # relevant, so it's better to remove the project to not
                    # have unexisting packages in the database. The unlikely
                    # case will eat a bit more resources, but it's really
                    # unlikely to happen anyway.
                    self.obs.remove_checkout_project(event.project)

                elif isinstance(event, hermes.HermesEventPackageMeta):
                    # Note that the ObsCheckout object will automatically check out
                    # devel projects that have appeared via metadata change, if
                    # necessary.
                    self.obs.queue_checkout_package_meta(event.project, event.package)

                elif isinstance(event, hermes.HermesEventPackageAdded):
                    # The pkgmeta file of the project won't have anything about
                    # this package, so we need to download the metadata too.
                    self.obs.queue_checkout_package(event.project, event.package)
                    self.obs.queue_checkout_package_meta(event.project, event.package)

                elif isinstance(event, hermes.HermesEventPackageDeleted):
                    self.obs.remove_checkout_package(event.project, event.package)

        self.obs.run()


    def _run_db(self, conf_changed):
        """ Return if a full rebuild was done, and if anything has been updated. """
        if self.conf.skip_db:
            return (False, False)

        if (self.conf.force_db or not self.db.exists() or
            (not self.conf.force_hermes and (conf_changed or self._status['db'] == -1))):
            # The database doesn't exist, the configuration has changed, or
            # we don't have the whole list of events that have happened since
            # the last database update. So we just rebuild it from scratch.
            self.db.rebuild()

            return (True, True)
        else:
            # update the relevant parts of the db

            # reverse to have chronological order
            events = self.hermes.get_events(self._status['db'], reverse = True)

            if len(events) == 0:
                return (False, False)

            changed = False

            for event in events:
                # ignore events that belong to a project we do not monitor
                # (ie, there's no checkout)
                project_dir = os.path.join(self._mirror_dir, event.project)
                if not os.path.exists(project_dir):
                    continue

                changed = True

                if isinstance(event, hermes.HermesEventCommit):
                    self.db.update_package(event.project, event.package)

                elif isinstance(event, hermes.HermesEventProjectDeleted):
                    self.db.remove_project(event.project)

                elif isinstance(event, hermes.HermesEventPackageMeta):
                    # Note that the ObsDb object will automatically add the
                    # devel projects to the database, if necessary.
                    self.db.update_package(event.project, event.package)

                elif isinstance(event, hermes.HermesEventPackageAdded):
                    self.db.add_package(event.project, event.package)

                elif isinstance(event, hermes.HermesEventPackageDeleted):
                    self.db.remove_package(event.project, event.package)

            return (False, changed)

    def _remove_stale_data(self):
        if self.conf.skip_mirror and self.conf.skip_db and self.conf.skip_xml:
            return

        if self.conf.skip_db and not self.db.exists():
            # If there's no database, but we skip its creation, it's not a bug
            return

        # If one project exists in the database, but it's not an explicitly
        # requested project, nor a devel project that we should have, then we
        # can safely remove it from the mirror and from the database
        requested_projects = self.conf.projects.keys()

        needed = []
        for project in requested_projects:
            needed.append(project)
            if self.conf.projects[project].checkout_devel_projects:
                needed.extend(self.db.get_devel_projects(project))
        needed = set(needed)

        db_projects = set(self.db.get_projects())
        unneeded = db_projects.difference(needed)
        for project in unneeded:
            if not self.conf.skip_xml:
                self.xml.remove_project(project)
            if not self.conf.skip_db:
                self.db.remove_project(project)
            if not self.conf.skip_mirror:
                self.obs.remove_checkout_project(project)

        if self.conf.skip_mirror and self.conf.skip_xml:
            return

        # We now have "projects in the db" = needed
        db_projects = needed

        if not self.conf.skip_mirror:
            # If one project exists in the mirror but not in the db, then it's
            # stale data from the mirror that we can remove.
            mirror_projects = set([ subdir for subdir in os.listdir(self._mirror_dir) if os.path.isdir(subdir) ])
            unneeded = mirror_projects.difference(db_projects)
            for project in unneeded:
                self.obs.remove_checkout_project(project)

        if not self.conf.skip_xml:
            # If one project exists in the xml but not in the db, then it's
            # stale data that we can remove.
            xml_projects = set([ file for file in os.listdir(self._xml_dir) if file.endswith('.xml') ])
            unneeded = xml_projects.difference(db_projects)
            for project in unneeded:
                self.xml.remove_project(project)


    def run(self):
        """ Run the various steps of the script."""
        # Get the previous status, and some info about what will be the new one
        self._read_status()

        if self.conf.filename:
            stats = os.stat(self.conf.filename)
            new_conf_mtime = stats.st_mtime
        else:
            new_conf_mtime = -1

        if self.conf.use_opensuse:
            new_opensuse_mtime = self.conf.get_opensuse_mtime()
        else:
            new_opensuse_mtime = -1

        conf_changed = (self._status['conf-mtime'] != new_conf_mtime or
                        self._status['opensuse-mtime'] != new_opensuse_mtime)

        # Setup hermes, it will be call before the mirror update, depending on
        # what we need
        self.hermes = hermes.HermesReader(min(self._status['mirror'], self._status['db']), self.conf.hermes_urls, self.conf)

        # Run the mirror update, and make sure to update the status afterwards
        # in case we crash later
        self.obs = buildservice.ObsCheckout(self.conf, self._mirror_dir)
        self._run_mirror(conf_changed)

        if not self.conf.mirror_only_new and not self.conf.skip_mirror:
            # we don't want to lose events if we went to fast mode once
            self._status['mirror'] = self.hermes.last_known_id
        self._write_status()

        # Update/create the upstream database
        self.upstream = upstream.UpstreamDb(self._upstream_dir, self._db_dir, self.conf.debug)
        if not self.conf.skip_upstream:
            self.upstream.update(self.conf.projects, self.conf.force_upstream)
        new_upstream_mtime = self.upstream.get_mtime()

        # Update/create the package database
        self.db = database.ObsDb(self.conf, self._db_dir, self._mirror_dir, self.upstream)
        (db_full_rebuild, db_changed) = self._run_db(conf_changed)

        if not self.conf.mirror_only_new and not self.conf.skip_db:
            # we don't want to lose events if we went to fast mode once
            self._status['db'] = self.hermes.last_known_id

        if not self.conf.skip_db and not self.conf.skip_upstream and not db_full_rebuild:
            # There's no point a looking at the upstream changes if we did a
            # full rebuild anyway
            upstream_changed = self.db.upstream_changes(self._status['upstream-mtime'])
            self._status['upstream-mtime'] = new_upstream_mtime
        else:
            upstream_changed = False

        # Prepare the creation of xml files
        self.xml = infoxml.InfoXml(self._xml_dir, self.conf.debug)

        # Post-analysis to remove stale data, or enhance the database
        self._remove_stale_data()

        if not self.conf.skip_db:
            if db_changed or upstream_changed:
                self.db.post_analyze()
            else:
                self._debug_print('No need to run the post-analysis')

        # Create xml last, after we have all the right data
        if not self.conf.skip_xml:
            # Note that if the xml id is not in sync with the db one, then it means
            # we have to regenerate the xml.
            if (self.conf.force_xml or
                db_changed or upstream_changed or
                self._status['xml'] != self._status['db']):
                self.xml.run(self.db.get_cursor())
            else:
                self._debug_print('No need to generate XML files')

        if not self.conf.skip_xml:
            # if we didn't skip the xml step, then we are at the same point as
            # the db
            self._status['xml'] = self._status['db']

        self._status['conf-mtime'] = new_conf_mtime
        self._status['opensuse-mtime'] = new_opensuse_mtime

        self._write_status()


#######################################################################


def get_conf(args):
    parser = optparse.OptionParser()

    parser.add_option('--config', dest='config',
                      help='configuration file to use')
    parser.add_option('--opensuse', dest='opensuse',
                      action='store_true', default=False,
                      help='use the openSUSE config as a basis')

    (options, args) = parser.parse_args()

    try:
        conf = config.Config(options.config, use_opensuse = options.opensuse)
    except config.ConfigException, e:
        print >>sys.stderr, e
        return (args, None)

    if conf.sockettimeout > 0:
        # we have a setting for the default socket timeout to not hang forever
        socket.setdefaulttimeout(conf.sockettimeout)

    try:
        os.makedirs(conf.cache_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            print >>sys.stderr, 'Cannot create cache directory.'
            return (args, None)

    return (args, conf)


#######################################################################


def lock_run(conf):
    # FIXME: this is racy, we need a real lock file. Or use an atomic operation
    # like mkdir instead
    running_file = os.path.join(conf.cache_dir, 'running')
    if os.path.exists(running_file):
        print >>sys.stderr, 'Another instance of the script is running.'
        return False

    open(running_file, 'w').write('')

    return True


def unlock_run(conf):
    running_file = os.path.join(conf.cache_dir, 'running')
    os.unlink(running_file)


#######################################################################


def main(args):
    (args, conf) = get_conf(args)
    if not conf:
        return 1

    if not lock_run(conf):
        return 1

    runner = Runner(conf)

    retval = 1

    try:
        runner.run()
        retval = 0
    except Exception, e:
        if isinstance(e, (RunnerException, config.ConfigException, hermes.HermesException, database.ObsDbException, infoxml.InfoXmlException)):
            print >>sys.stderr, e
        else:
            traceback.print_exc()

    unlock_run(conf)

    return retval


if __name__ == '__main__':
    try:
      ret = main(sys.argv)
      sys.exit(ret)
    except KeyboardInterrupt:
      pass
