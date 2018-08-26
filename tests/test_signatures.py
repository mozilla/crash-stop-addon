# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import signatures
from unittest.mock import patch
from . import common
from .hg import MyRevision
from .supersearch import MySuperSearch


def get_all_versions(products, channels):
    versions = common.get_all_versions()

    res = {}
    for prod, i in versions.items():
        if prod in products:
            res[prod] = res_prod = {}
            for chan, j in i.items():
                if chan in channels:
                    res_prod[chan] = j
    return res


def test_get_for_urls_sgns_empty():
    data = signatures.get_for_urls_sgns([], [])
    assert data == {'data': {}, 'versions': {}}


@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
def test_get_for_urls_sgns_no_patch_fx_fa(get_result):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]
    data = signatures.get_for_urls_sgns([], sgns)

    assert data == get_result('tests/data/crashstop/signatures_nop_fx_fa.json', data)


@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
def test_get_for_urls_sgns_no_patch_fa(get_result):
    sgns = MySuperSearch.get_signatures()
    sgns = [s for s in sgns['FennecAndroid'] if s.endswith('.java)')]
    sgns = sgns if len(sgns) < 10 else sgns[:10]
    data = signatures.get_for_urls_sgns([], sgns)

    assert data == get_result('tests/data/crashstop/signatures_nop_fa.json', data)


@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_get_for_urls_sgns_patch_fx_fa(get_result):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]

    # random choices for the revs
    revs = [
        'nightly|5c44264ed1fe',
        'nightly|9d0deb476c99',
        'beta|4a5ae6a7911d',
        'beta|55fc535ff4ce',
        'release|0be81adef007',
    ]

    data = signatures.get_for_urls_sgns(revs, sgns)

    assert data == get_result('tests/data/crashstop/signatures_p_fx_fa.json', data)


@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_prepare_bug_for_html(get_result):
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5] + sgns['FennecAndroid'][:5]

    # random choices for the revs
    revs = [
        'nightly|5c44264ed1fe',
        'nightly|9d0deb476c99',
        'beta|4a5ae6a7911d',
        'beta|55fc535ff4ce',
        'release|0be81adef007',
    ]

    data = signatures.get_for_urls_sgns(revs, sgns)
    data, affected, _ = signatures.prepare_bug_for_html(data)

    data = {'data': data, 'affected': affected}

    assert data == get_result('tests/data/crashstop/signatures_prepare.json', data)


def test_prepare_bug_for_html_empty():
    data, affected, extra = signatures.prepare_bug_for_html({})

    assert data == {}
    assert affected == {}
    assert extra is False
