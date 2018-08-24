# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import cache
import time
from unittest.mock import patch
from .hg import MyRevision
from .supersearch import MySuperSearch
from .test_signatures import get_all_versions


@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_cache():
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

    data1 = cache.get_sumup(revs, sgns, {})
    time.sleep(0.5)
    data2 = cache.get_sumup(revs, sgns, {})

    assert data1 == data2

    cache.clear()

    with patch('crashstop.config.get_cache_time', lambda: 1):
        data1 = cache.get_sumup(revs, sgns, {})
    time.sleep(1.1)
    data2 = cache.get_sumup(revs, sgns, {})

    assert data1 == data2
