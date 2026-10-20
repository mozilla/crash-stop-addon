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


KEY = cache.get_key([], ['sgn'], {})
VALUE = ({'Firefox': {}}, {}, False)
OTHER = ({'Fenix': {}}, {}, False)


class FakeMemcached:
    """In-memory cache stub with failure injection and no expiry."""

    def __init__(self):
        self.data = {}
        self.reachable = True
        self.set_result = True
        # Simulate a successful add with a lost acknowledgement.
        self.add_result_lost = False
        # Block selected methods until their events are set.
        self.stuck = {}

    def cas(self, key):
        # Approximate CAS using the stored object's identity.
        return id(self.data[key])

    def add(self, key, value, time=0):
        if 'add' in self.stuck:
            self.stuck['add'].wait()
        if not self.reachable or key in self.data:
            return False
        self.data[key] = value
        return not self.add_result_lost

    def get(self, key):
        return self.data.get(key) if self.reachable else None

    def gets(self, key):
        if not self.reachable or key not in self.data:
            return None, None
        return self.data[key], self.cas(key)

    def set(self, key, value, time=0, compress_level=-1):
        if 'set' in self.stuck:
            self.stuck['set'].wait()
        if isinstance(self.set_result, Exception):
            raise self.set_result
        if not self.reachable or not self.set_result:
            return False
        self.data[key] = value
        return True

    def delete(self, key, cas=0):
        if not self.reachable or key not in self.data:
            return False
        if cas and cas != self.cas(key):
            return False
        del self.data[key]
        return True


@pytest.fixture
def memcached(monkeypatch):
    fake = FakeMemcached()
    monkeypatch.setattr(cache, '_CLIENT', cache.OneThreadClient(fake))
    yield fake
    for event in fake.stuck.values():
        event.set()


def contents(memcached):
    """Wait for queued cache work before inspecting stored entries."""
    cache.get_client()._executor.submit(lambda: None).result()
    return memcached.data


@pytest.fixture
def computed(monkeypatch):
    """Record the signatures passed to get_value."""
    calls = []

    def get_value(hg_urls, signatures, extra):
        calls.append(signatures)
        return VALUE

    monkeypatch.setattr(cache, 'get_value', get_value)
    yield calls


def test_cached_value_is_reused(memcached, computed):
    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert computed == [['sgn']]
    assert contents(memcached) == {KEY: VALUE}


def test_waiter_gets_the_owners_value(memcached, computed):
    memcached.data[KEY] = 'owner'
    threading.Timer(0.3, memcached.data.__setitem__, (KEY, OTHER)).start()

    assert cache.get_sumup([], ['sgn'], {}) == OTHER
    assert computed == []


def test_waiter_takes_over_when_the_owner_fails(memcached, computed):
    # Simulate the owner removing its token after a failure.
    memcached.data[KEY] = 'owner'
    threading.Timer(0.3, memcached.data.pop, (KEY,)).start()

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert computed == [['sgn']]
    assert contents(memcached) == {KEY: VALUE}


def test_waiter_gives_up_and_stores_the_value(memcached, computed, monkeypatch, caplog):
    monkeypatch.setattr(cache, 'MAX_WAIT', 0.3)
    memcached.data[KEY] = 'owner'

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert computed == [['sgn']]
    assert contents(memcached) == {KEY: VALUE}
    assert 'Gave up waiting for the cached value.' in caplog.text


@pytest.mark.parametrize(
    'set_result, reason',
    [
        (False, 'memcached is unreachable'),
        (Exception('Code: 3 Message: Too large.'), 'Code: 3 Message: Too large.'),
    ],
)
def test_failed_set_removes_the_placeholder(memcached, computed, caplog, set_result, reason):
    memcached.set_result = set_result

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert contents(memcached) == {}
    assert 'Cannot cache the value: ' + reason in caplog.text


def test_waiter_failing_to_store_keeps_the_owners_value(memcached, monkeypatch):
    monkeypatch.setattr(cache, 'MAX_WAIT', 0.3)
    memcached.data[KEY] = 'owner'
    memcached.set_result = False

    def get_value(hg_urls, signatures, extra):
        # Simulate the owner publishing while the waiter computes.
        memcached.data[KEY] = OTHER
        return VALUE

    monkeypatch.setattr(cache, 'get_value', get_value)

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert contents(memcached) == {KEY: OTHER}


def test_failed_owner_removes_its_placeholder(memcached, monkeypatch):
    def get_value(hg_urls, signatures, extra):
        raise RuntimeError('Socorro is down')

    monkeypatch.setattr(cache, 'get_value', get_value)

    with pytest.raises(RuntimeError):
        cache.get_sumup([], ['sgn'], {})
    assert contents(memcached) == {}


def test_failed_owner_keeps_someone_elses_value(memcached, monkeypatch):
    def get_value(hg_urls, signatures, extra):
        # Simulate a replacement entry after our token expires.
        memcached.data[KEY] = OTHER
        raise RuntimeError('Socorro is down')

    monkeypatch.setattr(cache, 'get_value', get_value)

    with pytest.raises(RuntimeError):
        cache.get_sumup([], ['sgn'], {})
    assert contents(memcached) == {KEY: OTHER}


def test_add_whose_answer_was_lost(memcached, computed):
    memcached.add_result_lost = True

    start = time.monotonic()
    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    # Do not wait on our own token.
    assert time.monotonic() - start < 1
    assert computed == [['sgn']]
    assert contents(memcached) == {KEY: VALUE}


def test_timed_out_add_that_goes_through_is_undone(memcached, computed, monkeypatch):
    monkeypatch.setattr(cache, 'CALL_TIMEOUT', 0.2)
    memcached.stuck['add'] = threading.Event()

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert computed == [['sgn']]
    # Let the timed-out add finish; cleanup must remove its token.
    memcached.stuck['add'].set()
    assert contents(memcached) == {}


def test_timed_out_set_that_goes_through_is_kept(memcached, computed, monkeypatch):
    monkeypatch.setattr(cache, 'CALL_TIMEOUT', 0.2)
    memcached.stuck['set'] = threading.Event()

    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    memcached.stuck['set'].set()
    # Cleanup must preserve the late successful write.
    assert contents(memcached) == {KEY: VALUE}


def test_entries_from_before_the_key_version_are_ignored(memcached, computed):
    # An entry written by a worker without versioned keys.
    old_key = cache.get_hash('sgn')
    memcached.data[old_key] = 0

    start = time.monotonic()
    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert time.monotonic() - start < 1
    assert contents(memcached) == {old_key: 0, KEY: VALUE}


@pytest.mark.parametrize('when', ['before', 'while we compute'])
def test_worker_exiting(memcached, monkeypatch, when):
    def shut_down():
        # Simulate executor shutdown during worker exit.
        cache.get_client()._executor.shutdown()

    def get_value(hg_urls, signatures, extra):
        if when == 'while we compute':
            shut_down()
        return VALUE

    monkeypatch.setattr(cache, 'get_value', get_value)
    if when == 'before':
        shut_down()

    assert cache.get_sumup([], ['sgn'], {}) == VALUE


def test_unreachable_memcached(memcached, computed, caplog):
    memcached.reachable = False

    start = time.monotonic()
    assert cache.get_sumup([], ['sgn'], {}) == VALUE
    assert time.monotonic() - start < 1
    assert computed == [['sgn']]
    assert 'Memcached is unreachable, computing without the cache.' in caplog.text


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
