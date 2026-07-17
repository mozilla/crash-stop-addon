# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
from libmozdata.hgmozilla import Revision as _Revision
from libmozdata.hgmozilla import Mercurial
from libmozdata.connection import Connection, Query
import os.path
from .common import dumpjson, get_params_query


class MyRevision:

    PATH = 'tests/data/hg/revisions.json'

    @staticmethod
    def handler(json, data):
        data.append(json)

    @staticmethod
    def get_url(channel):
        return _Revision.get_url(channel)

    @staticmethod
    def get_data(url, params):
        if os.path.isfile(MyRevision.PATH):
            with open(MyRevision.PATH, 'r') as In:
                data = json.load(In)
        else:
            data = {}

        params_str = get_params_query(params)
        if params_str not in data:
            hdata = []
            Connection(
                Mercurial.HG_URL,
                queries=Query(url, params, MyRevision.handler, hdata),
            ).wait()
            data[params_str] = hdata[0]
            dumpjson(MyRevision.PATH, data)

            return hdata[0]

        return data[params_str]

    def __init__(self, *args, **kwargs):
        # crashstop.datacollector.get_pushdates bakes the correct per-channel
        # URL into each query and calls Revision(queries=...) with no channel
        # kwarg. Fetch (on a cache miss) via the query's own URL rather than
        # rebuilding it from a single/guessed channel, so mixed-channel queries
        # (beta/release/esr) hit the right repository.
        if 'handler' in kwargs:
            url = _Revision.get_url(kwargs.get('channel', 'nightly'))
            kwargs['handler'](
                MyRevision.get_data(url, kwargs['params']),
                kwargs['handlerdata'],
            )
        else:
            for query in kwargs['queries']:
                query.handler(
                    MyRevision.get_data(query.url, query.params),
                    query.handlerdata,
                )

    def wait(self):
        pass
