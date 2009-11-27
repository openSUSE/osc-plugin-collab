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

        self._status_dir = os.path.join(self.conf.cache_dir, 'status')
        self._status_file = os.path.join(self._status_dir, 'last')
        self._mirror_dir = os.path.join(self.conf.cache_dir, 'obs-mirror')
        self._upstream_dir = os.path.join(self.conf.cache_dir, 'upstream')
        self._db_dir = os.path.join(self.conf.cache_dir, 'db')


    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self.conf.debug:
            print 'Main: %s' % s


    def _read_status(self):
        """ Read the last known status of the script. """
        if not os.path.exists(self._status_file):
            return (-1, -1, -1, -1)

        file = open(self._status_file)
        lines = file.readlines()
        file.close()

        last_mirror_id = -1
        last_db_id = -1
        conf_mtime = -1
        upstream_mtime = -1

        for line in lines:
            line = line[:-1]
            if line.startswith('mirror='):
                value = line[len('mirror='):]
                try:
                    last_mirror_id = int(value)
                except ValueError:
                    raise HRunnnerException('Cannot parse last event id handled by mirror: %s' % value)

            elif line.startswith('db='):
                value = line[len('db='):]
                try:
                    last_db_id = int(value)
                except ValueError:
                    raise HRunnnerException('Cannot parse last event id handled by db: %s' % value)

            elif line.startswith('conf-mtime='):
                value = line[len('conf-mtime='):]
                try:
                    conf_mtime = int(value)
                except ValueError:
                    raise HRunnnerException('Cannot parse configuration file mtime: %s' % value)

            elif line.startswith('upstream-mtime='):
                value = line[len('upstream-mtime='):]
                try:
                    upstream_mtime = int(value)
                except ValueError:
                    raise HRunnnerException('Cannot parse upstream database mtime: %s' % value)

            else:
                raise RunnnerException('Unknown status line: %s' % (line,))

        return (last_mirror_id, last_db_id, conf_mtime, upstream_mtime)


    def _write_status(self, last_mirror_id, last_db_id, conf_mtime, upstream_mtime):
        """ Save the last known status of the script.

            Arguments:
            last_mirror_id -- id of the last event handled by the mirror cache
            last_db_id -- id if the last event used to create the database
            conf_mtime -- mtime of the configuration file
            upstream_mtime -- mtime of the last write to the upstream database
        
        """
        if not os.path.exists(self._status_dir):
            os.makedirs(self._status_dir)

        tmpfilename = self._status_file + '.new'

        file = open(tmpfilename, 'w')
        file.write('mirror=%d\n' % last_mirror_id)
        file.write('db=%d\n' % last_db_id)
        file.write('conf-mtime=%d\n' % conf_mtime)
        file.write('upstream-mtime=%d\n' % upstream_mtime)
        file.close()

        os.rename(tmpfilename, self._status_file)


    def _run_mirror(self, last_mirror_id, mtime_changed):
        if not os.path.exists(self._mirror_dir):
            os.makedirs(self._mirror_dir)

        if self.conf.skip_mirror:
            return

        if last_mirror_id == -1 or mtime_changed:
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
            events = self.hermes.get_events(last_mirror_id, reverse = True)

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


    def _run_db(self, last_mirror_id, last_db_id, mtime_changed):
        """ Return if a full rebuild was done, and if anything has been updated. """
        if self.conf.skip_db:
            return (False, False)

        if (self.conf.force_db or not self.db.exists() or
            mtime_changed or last_db_id == -1):
            # The database doesn't exist, the configuration has changed, or
            # we don't have the whole list of events that have happened since
            # the last database update. So we just rebuild it from scratch.
            self.db.rebuild()

            return (True, True)
        else:
            # update the relevant parts of the db

            # reverse to have chronological order
            events = self.hermes.get_events(last_db_id, reverse = True)

            if len(events) == 0:
                return (False, False)

            for event in events:
                # ignore events that belong to a project we do not monitor
                # (ie, there's no checkout)
                project_dir = os.path.join(self._mirror_dir, event.project)
                if not os.path.exists(project_dir):
                    continue

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

            return (False, True)

    def _run_post_analysis(self):
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

        unneeded = []
        db_projects = self.db.get_projects()
        for project in db_projects:
            if not project in needed:
                unneeded.append(project)

        for project in unneeded:
            self.db.remove_project(project)
            self.obs.remove_checkout_project(project)

        # If one project exists in the mirror but not in the db, then it's
        # stale data from the mirror that we can remove.
        db_projects = self.db.get_projects()
        mirror_projects = [ subdir for subdir in os.listdir(self._mirror_dir) if os.path.isdir(subdir) ]
        for project in mirror_projects:
            if project not in db_projects:
                self.obs.remove_checkout_project(project)

        self.db.post_analyze()


    def run(self):
        """ Run the various steps of the script."""
        # Get the previous status, and some info about what will be the new one
        stats = os.stat(self.conf.filename)
        new_conf_mtime = stats.st_mtime

        (last_mirror_id, last_db_id, conf_mtime, upstream_mtime) = self._read_status()

        mtime_changed = (conf_mtime != new_conf_mtime) and not self.conf.force_hermes

        # Setup hermes, it will be call before the mirror update, depending on
        # what we need
        self.hermes = hermes.HermesReader(min(last_mirror_id, last_db_id), self.conf.hermes_urls, self.conf)

        # Run the mirror update, and make sure to update the status afterwards
        # in case we crash later
        self.obs = buildservice.ObsCheckout(self.conf, self._mirror_dir)
        self._run_mirror(last_mirror_id, mtime_changed)
        self._write_status(self.hermes.last_known_id, last_db_id, conf_mtime, upstream_mtime)

        # Setup the upstream database, and update/create the package database
        self.upstream = upstream.UpstreamDb(self.conf.projects, self._upstream_dir, self._db_dir, self.conf.debug)
        new_upstream_mtime = self.upstream.get_mtime()

        self.db = database.ObsDb(self.conf, self._db_dir, self._mirror_dir, self.upstream)
        (db_full_rebuild, db_changed) = self._run_db(last_mirror_id, last_db_id, mtime_changed)

        if not db_full_rebuild:
            upstream_changed = self.db.upstream_changes(upstream_mtime)
        else:
            upstream_changed = False

        # Post-analysis to remove stale data
        if db_changed or upstream_changed:
            self._run_post_analysis()
        else:
            self._debug_print('No need to run the post-analysis')

        # create xml
        # TODO

        if not self.conf.mirror_only_new:
            self._write_status(self.hermes.last_known_id, self.hermes.last_known_id, new_conf_mtime, new_upstream_mtime)
        else:
            # we don't want to lose events if we went to fast mode once
            self._write_status(last_mirror_id, last_db_id, new_conf_mtime, new_upstream_mtime)


