# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import app, cache, models, signatures
import json
import os.path
import pytest
from unittest.mock import patch
from .common import dumpjson, get_all_versions


def get_or_create(path, data):
    if not os.path.isfile(path):
        dumpjson(path, data)
        return data
    else:
        with open(path, 'r') as Out:
            return json.load(Out)


@pytest.fixture
def get_result():
    yield get_or_create


@pytest.fixture()
def create_db():
    models.create()
    yield None
    models.clear()


@pytest.fixture
def client(create_db):
    cache.clear()

    with patch('crashstop.buildhub.get', get_all_versions):
        signatures.update()

    app.config['TESTING'] = True
    client = app.test_client()

    yield client
