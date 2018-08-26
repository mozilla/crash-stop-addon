# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import datacollector as dc
from crashstop import config, utils, signatures
import json
from unittest.mock import patch
from .common import get_all_versions
from .hg import MyRevision
from .supersearch import MySuperSearch


def test_get_useful_bids():
    buildhub_bids = [
        (utils.get_build_date('19750316010203'),),
        (utils.get_build_date('19760316010203'),),
        (utils.get_build_date('19770316010203'),),
        (utils.get_build_date('19780316010203'),),
        (utils.get_build_date('19790316010203'),),
        (utils.get_build_date('19800316010203'),),
    ]
    socorro_bids = {buildhub_bids[0][0], buildhub_bids[2][0], buildhub_bids[4][0]}

    expected = [buildhub_bids[0], buildhub_bids[2], buildhub_bids[4], buildhub_bids[5]]

    assert dc.get_useful_bids(buildhub_bids, socorro_bids) == expected


@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
def test_filter_nightly_buildids(get_result):
    with open('tests/data/buildhub/extract.json', 'r') as In:
        fa_fx_bids = json.load(In)['data']
    dc.filter_nightly_buildids(fa_fx_bids)

    assert fa_fx_bids == get_result('tests/data/crashstop/fa_fx_bids.json', fa_fx_bids)


def test_get_data_for_stats():
    N = 12
    L = [0] * N
    x = 'x' * N
    data = {'foo::bar': (x,)}

    for _ in range(2):
        r, i, s, n = dc.get_data_for_stats(data, 'foo::bar')

        assert r == L
        assert i == L
        assert s == L
        assert n == x


def test_get_unicity_stuff(get_result):
    versions = get_all_versions()
    min_buildid, allbids, unique, leftovers = dc.get_unicity_stuff(versions)

    # need to replace all datetime by string !!!
    min_buildid = utils.get_buildid(min_buildid)
    for prod, i in allbids.items():
        for chan, j in i.items():
            allbids[prod][chan] = {utils.get_buildid(k): v for k, v in j.items()}
    for prod, i in unique.items():
        unique[prod] = {utils.get_buildid(k): v for k, v in i.items()}
    for x in leftovers:
        x[0] = utils.get_buildid(x[0])

    res = {
        'min_buildid': min_buildid,
        'allbids': allbids,
        'unique': unique,
        'leftovers': leftovers,
    }

    assert res == get_result('tests/data/crashstop/unicity.json', res)


@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
def test_get_sgns_data(get_result):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]
    products = config.get_products()
    channels = config.get_channels()
    versions = get_all_versions()
    towait = []
    extra = {}
    platforms = signatures.init_platforms(sgns, channels, products)
    data = dc.get_sgns_data(
        channels, versions, platforms, sgns, extra, products, towait
    )

    for w in towait:
        w.wait()

    for prod, i in data.items():
        for chan, j in i.items():
            for sgn, numbers in j.items():
                if isinstance(numbers, list):
                    # remove the index dictionary
                    j[sgn] = numbers[:-1]
                elif isinstance(numbers, tuple):
                    j[sgn] = []

    assert data == get_result('tests/data/crashstop/sgns_stats.json', data)


@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_pushdates(get_result):
    revs = [
        'nightly|5c44264ed1fe',
        'nightly|9d0deb476c99',
        'beta|4a5ae6a7911d',
        'beta|55fc535ff4ce',
        'release|0be81adef007',
        'esr60|5c3ef4992a63',
        'esr60|bcb4837d51e8',
    ]
    revs = utils.get_channel_revision(revs)
    res, data = dc.get_pushdates(revs)

    for r in res:
        r.wait()

    for chan, dates in data.items():
        data[chan] = [str(date) for date in dates]

    assert data == get_result('tests/data/crashstop/pushdates.json', data)
