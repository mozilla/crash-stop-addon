# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from dateutil.relativedelta import relativedelta
import json
from libmozdata.socorro import SuperSearch as _SuperSearch
from libmozdata import socorro
from libmozdata.connection import Connection, Query
from libmozdata import utils as lmdutils
import os.path
from .common import dumpjson, get_params_query


class MySuperSearch:

    PATH = 'tests/data/socorro/crash_data.json'
    URL = _SuperSearch.URL
    WEB_URL = _SuperSearch.WEB_URL

    @staticmethod
    def handler(json, data):
        data.append(json)

    @staticmethod
    def get_data(params):
        if os.path.isfile(MySuperSearch.PATH):
            with open(MySuperSearch.PATH, 'r') as In:
                data = json.load(In)
        else:
            data = {}

        for k, v in params.items():
            if isinstance(v, list):
                params[k] = sorted(v)

        params_str = get_params_query(params)
        if params_str not in data:
            hdata = []
            Connection(
                socorro.Socorro.API_URL,
                queries=Query(_SuperSearch.URL, params, MySuperSearch.handler, hdata),
            ).wait()
            data[params_str] = hdata[0]
            dumpjson(MySuperSearch.PATH, data)

            return hdata[0]

        return data[params_str]

    def __init__(self, *args, **kwargs):
        if 'handler' in kwargs:
            kwargs['handler'](
                MySuperSearch.get_data(kwargs['params']), kwargs['handlerdata']
            )
        else:
            for query in kwargs['queries']:
                query.handler(MySuperSearch.get_data(query.params), query.handlerdata)

    def wait(self):
        pass

    @staticmethod
    def get_search_date(start, end=None):
        return _SuperSearch.get_search_date(start, end=end)

    @staticmethod
    def get_link(params):
        return _SuperSearch.get_link(params)

    @staticmethod
    def get_signatures():
        def handler(json, data):
            for i in json['facets']['signature']:
                data.append(i['term'])

        if not os.path.exists('tests/data/socorro/test_date.json'):
            date = lmdutils.get_date_ymd('today')
            dumpjson('tests/data/socorro/test_date.json', date.strftime('%Y-%m-%d'))
        else:
            with open('tests/data/socorro/test_date.json', 'r') as In:
                date = lmdutils.get_date_ymd(json.load(In))

        few_days_ago = date - relativedelta(days=3)
        search_date = _SuperSearch.get_search_date(few_days_ago)

        params = {
            'date': search_date,
            '_results_number': 0,
            '_facets': 'signature',
            '_facets_size': 100,
        }

        data = {'Firefox': []}
        queries = []
        for prod, hdata in data.items():
            pparams = params.copy()
            pparams['product'] = prod
            queries.append(
                Query(
                    MySuperSearch.URL,
                    params=pparams,
                    handler=handler,
                    handlerdata=hdata,
                )
            )
        MySuperSearch(queries=queries).wait()

        return data
