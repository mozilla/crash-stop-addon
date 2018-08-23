# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import requests
import time
from . import config, datacollector as dc, utils
from .logger import logger


URL = 'https://buildhub.prod.mozaws.net/v1/buckets/build-hub/collections/releases/search'
VERSION_PAT = '[0-9\.]+(([ab][0-9]+)|esr)?'
LEGAL_CHANNELS = ['nightly', 'beta', 'release', 'esr']
CHANNELS = LEGAL_CHANNELS + ['aurora']
PRODUCTS = ['firefox', 'devedition', 'fennec']
SOCORRO_PRODUCTS = ['Firefox', 'FennecAndroid']
RPRODS = {'firefox': 'Firefox',
          'devedition': 'Firefox',
          'fennec': 'FennecAndroid'}


def make_request(params, sleep, retry, callback):
    """Query Buildhub"""
    params = json.dumps(params)

    for _ in range(retry):
        r = requests.post(URL, data=params)
        if 'Backoff' in r.headers:
            time.sleep(sleep)
        else:
            try:
                return callback(r.json())
            except BaseException as e:
                logger.error('Buildhub query failed with parameters: {}.'.format(params))
                logger.error(e, exc_info=True)
                return None

    logger.error('Too many attempts in buildhub.make_request (retry={})'.format(retry))

    return None


def get_last_versions(data):
    """Get the correct numbers of last versions according to thresholds.json.

       Args:
           data (dict): product => { channel => [(datetime(buildid), 'version'), ...] }
    """
    for prod, v1 in data.items():
        to_rm = []
        for chan, v2 in v1.items():
            if not v2:
                to_rm.append(chan)
                continue

            min_v = config.get_versions(prod, chan)
            # we keep only the last min_v versions
            if len(v2) > min_v:
                v1[chan] = v2[-min_v:]

        for x in to_rm:
            del v1[x]


def add_unicity_info(data, buildids, buildids_per_prod):
    """Add info about unicity of buildids.

       Args:
           data (dict): product => { channel => [(datetime(buildid), 'version'), ...] }
           buildids (dict): datetime(buildid) => True if buildid is unique
           buildids_per_prod (dict): product => {datetime(buildid)
                                                 => True if buildid is unique in its product, ...
       Returns:
           dict: product => { channel => [(datetime(buildid),
                                           'version',
                                           True if buildid is unique,
                                           True if builid is unique in its product), ...] }
    """
    for prod, v1 in data.items():
        buildids_p = buildids_per_prod[prod]
        for chan, v2 in v1.items():
            v1[chan] = [[b, v, buildids[b], buildids_p[b]] for b, v in v2]


def get_bid_as_date(data):
    """Replace buildid (str) by datetime"""
    for prod, v1 in data.items():
        for chan, v2 in v1.items():
            for e in v2:
                e[0] = utils.get_build_date(e[0])


def get_info(data):
    """Get info from Buildhub data"""
    data, buildids, buildids_per_prod = extract(data)
    improve(data, buildids, buildids_per_prod)
    return data


def extract(data):
    """Extract useful info from Buildhub data"""
    buildids = {}
    res = {p: {c: set() for c in LEGAL_CHANNELS} for p in SOCORRO_PRODUCTS}
    buildids_per_prod = {p: {} for p in SOCORRO_PRODUCTS}

    for product in data['aggregations']['products']['buckets']:
        prod = RPRODS[product['key']]
        res_p = res[prod]
        buildids_p = buildids_per_prod[prod]
        for channel in product['channels']['buckets']:
            chan = channel['key']
            res_pc = res_p['beta'] if chan == 'aurora' else res_p[chan]
            for buildid in channel['buildids']['buckets']:
                bid = buildid['key']
                version = buildid['versions']['buckets'][0]['key']
                if chan != 'aurora' or version.endswith('b1') or version.endswith('b2'):
                    res_pc.add((bid, version))

                    # finally if buildids[b] is True it means that we've only one buildid
                    buildids[bid] = bid not in buildids
                    buildids_p[bid] = bid not in buildids_p

    for v1 in res.values():
        for chan, v2 in v1.items():
            v1[chan] = [[x, y] for x, y in sorted(v2)]

    return res, buildids, buildids_per_prod


def improve(data, buildids, buildids_per_prod):
    """Improve the data we've in removing useless builds in nightly (low volume crashes)"""

    # Filter nightly builds according to the number of crashes and the threshold
    dc.filter_nightly_buildids(data)

    get_last_versions(data)
    add_unicity_info(data, buildids, buildids_per_prod)


def get_query():
    return {
        'aggs': {
            'products': {
                'terms': {
                    'field': 'source.product',
                    'size': len(PRODUCTS)
                },
                'aggs': {
                    'channels': {
                        'terms': {
                            'field': 'target.channel',
                            'size': len(CHANNELS)
                        },
                        'aggs': {
                            'buildids': {
                                'terms': {
                                    'field': 'build.id',
                                    'size': config.get_versions('Firefox', 'nightly') * 4,
                                    'order': {
                                        '_term': 'desc'
                                    }
                                },
                                'aggs': {
                                    'versions': {
                                        'terms': {
                                            'field': 'target.version',
                                            'size': 1,
                                            'order': {
                                                '_term': 'desc'
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        'query': {
            'bool': {
                'filter': [
                    {'regexp': {'target.version': {'value': VERSION_PAT}}},
                    {'terms': {'target.channel': CHANNELS}},
                    {'terms': {'source.product': PRODUCTS}}
                ]
            }
        },
        'size': 0}


def get(bid_as_date=True):
    """Get buildids and versions info from Buildhub"""
    data = get_query()
    data = make_request(data, 1, 100, get_info)
    if bid_as_date:
        get_bid_as_date(data)

    return data


def get_raw():
    data = get_query()
    return make_request(data, 1, 100, lambda x: x)
