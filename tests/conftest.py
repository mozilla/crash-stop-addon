# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import crashstop
import json
import os.path
import pytest
from .common import dumpjson


@pytest.fixture
def app():
    return crashstop.app


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
