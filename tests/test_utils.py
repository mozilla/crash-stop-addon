# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime
import pytz
from crashstop import utils


def test_get_major():
    assert utils.get_major('12.34.0') == 12
    assert utils.get_major('12') == -1
    assert utils.get_major('12.0b1') == 12


def test_strip_rc():
    assert utils.strip_rc('65.0.1rc2') == '65.0.1'


def test_get_channel_revision():
    chan_rev = utils.get_channel_revision(
        ['beta|1234', 'nightly|5678', '91012', 'beta|91011']
    )
    assert chan_rev == {'beta': ['1234', '91011'], 'nightly': ['5678']}


def test_get_build_date():
    assert utils.get_build_date('20180102123456') == datetime(
        2018, 1, 2, 12, 34, 56, 0, pytz.utc
    )
    assert utils.get_build_date(20180102123456) == datetime(
        2018, 1, 2, 12, 34, 56, 0, pytz.utc
    )


def test_get_buildid():
    date = datetime(2018, 1, 2, 12, 34, 56, 0, pytz.utc)
    assert utils.get_buildid(date) == '20180102123456'


def test_get_position():
    dates = [
        datetime(2018, 1, 2, 12, 34, 56, 0, pytz.utc),
        datetime(2018, 1, 4, 12, 34, 56, 0, pytz.utc),
        datetime(2018, 1, 6, 12, 34, 56, 0, pytz.utc),
        datetime(2018, 1, 8, 12, 34, 56, 0, pytz.utc),
    ]

    assert utils.get_position(None, dates) == -2
    assert utils.get_position(datetime(2018, 1, 5, 12, 34, 56, 0, pytz.utc), dates) == 1
    assert (
        utils.get_position(datetime(2018, 1, 1, 12, 34, 56, 0, pytz.utc), dates) == -1
    )
    assert utils.get_position(datetime(2018, 1, 9, 12, 34, 56, 0, pytz.utc), dates) == 3


def test_update_params():
    params = {'a': 1, 'b': 2}
    extra = {'b': 3, 'c': 4}

    r = utils.update_params(params, extra)
    assert r
    assert params == {'a': 1, 'b': 2, 'c': 4}

    extra = {'c': 5}
    r = utils.update_params(params, extra)
    assert not r
    assert params == {'a': 1, 'b': 2, 'c': 4}


def test_is_java():
    sgns = ['foo (bar.java)', 'oof (rab.java)', 'foo(Native Method)']

    assert utils.is_java(sgns)

    sgns.append('foo::bar')

    assert not utils.is_java(sgns)
