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


__CLIENT = Client(
    os.environ.get('MEMCACHEDCLOUD_SERVERS', config.get_memcached('servers')).split(
        ','
    ),
    os.environ.get('MEMCACHEDCLOUD_USERNAME', config.get_memcached('username')),
    os.environ.get('MEMCACHEDCLOUD_PASSWORD', config.get_memcached('password')),
)


def get_client():
    return __CLIENT


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
            for i in v:
                res.append(i)
        else:
            res.append(v)

    return res


def get_sumup(hg_urls, signatures, extra):
    key = '\n'.join(chain(signatures, hg_urls, get_extra_as_list(extra)))
    key = get_hash(key)
    bcache = get_client()
    for _ in [0, 1]:
        if bcache.add(key, 0, time=30):
            try:
                value = get_value(hg_urls, signatures, extra)
            except Exception:
                bcache.delete(key)
                raise
            bcache.set(key, value, time=config.get_cache_time(), compress_level=9)
            return value
        else:
            # since add returned False, it means that the key is already here
            while True:
                value = bcache.get(key)
                if value is None:
                    # key has expired
                    break
                if value != 0:
                    # we've a correct value
                    return value
                time.sleep(0.1)

    # if we're here then it means that value is two times None...
    # so probably the memcached server is down
    logger.warning('Issue with memcached...')

    return get_value(hg_urls, signatures, extra)


def clear():
    get_client().flush_all()
