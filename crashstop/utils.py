# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from bisect import bisect_left
from datetime import datetime
import math
import pytz
import re
import six


KOTLIN_PAT = re.compile(r'.*\.kt:[0-9]+\)$')


def get_major(v):
    """Get major version as an int from a version string
    """
    v = v.split('.')
    if len(v) >= 2:
        return int(v[0])
    return -1


def strip_rc(v):
    return v.split('rc', 1)[0]


def get_channel_revision(pairs):
    """Get a map channel->revision
    """
    res = {}
    for pair in pairs:
        pair = pair.split('|')
        if len(pair) < 2:
            continue
        repo, rev = pair
        if repo in res:
            res[repo].append(rev)
        else:
            res[repo] = [rev]

    return res


def get_params_for_link(query={}):
    params = {
        'product': '',
        'date': '',
        'release_channel': '',
        'version': '',
        'signature': '',
        '_facets': [
            'url',
            'user_comments',
            'install_time',
            'version',
            'address',
            'moz_crash_reason',
            'reason',
            'build_id',
            'platform_pretty_version',
            'signature',
            'useragent_locale',
        ],
    }
    params.update(query)
    return params


def get_build_date(bid):
    if isinstance(bid, six.string_types):
        Y = int(bid[0:4])
        m = int(bid[4:6])
        d = int(bid[6:8])
        H = int(bid[8:10])
        M = int(bid[10:12])
        S = int(bid[12:])
    else:
        # 20160407164938 == 2016 04 07 16 49 38
        N = 5
        r = [0] * N
        for i in range(N):
            r[i] = bid % 100
            bid //= 100
        Y = bid
        S, M, H, d, m = r
    d = datetime(Y, m, d, H, M, S)
    dutc = pytz.utc.localize(d)

    return dutc


def get_buildid(date):
    return date.strftime('%Y%m%d%H%M%S')


def get_position(pushdate, dates):
    if pushdate:
        return bisect_left(dates, pushdate) - 1

    return -2


def update_params(params, extra):
    added = False
    for k, v in extra.items():
        if k not in params:
            params[k] = v
            added = True
    return added


def is_java(signatures):
    for sgn in signatures:
        if not sgn.endswith('.java)') and not sgn.endswith('(Native Method)') and KOTLIN_PAT.match(sgn) is None:
            return False
    return True


def startup_crash_rate(data):
    res = [0, 0]
    for d in data:
        res[int(d['term'] == 'T')] = d['count']
    if res == [0, 0]:
        return -1
    return int(math.ceil(float(res[1]) / float(res[0] + res[1]) * 100.0))


def analyze_platforms(res, data):
    for i in data:
        platform = i['term']
        if platform.startswith('Windows'):
            short = 'Windows'
        elif platform.startswith('OS X'):
            short = 'OS X'
        elif platform.startswith('Linux'):
            short = 'Linux'
        else:
            short = 'others'
        if short in res:
            res[short] += i['count']
        else:
            res[short] = i['count']


def percentage_platforms(data):
    total = float(sum(data.values()))
    for p, v in data.items():
        data[p] = math.ceil(float(v) / total * 1000.0) / 10.0
    return data
