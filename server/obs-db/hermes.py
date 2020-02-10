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

import re
import urllib.parse

import feedparser

#######################################################################


class HermesException(Exception):
    pass


#######################################################################


# Note: we subclass object because we need super
class HermesEvent(object):

    regexp = None
    raw_type = None

    def __init__(self, id, title, summary):
        self.id = id
        self.project = None
        self.package = None
        self.raw = False

        if self.raw_type:
            if title == 'Notification %s arrived!' % self.raw_type:
                self.raw = True
                for line in summary.split('\n'):
                    if not self.project and line.startswith('   project = '):
                        self.project = line[len('   project = '):]
                    elif not self.package and line.startswith('   package = '):
                        self.package = line[len('   package = '):]


    @classmethod
    def is_type_for_title(cls, title):
        """ Determines if a feed entry belongs to the event class.

            The match is based on the title of the feed entry, that is passed
            through a regular expression.

        """
        if cls.raw_type:
            if title == 'Notification %s arrived!' % cls.raw_type:
                return True

        if not cls.regexp:
            return False

        match = cls.regexp.match(title)
        return match != None


    def is_project_event(self):
        """ Return True if the event is for a project and not a package. """
        return False


    def is_package_event(self):
        """ Return True if the event is for a package and not a project. """
        return False


#######################################################################


class HermesEventCommit(HermesEvent):

    regexp = re.compile('OBS ([^/\s]*)/([^/\s]*) r\d* commited')
    raw_type = 'obs_srcsrv_commit'

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        if self.raw:
            return

        match = self.regexp.match(title)

        # for some reason, not using str() sometimes make our requests to the
        # build service using those variables fail. I have absolutely no reason
        # why. It fails with "X-Error-Info: Request Line did not contain
        # request URI. The request that was received does not appear to be a
        # valid HTTP request. Please verify that your application uses HTTP"
        self.project = str(match.group(1))
        self.package = str(match.group(2))


    def is_package_event(self):
        return True


#######################################################################


class HermesEventProjectDeleted(HermesEvent):

    regexp = re.compile('\[obs del\] Project ([^/\s]*) deleted')
    raw_type = 'OBS_SRCSRV_DELETE_PROJECT'

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        if self.raw:
            return

        match = self.regexp.match(title)

        self.project = str(match.group(1))


    def is_project_event(self):
        return True


#######################################################################


class HermesEventPackageMeta(HermesEvent):

    regexp = re.compile('\[obs update\] Package ([^/\s]*) in ([^/\s]*) updated')
    raw_type = 'OBS_SRCSRV_UPDATE_PACKAGE'

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        if self.raw:
            return

        match = self.regexp.match(title)

        self.project = str(match.group(2))
        self.package = str(match.group(1))


    def is_package_event(self):
        return True


#######################################################################


class HermesEventPackageAdded(HermesEvent):

    regexp = re.compile('\[obs new\] New Package ([^/\s]*) ([^/\s]*)')
    # Workaround again buggy messages
    workaround_regexp = re.compile('\[obs new\] New Package\s*$')
    raw_type = 'OBS_SRCSRV_CREATE_PACKAGE'

    @classmethod
    def is_type_for_title(cls, title):
        if super(HermesEventPackageAdded, cls).is_type_for_title(title):
            return True
        else:
            match = cls.workaround_regexp.match(title)
            return match != None

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        if self.raw:
            return

        match = self.regexp.match(title)

        if match:
            # Hermes previously said "Package $PGK in $PRJ"
            if str(match.group(2)) == 'in':
                raise HermesException('Old format of hermes message detected: %s' % title)

            self.project = str(match.group(2))
            self.package = str(match.group(1))
        else:
            match = self.workaround_regexp.match(title)
            if match != None:
                self.project = ''
                self.package = ''
            else:
                raise HermesException('Event should not be in PackagedAdded: %s' % title)


    def is_package_event(self):
        return True


#######################################################################


class HermesEventPackageDeleted(HermesEvent):

    regexp = re.compile('\[obs del\] Package ([^/\s]*) from ([^/\s]*) deleted')
    raw_type = 'OBS_SRCSRV_DELETE_PACKAGE'

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        if self.raw:
            return

        match = self.regexp.match(title)

        self.project = str(match.group(2))
        self.package = str(match.group(1))


    def is_package_event(self):
        return True


