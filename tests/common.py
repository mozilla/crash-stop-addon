# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from crashstop import utils


def get_all_versions():
    with open('tests/data/buildhub/get.json', 'r') as In:
        versions = json.load(In)
    for prod, i in versions.items():
        for chan, j in i.items():
            for x in j:
                x[0] = utils.get_build_date(x[0])
        if 'esr' not in i:
            i['esr'] = []
    return versions


def dumpjson(path, data):
    with open(path, 'w') as Out:
        json.dump(data, Out, sort_keys=True, indent=4, separators=(',', ': '))


def get_params_query(params):
    res = []
    for k, v in sorted(params.items()):
        if isinstance(v, list) or isinstance(v, set):
            res += ['{}={}'.format(k, x) for x in list(sorted(v))]
        else:
            res.append('{}={}'.format(k, v))
    return '?' + '&'.join(res)
