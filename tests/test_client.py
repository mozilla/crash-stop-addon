# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import escape
from jinja2.utils import unicode_urlencode as urlencode
from unittest.mock import patch
from .hg import MyRevision
from .supersearch import MySuperSearch


def test_root(client):
    res = client.get('/')

    assert b'<title>Crash-Stop Help</title>' in res.data


def test_wtf(client):
    assert client.get('/wtf').status_code == 404


def test_css(client):
    res = client.get('/stop.css')
    data = res.data.decode('utf-8')
    with open('static/stop.css', 'r') as In:
        css = In.read()

    assert data == css


@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_sumup(client):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]
    query_sgns = '&'.join(['s=' + urlencode(sgn) for sgn in sgns])

    # random choices for the revs
    revs = [
        'nightly|5c44264ed1fe',
        'nightly|9d0deb476c99',
        'beta|4a5ae6a7911d',
        'beta|55fc535ff4ce',
        'release|0be81adef007',
    ]

    query_revs = '&'.join(['h=' + urlencode(rev) for rev in revs])
    url = 'sumup.html?' + query_sgns + '&' + query_revs

    res = client.get(url)

    assert b'<title>Crash data</title>' in res.data

    for sgn in sgns:
        sgn = escape(sgn)
        sgn = bytes(sgn, 'utf-8')
        assert sgn in res.data


@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_sumup_extra(client):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]
    query_sgns = '&'.join(['s=' + urlencode(sgn) for sgn in sgns])

    # random choices for the revs
    revs = [
        'nightly|5c44264ed1fe',
        'nightly|9d0deb476c99',
        'beta|4a5ae6a7911d',
        'beta|55fc535ff4ce',
        'release|0be81adef007',
    ]

    query_revs = '&'.join(['h=' + urlencode(rev) for rev in revs])
    url = 'sumup.html?' + query_sgns + '&' + query_revs
    url += '&' + urlencode('uptime>=0')

    res = client.get(url)

    assert b'<title>Crash data</title>' in res.data

    for sgn in sgns:
        sgn = escape(sgn)
        sgn = bytes(sgn, 'utf-8')
        assert sgn in res.data
