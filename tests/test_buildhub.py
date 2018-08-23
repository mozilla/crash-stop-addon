# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import buildhub
from datetime import datetime
import functools
import json
import os.path
import pytest
import pytz
from unittest.mock import patch
from .common import dumpjson


class MyResponse:

    path = 'tests/data/buildhub/buildhub.json'

    def __init__(self, err):
        self.err = err

    @property
    def headers(self):
        return {} if not self.err else {'Backoff': ''}

    def json(self):
        if not self.err:
            with open(MyResponse.path, 'r') as In:
                return json.load(In)

        return {}

    @staticmethod
    def post(err, url, data={}):
        return MyResponse(err)


@pytest.fixture()
def create_buildhub_data():
    if not os.path.isfile(MyResponse.path):
        data = buildhub.get_raw()
        dumpjson(MyResponse.path, data)

    yield None


@patch('requests.post', new=functools.partial(MyResponse.post, True))
def test_make_request_fail():
    query = buildhub.get_query()
    x = buildhub.make_request(query, 0.01, 5, lambda x: x)
    assert x is None


@patch('requests.post', new=functools.partial(MyResponse.post, False))
def test_make_request(create_buildhub_data):
    d = buildhub.get_raw()
    assert d == MyResponse(False).json()


@patch('requests.post', new=functools.partial(MyResponse.post, False))
def test_extract(create_buildhub_data, get_result):
    data = buildhub.get_raw()
    data, buildids, buildids_per_prod = buildhub.extract(data)
    data = {'data': data,
            'buildids': buildids,
            'buildids_per_prod': buildids_per_prod}
    x = get_result('tests/data/buildhub/extract.json', data)

    assert x['data'] == data['data']
    assert x['buildids'] == data['buildids']
    assert x['buildids_per_prod'] == data['buildids_per_prod']


@patch('requests.post', new=functools.partial(MyResponse.post, False))
def test_get_last_versions(create_buildhub_data, get_result):
    data = buildhub.get_raw()
    data, _, _ = buildhub.extract(data)
    buildhub.get_last_versions(data)
    x = get_result('tests/data/buildhub/last_versions.json', data)

    assert x == data


@patch('requests.post', new=functools.partial(MyResponse.post, False))
def test_add_unicity(create_buildhub_data, get_result):
    data = buildhub.get_raw()
    data, buildids, buildids_per_prod = buildhub.extract(data)
    buildhub.add_unicity_info(data, buildids, buildids_per_prod)
    x = get_result('tests/data/buildhub/unicity.json', data)

    assert x == data


@patch('requests.post', new=functools.partial(MyResponse.post, False))
@patch('crashstop.datacollector.filter_nightly_buildids', new=lambda x: x)
def test_get(create_buildhub_data, get_result):
    data = buildhub.get(bid_as_date=False)
    x = get_result('tests/data/buildhub/get.json', data)

    assert x == data


def test_get_bid_as_date():
    data = {'FennecAndroid': {'beta': [['20180709172241'],
                                       ['20180713213322']]}}
    x = {'FennecAndroid': {'beta': [[datetime(2018, 7, 9, 17, 22, 41, 0, pytz.utc)],
                                    [datetime(2018, 7, 13, 21, 33, 22, 0, pytz.utc)]]}}
    buildhub.get_bid_as_date(data)

    assert x == data
