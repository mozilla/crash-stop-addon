# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import config, models, signatures
from unittest.mock import patch
from .common import get_all_versions


@patch('crashstop.buildhub.get', get_all_versions)
def test_add_builds(create_db):
    # get the data from buildhub and put them in the db
    signatures.update()

    products = config.get_products()
    channels = config.get_channels()
    dbdata = signatures.get_all_versions(products, channels)

    assert get_all_versions() == dbdata


@patch('crashstop.buildhub.get', get_all_versions)
def test_add_builds_here(create_db):
    signatures.update()
    data = get_all_versions()
    fa_data = data['FennecAndroid']['beta']
    del fa_data[0]

    models.Buildid.add_buildids(data)

    dbdata = models.Buildid.get_versions('FennecAndroid', 'beta')
    dbdata = dbdata['FennecAndroid']['beta']

    assert fa_data == dbdata

    assert models.Buildid.add_buildids({}) is None
