# vim: sw=4 et

# Copyright (C) 2006 Novell Inc.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).

# This file contains copy of some trivial functions from osc that we want to
# use. It is copied here to avoid importing large python modules.

from urllib.parse import urlencode
from urllib.parse import urlsplit, urlunsplit

def makeurl(baseurl, l, query=[]):
    """Given a list of path compoments, construct a complete URL.

    Optional parameters for a query string can be given as a list, as a
    dictionary, or as an already assembled string.
    In case of a dictionary, the parameters will be urlencoded by this
    function. In case of a list not -- this is to be backwards compatible.
    """

    #print 'makeurl:', baseurl, l, query

    if type(query) == type(list()):
        query = '&'.join(query)
    elif type(query) == type(dict()):
        query = urlencode(query)

    scheme, netloc = urlsplit(baseurl)[0:2]
    return urlunsplit((scheme, netloc, '/'.join(l), query, ''))               
