# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from bmemcached import Client
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


_CLIENT = Client(*_get_credentials())


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
            # since add returned False, it means that the key is already here
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
