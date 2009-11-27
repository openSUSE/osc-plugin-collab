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
# Authors: Vincent Untz <vuntz@novell.com>
#

import os
import sys

import re

import feedparser

#######################################################################


class HermesException(Exception):
    pass


#######################################################################


class HermesEvent:

    regexp = None

    def __init__(self, id, title, summary):
        self.id = id
        self.project = None
        self.package = None


    @classmethod
    def is_type_for_title(cls, title):
        """ Determines if a feed entry belongs to the event class.

            The match is based on the title of the feed entry, that is passed
            through a regular expression.

        """
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

    regexp = re.compile('OBS ([^/\s]+)/([^/\s]+) r\d+ commited')

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
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

    regexp = re.compile('\[obs del\] Project ([^/\s]+) deleted')

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        match = self.regexp.match(title)

        self.project = str(match.group(1))


    def is_project_event(self):
        return True


#######################################################################


class HermesEventPackageMeta(HermesEvent):

    regexp = re.compile('\[obs update\] Package ([^/\s]+) in ([^/\s]+) updated')

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        match = self.regexp.match(title)

        self.project = str(match.group(2))
        self.package = str(match.group(1))


    def is_package_event(self):
        return True


#######################################################################


class HermesEventPackageAdded(HermesEvent):

    regexp = re.compile('\[obs new\] New Package ([^/\s]+) in ([^/\s]+)')

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        match = self.regexp.match(title)

        self.project = str(match.group(2))
        self.package = str(match.group(1))


    def is_package_event(self):
        return True


#######################################################################


class HermesEventPackageDeleted(HermesEvent):

    regexp = re.compile('\[obs del\] Package ([^/\s]+) from ([^/\s]+) deleted')

    def __init__(self, id, title, summary):
        HermesEvent.__init__(self, id, title, summary)
        match = self.regexp.match(title)

        self.project = str(match.group(2))
        self.package = str(match.group(1))


    def is_package_event(self):
        return True


#######################################################################


class HermesReader:

    types = [ HermesEventCommit, HermesEventProjectDeleted, HermesEventPackageMeta, HermesEventPackageAdded, HermesEventPackageDeleted ]


    def __init__(self, last_known_id, base_urls, conf):
        """ Arguments:
            last_known_id -- id of the last known event, so the hermes reader
                             can know where to stop.
            base_urls -- a list of base urls, one for each feed. "?page=X" can
                         be appended to view additional events.
            conf -- configuration object

        """
        self.events = []
        self.last_known_id = last_known_id

        self._previous_last_known_id = last_known_id
        self._base_urls = base_urls
        self._conf = conf

        self._last_parsed_id = -1


    def _debug_print(self, s):
        """ Print s if debug is enabled. """
        if self._conf.debug:
            print 'HermesReader: %s' % s


    def _get_entry_id(self, entry):
        """ Gets the hermes id of the event.
        
            This is an integer that we can compare with other ids.

        """
        entry_id = entry['id']
        id = os.path.basename(entry_id)

        try:
            self._last_parsed_id = int(id)
        except ValueError:
            raise HermesException('Cannot get event id from: %s' % entry_id)

        return self._last_parsed_id


    def _parse_entry(self, id, entry):
        """ Return an event object based on the entry. """
        title = entry['title']

        for type in self.types:
            if type.is_type_for_title(title):
                return type(id, title, entry['summary'])

        raise HermesException('Cannot get event type from: %s' % title)


    def _parse_feed(self, url):
        """ Parses the feed to get events that are somehow relevant.

            This function stops when we reach the last known id that was
            previously seen, or when all entries of the feed were parsed.

            Return True if the last known id was reached, False otherwise.

        """
        feed = feedparser.parse(url)

        for entry in feed['entries']:
            id = self._get_entry_id(entry)
            if id <= self._previous_last_known_id:
                return True

            event = self._parse_entry(id, entry)
            if event:
                # put the id in the tuple so we can sort the list later
                self.events.append((id, event))

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

        if len(self._base_urls) == 0:
            return

        feed = feedparser.parse(self._base_urls[0])
        if len(feed['entries']) == 0:
            return

        id = self._get_entry_id(feed['entries'][0])
        if id > self.last_known_id:
            self.last_known_id = id


    def _read_feed(self, base_url):
        """ Read events from hermes, and populates the events item. """
        page = 1
        url = base_url

        if self._conf.skip_hermes:
            return

        while True:
            if page > 100:
                raise HermesException('Parsing too many pages: last parsed id is %d, last known id is %d' % (self._last_parsed_id, self._previous_last_known_id))

            self._debug_print('Parsing %s' % url)

            stop = self._parse_feed(url)
            if stop:
                break

            page += 1
            url = self._append_data_to_url(base_url, 'page=%d' % page)


    def read(self):
        """ Read events from hermes, and populates the events item. """
        # Make sure we don't append events to some old values
        self.events = []

        for base_url in self._base_urls:
            self._read_feed(base_url)

        # Sort to make sure events are in the reverse chronological order
        self.events.sort(reverse = True)

        self._debug_print('Number of events: %d' % len(self.events))
        if len(self.events) == 0:
            return

        self._debug_print('Events (reverse sorted): %s' % [ id for (id, event) in self.events ])

        # Remove the id of events for easier consumption
        self.events = [ event for (id, event) in self.events ]

        self._strip()

        self._debug_print('Number of events after strip: %d' % len(self.events))


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

        for event in self.events:
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
                new_events.append(event)

            elif isinstance(event, HermesEventProjectDeleted):
                deleted.append((event.project, None))
                new_events.append(event)

            elif isinstance(event, HermesEventPackageMeta):
                # Ignore meta event if the meta of the package was changed
                # afterwards
                if (event.project, event.package) in meta_changed:
                    continue
                meta_changed.append((event.project, event.package))
                new_events.append(event)

            elif isinstance(event, HermesEventPackageAdded):
                # Ignore added event if the package was re-committed
                # afterwards and meta was changed
                if (event.project, event.package) in meta_changed and (event.project, event.package) in changed:
                    continue
                changed.append((event.project, event.package))
                meta_changed.append((event.project, event.package))
                new_events.append(event)

            elif isinstance(event, HermesEventPackageDeleted):
                # Ignore deleted event if the package was re-committed
                # afterwards (or meta was changed)
                if (event.project, event.package) in meta_changed:
                    continue
                if (event.project, event.package) in changed:
                    continue
                deleted.append((event.project, event.package))
                new_events.append(event)

        self.events = new_events


#######################################################################


def main(args):
    #url = '25547.rdf'
    #last_known_id = 2049567
    url = 'https://hermes.opensuse.org/feeds/25547.rdf'
    last_known_id = 2049168

    reader = HermesReader(last_known_id, [ url ], debug = True)
    reader.read()

    print 'Number of events: %d' % len(reader.events)
    print 'Last known event: %d' % reader.last_known_id


if __name__ == '__main__':
    try:
      main(sys.argv)
    except KeyboardInterrupt:
      pass
