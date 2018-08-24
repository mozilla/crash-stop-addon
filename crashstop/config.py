# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json


_THRESHOLDS = None
_GLOBAL = None
_LOCAL = None


def _get_thresholds():
    global _THRESHOLDS
    if not _THRESHOLDS:
        with open('./config/thresholds.json', 'r') as In:
            _THRESHOLDS = json.load(In)
    return _THRESHOLDS


def _get_global():
    global _GLOBAL
    if not _GLOBAL:
        with open('./config/global.json', 'r') as In:
            _GLOBAL = json.load(In)
    return _GLOBAL


def _get_local():
    global _LOCAL
    if not _LOCAL:
        try:
            with open('./config/local.json', 'r') as In:
                _LOCAL = json.load(In)
        except Exception:
            _LOCAL = {}
    return _LOCAL


def get_min_total(prod, chan):
    return _get_thresholds()[prod][chan]['min_total_crashes']


def get_versions(prod, chan):
    return _get_thresholds()[prod][chan]['versions']


def get_channels():
    return _get_global()['channels']


def get_products():
    return _get_global()['products']


def get_cache_time():
    return _get_global()['cache_time']


def get_database():
    return _get_local().get('database', '')


def get_memcached(k):
    return _get_local().get('memcached', {}).get(k, '')
