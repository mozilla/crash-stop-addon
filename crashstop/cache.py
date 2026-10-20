# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from bmemcached import Client
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import chain
import os
import time
import uuid
from . import config, signatures
from .logger import logger


# Placeholder TTL; cleanup must preserve any replacement entry.
LOCK_TIME = 30

# Polling budget before computing independently.
MAX_WAIT = 25

# Isolate token placeholders from older workers that expect 0.
KEY_VERSION = 2


def _get_credentials():
    """Get the servers/username/password for the cache.

       MEMCACHIER_* is the Heroku addon, MEMCACHEDCLOUD_* is what
       docker-compose sets (and the addon we used to be on).
    """
    for prefix in ['MEMCACHIER', 'MEMCACHEDCLOUD']:
        servers = os.environ.get(prefix + '_SERVERS')
        if servers:
            return (
                servers.split(','),
                os.environ.get(prefix + '_USERNAME', ''),
                os.environ.get(prefix + '_PASSWORD', ''),
            )

    return (
        config.get_memcached('servers').split(','),
        config.get_memcached('username'),
        config.get_memcached('password'),
    )


# Timeout for socket operations, separate from the request wait limit.
SOCKET_TIMEOUT = 0.5

# Maximum wait per cache call, including queueing.
CALL_TIMEOUT = 1

# Skip cache calls for this many seconds after a call times out.
SKIP_TIME = 10


class OneThreadClient:
    """Reuse bmemcached's thread-local connections by calling from one thread.

       Limit request waits, including queueing. After a timeout, skip cache
       calls for SKIP_TIME and return cache-unavailable results.
       Cleanup bypasses the skip period and runs after earlier calls.
    """

    def __init__(self, client):
        self._client = client
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='memcached'
        )
        self._skip_until = 0

    def _call(self, unreachable, name, *args, **kwargs):
        if time.monotonic() < self._skip_until:
            return unreachable

        method = getattr(self._client, name)
        try:
            future = self._executor.submit(method, *args, **kwargs)
        except RuntimeError:
            # Treat executor shutdown during worker exit as cache unavailability.
            return unreachable

        try:
            return future.result(timeout=CALL_TIMEOUT)
        except TimeoutError:
            # Cancel queued work; running calls may still complete.
            future.cancel()
            self._skip_until = time.monotonic() + SKIP_TIME
            logger.warning(
                'Memcached is not answering, skipping it for {}s.'.format(SKIP_TIME)
            )
            return unreachable

    def add(self, *args, **kwargs):
        return self._call(False, 'add', *args, **kwargs)

    def get(self, *args, **kwargs):
        return self._call(None, 'get', *args, **kwargs)

    def set(self, *args, **kwargs):
        return self._call(False, 'set', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._call(False, 'delete', *args, **kwargs)

    def flush_all(self, *args, **kwargs):
        return self._call(False, 'flush_all', *args, **kwargs)

    def _delete_if(self, key, value):
        try:
            found, cas = self._client.gets(key)
            if found == value:
                # Reject the delete if the entry changed after gets().
                self._client.delete(key, cas)
        except Exception as e:
            logger.warning('Cannot delete the key: {}'.format(e))

    def delete_if_later(self, key, value):
        """Queue a conditional delete after earlier calls, bypassing the skip period."""
        try:
            self._executor.submit(self._delete_if, key, value)
        except RuntimeError:
            # During shutdown, leave the placeholder to expire.
            pass


_CLIENT = OneThreadClient(
    Client(*_get_credentials(), socket_timeout=SOCKET_TIMEOUT)
)


def get_client():
    return _CLIENT


def get_value(hgurls, sgns, extra):
    data = signatures.get_for_urls_sgns(hgurls, sgns, extra=extra)
    data, affected, has_extra = signatures.prepare_bug_for_html(data, extra)
    return (data, affected, has_extra)


def get_hash(key):
    key = key.encode('utf-8')
    md5 = hashlib.md5(key).hexdigest()
    sha1 = hashlib.sha1(key).hexdigest()
    return md5 + sha1 + str(len(key))


def get_extra_as_list(extra):
    res = []
    for k, v in sorted(extra.items()):
        res.append(k)
        if isinstance(v, list):
            res += v
        else:
            res.append(v)

    return res


def get_key(hg_urls, signatures, extra):
    key = '\n'.join(chain(signatures, hg_urls, get_extra_as_list(extra)))
    return 'v{}:{}'.format(KEY_VERSION, get_hash(key))


def release(key, token):
    """Queue removal of our token, including a late successful add."""
    get_client().delete_if_later(key, token)


def store(key, token, value):
    """Cache the result; release our token if the write fails."""
    try:
        if get_client().set(
            key, value, time=config.get_cache_time(), compress_level=9
        ):
            return
        reason = 'memcached is unreachable'
    except Exception as e:
        reason = e

    logger.warning('Cannot cache the value: {}'.format(reason))
    # Stop waiters polling our token after a failed write.
    release(key, token)


def compute(key, token, hg_urls, signatures, extra):
    try:
        value = get_value(hg_urls, signatures, extra)
    except Exception:
        release(key, token)
        raise
    store(key, token, value)
    return value


def get_sumup(hg_urls, signatures, extra):
    key = get_key(hg_urls, signatures, extra)
    bcache = get_client()
    token = uuid.uuid4().hex
    deadline = time.monotonic() + MAX_WAIT
    for _ in [0, 1]:
        if bcache.add(key, token, time=LOCK_TIME):
            return compute(key, token, hg_urls, signatures, extra)
        else:
            # The key may already exist, or the cache may be unavailable.
            while time.monotonic() < deadline:
                value = bcache.get(key)
                if value is None:
                    break
                if value == token:
                    # Recover an add whose acknowledgement was lost.
                    return compute(key, token, hg_urls, signatures, extra)
                if not isinstance(value, str):
                    # Cached results are tuples; placeholders are strings.
                    return value
                time.sleep(0.1)
            else:
                logger.warning('Gave up waiting for the cached value.')
                return compute(key, token, hg_urls, signatures, extra)

    # A timed-out add may still succeed; queue cleanup before computing uncached.
    logger.warning('Memcached is unreachable, computing without the cache.')
    release(key, token)
    return get_value(hg_urls, signatures, extra)


def clear():
    get_client().flush_all()