#######################################################################


def main(args):
    parser = optparse.OptionParser()

    parser.add_option('--config', dest='config',
                      help='configuration file to use')

    (options, args) = parser.parse_args()

    try:
        if options.config:
            conf = config.Config(options.config)
        else:
            conf = config.Config()
    except config.ConfigException, e:
        print >>sys.stderr, e
        return 1

    if conf.sockettimeout > 0:
        # we have a setting for the default socket timeout to not hang forever
        socket.setdefaulttimeout(conf.sockettimeout)

    try:
        os.makedirs(conf.cache_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            print >>sys.stderr, 'Cannot create cache directory.'
            return 1

    # FIXME: this is racy, we need a real lock file. Or use an atomic operation
    # like mkdir instead
    running_file = os.path.join(conf.cache_dir, 'running')
    if os.path.exists(running_file):
        print >>sys.stderr, 'Another instance of the script is running.'
        return 1

    open(running_file, 'w').write('')

    runner = Runner(conf)

    retval = 1

    try:
        runner.run()
        retval = 0
    except Exception, e:
        if isinstance(e, hermes.HermesException) or isinstance(e, RunnerException):
            print >>sys.stderr, e
        else:
            traceback.print_exc()

    os.unlink(running_file)

    return retval


if __name__ == '__main__':
    try:
      ret = main(sys.argv)
      sys.exit(ret)
    except KeyboardInterrupt:
      pass
