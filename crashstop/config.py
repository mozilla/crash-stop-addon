# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json


__THRESHOLDS = None
__GLOBAL = None
__LOCAL = None


def _get_thresholds():
    global __THRESHOLDS
    if not __THRESHOLDS:
        with open('./config/thresholds.json', 'r') as In:
            __THRESHOLDS = json.load(In)
    return __THRESHOLDS


def _get_global():
    global __GLOBAL
    if not __GLOBAL:
        with open('./config/global.json', 'r') as In:
            __GLOBAL = json.load(In)
    return __GLOBAL


def _get_local():
    global __LOCAL
    if not __LOCAL:
        try:
            with open('./config/local.json', 'r') as In:
                __LOCAL = json.load(In)
        except Exception:
            __LOCAL = {}
    return __LOCAL


def get_min_total(prod, chan):
    return _get_thresholds()[prod][chan]['min_total_crashes']


def get_min(prod, chan):
    return _get_thresholds()[prod][chan]['min_crashes']


def get_versions(prod, chan):
    return _get_thresholds()[prod][chan]['versions']


def get_max_versions():
    return max(v2['versions'] for v1 in _get_thresholds().values() for v2 in v1.values())


def get_channels():
    return _get_global()['channels']


def get_products():
    return _get_global()['products']


def get_limit():
    return _get_global()['days_limit']


def get_limit_facets():
    return _get_global()['facets_limit']


def get_cache_time():
    return _get_global()['cache_time']


def get_database():
    return _get_local().get('database', '')


def get_memcached(k):
    return _get_local().get('memcached', {}).get(k, '')
