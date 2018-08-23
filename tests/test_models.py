# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import config, models, signatures
import pytest
from unittest.mock import patch
from .common import get_all_versions


@pytest.fixture()
def create_db():
    models.clear()
    models.create()
    yield None


@patch('crashstop.buildhub.get', get_all_versions)
def test_add_builds(create_db):
    signatures.update()

    products = config.get_products()
    channels = config.get_channels()
    dbdata = signatures.get_all_versions(products, channels)

    assert get_all_versions() == dbdata
