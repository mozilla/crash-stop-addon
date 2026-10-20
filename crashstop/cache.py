# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from bmemcached import Client
from concurrent.futures import ThreadPoolExecutor
import hashlib
from itertools import chain
import os
import time
from . import config, signatures
from .logger import logger


# How long the placeholder holds the key while its owner computes the value.
LOCK_TIME = 30

# How long another request waits on that placeholder. It has to give up well
# before the router does: recomputing the value is wasteful, but cheaper than
# spending the whole budget queueing and timing out anyway.
MAX_WAIT = 15


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


def get_sumup(hg_urls, signatures, extra):
    key = '\n'.join(chain(signatures, hg_urls, get_extra_as_list(extra)))
    key = get_hash(key)
    bcache = get_client()
    for _ in [0, 1]:
        if bcache.add(key, 0, time=LOCK_TIME):
            try:
                value = get_value(hg_urls, signatures, extra)
            except Exception:
                bcache.delete(key)
                raise
            try:
                bcache.set(
                    key, value, time=config.get_cache_time(), compress_level=9
                )
            except Exception as e:
                # Most likely the value is over the server's 1MB item limit.
                # Serving it uncached is fine, but the placeholder has to go:
                # anyone waiting on it is waiting for a value that will never
                # show up.
                logger.warning('Cannot cache the value: {}'.format(e))
                bcache.delete(key)
            return value
        else:
            # The key may already exist, or the cache may be unavailable.
            deadline = time.monotonic() + MAX_WAIT
            while time.monotonic() < deadline:
                value = bcache.get(key)
                if value is None:
                    # key has expired
                    break
                if value != 0:
                    # we've a correct value
                    return value
                time.sleep(0.1)
            else:
                # whoever holds the key is taking longer than we can afford
                logger.warning('Gave up waiting for the cached value.')
                break

    # if we're here then either the value was twice None (so the memcached
    # server is probably down) or we stopped waiting for the key holder.
    return get_value(hg_urls, signatures, extra)


def clear():
    get_client().flush_all()
