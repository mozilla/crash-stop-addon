# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import gc
import json
from queue import SimpleQueue
from types import SimpleNamespace
from unittest.mock import Mock
import weakref

from crashstop import memory


def test_read_current_memory(monkeypatch, tmp_path):
    rollup = tmp_path / 'smaps_rollup'
    rollup.write_text(
        '00000000-ffffffff ---p 00000000 00:00 0 [rollup]\n'
        'Rss: 20480 kB\nPss: 19000 kB\nPrivate_Dirty: 18000 kB\nSwap: 1024 kB\n'
    )
    monkeypatch.setattr(memory, 'Path', lambda _: rollup)
    assert memory.read_memory() == {
        'rss_kib': 20480, 'pss_kib': 19000, 'swap_kib': 1024,
    }


def test_memory_measurement_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, 'Path', lambda _: tmp_path / 'missing')
    assert memory.read_memory() is None


def test_collection_measurements_are_ordered(monkeypatch):
    events = []
    snapshots = iter([{'rss_kib': 300}, {'rss_kib': 200}, {'rss_kib': 100}])

    def read_memory():
        events.append('measure')
        return next(snapshots)

    def collect():
        events.append('gc')
        return 12

    def trim(pad):
        assert pad == 0
        events.append('trim')
        return 1

    monkeypatch.setattr(memory, 'read_memory', read_memory)
    monkeypatch.setattr(memory.gc, 'collect', collect)
    monkeypatch.setenv('DYNO', 'web.1')
    result = memory.collect_memory(trim)
    assert events == ['measure', 'gc', 'measure', 'trim', 'measure']
    assert result['dyno'] == 'web.1'
    assert result['before']['rss_kib'] == 300
    assert result['after_gc']['rss_kib'] == 200
    assert result['after_trim']['rss_kib'] == 100
    assert result['collected_objects'] == 12
    assert result['trim_released_memory'] is True


def test_cleanup_collects_cycles_without_malloc_trim(monkeypatch):
    monkeypatch.setattr(memory, 'read_memory', lambda: None)
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        obj = SimpleCycle()
        reference = weakref.ref(obj)
        obj.self_reference = obj
        del obj
        assert reference() is not None
        result = memory.collect_memory(None)
        assert reference() is None
        assert result['collected_objects'] >= 1
        assert result['trim_released_memory'] is None
    finally:
        if was_enabled:
            gc.enable()


class SimpleCycle:
    pass


def test_malloc_trim_signature(monkeypatch):
    trim = Mock()
    monkeypatch.setattr(memory.ctypes, 'CDLL', lambda _: SimpleNamespace(malloc_trim=trim))
    assert memory.load_malloc_trim() is trim
    assert trim.argtypes == [memory.ctypes.c_size_t]
    assert trim.restype == memory.ctypes.c_int


def test_malloc_trim_unavailable(monkeypatch):
    monkeypatch.setattr(memory.ctypes, 'CDLL', lambda _: SimpleNamespace())
    assert memory.load_malloc_trim() is None


def test_listener_survives_cleanup_failure(monkeypatch, caplog):
    requests = SimpleQueue()
    for value in [True, True, False]:
        requests.put(value)
    result = {'pid': 123, 'collected_objects': 7}
    monkeypatch.setattr(memory, 'collect_memory', Mock(side_effect=[RuntimeError('failed'), result]))
    memory.run_cleanups(requests, None)
    assert 'memory_cleanup failed' in caplog.text
    assert json.dumps(result, sort_keys=True) in caplog.text


def test_signal_only_queues_cleanup(monkeypatch):
    thread = Mock()
    signals = Mock()
    cleanup = Mock()
    monkeypatch.setattr(memory.threading, 'Thread', thread)
    monkeypatch.setattr(memory.signal, 'signal', signals)
    monkeypatch.setattr(memory.signal, 'siginterrupt', Mock())
    monkeypatch.setattr(memory, 'load_malloc_trim', lambda: None)
    monkeypatch.setattr(memory, 'collect_memory', cleanup)
    memory.install_cleanup()
    signal_number, handler = signals.call_args.args
    assert signal_number == memory.signal.SIGURG
    handler(signal_number, None)
    cleanup.assert_not_called()
    requests, trim = thread.call_args.kwargs['args']
    assert requests.get_nowait() is True
    assert trim is None
    assert thread.call_args.kwargs['daemon'] is True
    thread.return_value.start.assert_called_once()