#######################################################################


class HermesReader:

    types = [ HermesEventCommit, HermesEventProjectDeleted, HermesEventPackageMeta, HermesEventPackageAdded, HermesEventPackageDeleted ]


    def __init__(self, last_known_id, base_url, feeds, conf):
        """ Arguments:
            last_known_id -- id of the last known event, so the hermes reader
                             can know where to stop.
            base_url -- the base url for the hermes server.
            feeds -- a list of feed ids. They will be used to get a merged feed
                     from the hermes server.
            conf -- configuration object

        """
        self._events = []
        self.last_known_id = last_known_id

        self._previous_last_known_id = int(last_known_id)
        self._conf = conf

        if not base_url or not feeds:
            self._feed = None
            self._debug_print('No defined feed')
        else:
            resource = '/feeds/' + ','.join(feeds) + '.rdf'
            self._feed = urllib.parse.urljoin(base_url, resource)
            self._debug_print('Feed to be used: %s' % self._feed)

        self._last_parsed_id = -1


    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self._conf.debug:
            print('HermesReader: %s' % s)


    def _get_entry_id(self, entry):
        """ Gets the hermes id of the event.
        
            This is an integer that we can compare with other ids.

        """
        entry_id = entry['id']
        id = os.path.basename(entry_id)

        try:
            return int(id)
        except ValueError:
            raise HermesException('Cannot get event id from: %s' % entry_id)


    def _parse_entry(self, id, entry):
        """ Return an event object based on the entry. """
        title = entry['title']

        for type in self.types:
            if type.is_type_for_title(title):
                return type(id, title, entry['summary'])

        # work around some weird hermes bug
        if title in [ 'Notification  arrived!', 'Notification unknown type arrived!' ]:
            return None

        raise HermesException('Cannot get event type from message %d: "%s"' % (id, title))


    def _parse_feed(self, url):
        """ Parses the feed to get events that are somehow relevant.

            This function ignores entries older than the previous last known id.

            Return True if the feed was empty.

        """
        feed = feedparser.parse(url)

        if len(feed['entries']) == 0:
            return True

        for entry in feed['entries']:
            error_encoded = False

            id = self._get_entry_id(entry)
            if id <= self._previous_last_known_id:
                continue
            if id > self._last_parsed_id:
                self._last_parsed_id = id

            try:
                event = self._parse_entry(id, entry)
            except UnicodeEncodeError as e:
                error_encoded = True
                event = None
                print('Cannot convert hermes message %d to str: %s' % (id, e), file=sys.stderr)

            # Note that hermes can be buggy and give events without the proper
            # project/package. If it's '' and not None, then it means it has
            # been changed to something empty (and therefore it's a bug from
            # hermes).
            if (event and
                event.project != '' and
                not (event.is_package_event() and event.package == '')):
                # put the id in the tuple so we can sort the list later
                self._events.append((id, event))
            # in case of UnicodeEncodeError, we already output a message
            elif not error_encoded:
                print('Buggy hermes message %d (%s): "%s".' % (id, entry['updated'], entry['title']), file=sys.stderr)
                print('----------', file=sys.stderr)
                for line in entry['summary'].split('\n'):
                    print('> %s' % line, file=sys.stderr)
                print('----------', file=sys.stderr)

            if id > self.last_known_id:
                self.last_known_id = id

        return False


    def _append_data_to_url(self, url, data):
        """ Append data to the query arguments passed to url. """
        if url.find('?') != -1:
            return '%s&%s' % (url, data)
        else:
            return '%s?%s' % (url, data)


    def fetch_last_known_id(self):
        """ Read the first feed just to get a last known id. """
        self._debug_print('Fetching new last known id')

        # we don't ignore self._conf.skip_hermes if we don't have a last known
        # id, since it can only harm by creating a later check for all projects
        # on the build service, which is expensive
        if self._conf.skip_hermes and self.last_known_id != -1:
            return

        if not self._feed:
            return

        feed = feedparser.parse(self._feed)
        for entry in feed['entries']:
            id = self._get_entry_id(entry)
            if id > self.last_known_id:
                self.last_known_id = id


    def _read_feed(self, feed_url):
        """ Read events from hermes, and populates the events item. """
        self._last_parsed_id = -1
        page = 1
        if self._previous_last_known_id > 0:
            url = self._append_data_to_url(feed_url, 'last_id=%d' % self._previous_last_known_id)
        else:
            raise HermesException('Internal error: trying to parse feeds while there is no last known id')

        if self._conf.skip_hermes:
            return

        while True:
            if page > 100:
                raise HermesException('Parsing too many pages: last parsed id is %d, last known id is %d' % (self._last_parsed_id, self._previous_last_known_id))

            self._debug_print('Parsing %s' % url)

            old_last_parsed_id = self._last_parsed_id

            empty_feed = self._parse_feed(url)
            if empty_feed:
                break
            elif old_last_parsed_id >= self._last_parsed_id:
                # this should never happen, as if we don't have an empty feeed, it
                # means we progress
                raise HermesException('No progress when parsing pages: last parsed id is %d, last known id is %d' % (self._last_parsed_id, self._previous_last_known_id))

            page += 1
            url = self._append_data_to_url(feed_url, 'last_id=%d' % self._last_parsed_id)


    def read(self):
        """ Read events from hermes, and populates the events item. """
        # Make sure we don't append events to some old values
        self._events = []

        if self._feed:
            self._read_feed(self._feed)

        # Sort to make sure events are in the reverse chronological order
        self._events.sort(reverse = True)

        self._debug_print('Number of events: %d' % len(self._events))
        if len(self._events) == 0:
            return

        self._debug_print('Events (reverse sorted): %s' % [ id for (id, event) in self._events ])

        self._strip()

        self._debug_print('Number of events after strip: %d' % len(self._events))


    def _strip(self):
        """ Strips events that we can safely ignore.

            For example, we can ignore multiple commits, or commits that were
            done before a deletion.

        """
        meta_changed = []
        changed = []
        deleted = []

        new_events = []

        # Note: the event list has the most recent event first
        # FIXME: we should do a first pass in the reverse order to know which
        # packages were added, and then later removed, so we can also strip the
        # remove event below.

        for (id, event) in self._events:
            # Ignore event if the project was deleted after this event
            if (event.project, None) in deleted:
                continue
            # Ignore event if the package was deleted after this event
            if event.package and (event.project, event.package) in deleted:
                continue

            if isinstance(event, HermesEventCommit):
                # Ignore commit event if the package was re-committed
                # afterwards
                if (event.project, event.package) in changed:
                    continue
                changed.append((event.project, event.package))
                new_events.append((id, event))

            elif isinstance(event, HermesEventProjectDeleted):
                deleted.append((event.project, None))
                new_events.append((id, event))

            elif isinstance(event, HermesEventPackageMeta):
                # Ignore meta event if the meta of the package was changed
                # afterwards
                if (event.project, event.package) in meta_changed:
                    continue
                meta_changed.append((event.project, event.package))
                new_events.append((id, event))

            elif isinstance(event, HermesEventPackageAdded):
                # Ignore added event if the package was re-committed
                # afterwards and meta was changed
                if (event.project, event.package) in meta_changed and (event.project, event.package) in changed:
                    continue
                changed.append((event.project, event.package))
                meta_changed.append((event.project, event.package))
                new_events.append((id, event))

            elif isinstance(event, HermesEventPackageDeleted):
                # Ignore deleted event if the package was re-committed
                # afterwards (or meta was changed)
                if (event.project, event.package) in meta_changed:
                    continue
                if (event.project, event.package) in changed:
                    continue
                deleted.append((event.project, event.package))
                new_events.append((id, event))

        self._events = new_events


    def get_events(self, last_known_id = -1, reverse = False):
        """ Return the list of events that are more recent than last_known_id. """
        result = []

        for (id, event) in self._events:
            if id <= last_known_id:
                break
            result.append(event)

        if reverse:
            result.reverse()

        return result

#######################################################################


def main(args):
    class Conf:
        def __init__(self):
            self.debug = True
            self.skip_hermes = False

    feeds = [ '25545', '25547', '55386', '55387', '55388' ]
    last_known_id = 10011643

    reader = HermesReader(last_known_id, 'https://hermes.opensuse.org/', feeds, Conf())
    reader.read()

    print('Number of events: %d' % len(reader.get_events(2094133)))
    print('Last known event: %d' % reader.last_known_id)


if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
