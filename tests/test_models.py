# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import config, normalize_database_uri, signatures
from sqlalchemy import create_engine
from unittest.mock import patch
from .common import get_all_versions


def test_normalize_database_uri():
    for uri in ['postgres://u:p@h/db', 'postgresql://u:p@h/db']:
        uri = normalize_database_uri(uri)
        assert uri == 'postgresql+psycopg2://u:p@h/db'
        # Load the driver without connecting to a database.
        assert create_engine(uri).dialect.driver == 'psycopg2'

    assert normalize_database_uri('sqlite:////tmp/db') == 'sqlite:////tmp/db'


@patch('crashstop.buildhub.get', get_all_versions)
def test_add_builds(create_db):
    # get the data from buildhub and put them in the db
    signatures.update()

    products = config.get_products()
    channels = config.get_channels()
    dbdata = signatures.get_all_versions(products, channels)

    assert get_all_versions() == dbdata
