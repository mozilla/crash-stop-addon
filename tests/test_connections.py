# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import gc
from types import SimpleNamespace
from unittest.mock import Mock
import weakref

from libmozdata.connection import Connection, Query
import pytest
from requests import Response
from requests.adapters import HTTPAdapter

from crashstop import config, datacollector, signatures
from crashstop.connections import managed_connections


def test_completed_response_released_without_cyclic_gc(monkeypatch):
    references = []
    received = []

    def send(adapter, request, **kwargs):
        response = Response()
        response.status_code = 200
        response.request = request
        response.url = request.url
        response._content = b'{"value": "' + b'x' * 1024 * 1024 + b'"}'
        references.append(weakref.ref(response))
        return response

    monkeypatch.setattr(HTTPAdapter, 'send', send)

    def query():
        with managed_connections() as connections:
            connection = Connection(
                'https://example.invalid/',
                queries=[Query(
                    'https://example.invalid/',
                    handler=lambda data: received.append(len(data['value'])),
                )],
            )
            references.append(weakref.ref(connection))
            connections.append(connection)
            connection.wait()

    # The regression is relying on cyclic GC to release completed responses.
    # Disable it so a collection cannot make a leaking implementation pass.
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        query()
        assert received == [1024 * 1024]
        assert all(reference() is None for reference in references)
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def make_connection():
    return SimpleNamespace(
        session=SimpleNamespace(close=Mock()),
        results=[object()],
        wait=Mock(),
    )


@pytest.mark.parametrize('failure', ['none', 'database', 'setup', 'wait', 'hg'])
def test_request_closes_all_started_connections(monkeypatch, failure):
    hg, first, second = [make_connection() for _ in range(3)]
    started = [hg]
    error = RuntimeError('upstream failed')
    monkeypatch.setattr(datacollector, 'get_pushdates', lambda _: (hg, {}))

    def versions(products, channels):
        if failure == 'database':
            raise error
        return {p: {c: [] for c in channels} for p in products}

    monkeypatch.setattr(signatures, 'get_all_versions', versions)

    def get_data(*args):
        connections = args[-1]
        connections.extend([first, second])
        started.extend([first, second])
        if failure == 'setup':
            raise error
        return {}

    monkeypatch.setattr(datacollector, 'get_sgns_data', get_data)
    if failure == 'wait':
        first.wait.side_effect = error
    if failure == 'hg':
        hg.wait.side_effect = error

    if failure in ('database', 'setup', 'wait'):
        with pytest.raises(RuntimeError) as caught:
            signatures.get_for_urls_sgns([], ['test signature'])
        assert caught.value is error
    else:
        assert signatures.get_for_urls_sgns([], ['test signature']) == {}
        first.wait.assert_called_once()
        second.wait.assert_called_once()

    for connection in started:
        connection.session.close.assert_called_once()
        assert connection.results == []


def test_no_signatures_closes_hg(monkeypatch):
    hg = make_connection()
    monkeypatch.setattr(datacollector, 'get_pushdates', lambda _: (hg, {}))
    assert signatures.get_for_urls_sgns([], []) == {'data': {}, 'versions': {}}
    hg.wait.assert_called_once()
    hg.session.close.assert_called_once()
    assert hg.results == []


def test_close_failure_still_cleans_other_connections():
    first, second = make_connection(), make_connection()
    second.session.close.side_effect = RuntimeError('close failed')
    with pytest.raises(RuntimeError, match='close failed'):
        with managed_connections() as connections:
            connections.extend([first, second])
    for connection in [first, second]:
        connection.session.close.assert_called_once()
        assert connection.results == []


@pytest.mark.parametrize('operation', ['fenix', 'filter'])
def test_scheduled_queries_close_on_failure(monkeypatch, operation):
    connection = make_connection()
    connection.wait.side_effect = RuntimeError('query failed')
    monkeypatch.setattr(
        datacollector.socorro, 'SuperSearch',
        Mock(return_value=connection, URL='https://example.invalid/'),
    )
    with pytest.raises(RuntimeError, match='query failed'):
        if operation == 'fenix':
            datacollector.get_fenix_buildids(config.get_channels())
        else:
            datacollector.filter_buildids_helper([], [], 'nightly')
    connection.session.close.assert_called_once()
    assert connection.results == []
