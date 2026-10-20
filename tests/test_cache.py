# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from concurrent.futures import ThreadPoolExecutor
from crashstop import cache
import pytest
import threading
import time
from unittest.mock import patch
from .hg import MyRevision
from .supersearch import MySuperSearch
from .test_signatures import get_all_versions


def test_one_thread_client():
    class Client:
        threads = set()

        def get(self, key):
            self.threads.add(threading.get_ident())
            return 2 * key

        def delete(self, key):
            raise ValueError(key)

    client = cache.OneThreadClient(Client())
    callers = set()
    # Start all four calls from distinct request threads.
    barrier = threading.Barrier(4)

    def call(key):
        barrier.wait()
        callers.add(threading.get_ident())
        return client.get(key)

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(call, range(4))) == [0, 2, 4, 6]

    assert len(callers) == 4
    assert len(Client.threads) == 1
    assert not Client.threads & callers
    with pytest.raises(ValueError):
        client.delete(1)


class StuckClient:
    """Block get() until released."""

    def __init__(self):
        self.calls = []
        self.released = threading.Event()

    def get(self, key):
        self.calls.append(('get', key))
        self.released.wait()
        return 'value'

    def add(self, key, value, time=0):
        self.calls.append(('add', key))
        return True


@pytest.fixture
def stuck(monkeypatch):
    monkeypatch.setattr(cache, 'CALL_TIMEOUT', 0.2)
    monkeypatch.setattr(cache, 'SKIP_TIME', 0.3)
    client = StuckClient()
    yield client
    client.released.set()


def test_stuck_call_is_taken_as_unreachable(stuck):
    client = cache.OneThreadClient(stuck)

    start = time.monotonic()
    assert client.get('a') is None
    # Calls during the skip period must not reach the client.
    assert client.add('b', 0, time=1) is False
    assert time.monotonic() - start < 0.4
    assert stuck.calls == [('get', 'a')]

    stuck.released.set()
    time.sleep(0.5)
    # Calls resume after the skip period.
    assert client.add('c', 0, time=1) is True
    assert stuck.calls == [('get', 'a'), ('add', 'c')]


def test_calls_queued_behind_a_stuck_one_are_dropped(stuck):
    client = cache.OneThreadClient(stuck)
    first = threading.Thread(target=client.get, args=('a',))
    first.start()
    while not stuck.calls:
        time.sleep(0.01)

    # The queued add must be cancelled when its wait expires.
    assert client.add('b', 0, time=1) is False
    stuck.released.set()
    first.join()
    time.sleep(0.1)
    assert stuck.calls == [('get', 'a')]


def test_calls_once_the_executor_is_shut_down():
    class Client:
        def get(self, key):
            return 'value'

    client = cache.OneThreadClient(Client())
    # Simulate executor shutdown during worker exit.
    client._executor.shutdown()
    assert client.get('a') is None


# Fixture misses query live APIs; this test also requires memcached.
@pytest.mark.integration
@patch('crashstop.signatures.get_all_versions', get_all_versions)
@patch('libmozdata.socorro.SuperSearch', MySuperSearch)
@patch('libmozdata.hgmozilla.Revision', MyRevision)
def test_cache():
    sgns = MySuperSearch.get_signatures()
    sgns = sgns['Firefox'][:5]

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
