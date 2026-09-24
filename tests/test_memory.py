# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import gc
import json
from queue import Empty, SimpleQueue
from types import SimpleNamespace
from unittest.mock import Mock
import weakref

import pytest

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


def test_trim_without_forced_python_collection(monkeypatch):
    collect = Mock()
    monkeypatch.setattr(memory.gc, 'collect', collect)
    monkeypatch.setattr(memory, 'read_memory', Mock(side_effect=[
        {'rss_kib': 300}, {'rss_kib': 100},
    ]))
    result = memory.collect_memory(lambda pad: 1, collect_python=False)
    collect.assert_not_called()
    assert result['before']['rss_kib'] == 300
    assert result['after_trim']['rss_kib'] == 100
    assert result['after_gc'] is None
    assert result['collected_objects'] is None


def test_timer_runs_without_signal(monkeypatch, caplog):
    requests = SimpleQueue()

    def collect(trim, *, collect_python):
        assert collect_python is False
        requests.put(False)
        return {'pid': 123}

    monkeypatch.setattr(memory, 'collect_memory', collect)
    memory.run_cleanups(requests, lambda pad: 1, interval=0.001)
    assert '"trigger": "timer"' in caplog.text


def test_timer_failure_keeps_manual_cleanup_working(monkeypatch, caplog):
    requests = Mock()
    requests.get.side_effect = [Empty, True, False]
    cleanup = Mock(side_effect=[RuntimeError('failed'), {'pid': 123}])
    monkeypatch.setattr(memory, 'collect_memory', cleanup)
    trim = Mock()
    memory.run_cleanups(requests, trim, interval=300)
    assert cleanup.call_args_list[0].kwargs == {'collect_python': False}
    assert cleanup.call_args_list[1].kwargs == {}
    assert 'memory_cleanup failed' in caplog.text
    assert '"trigger": "signal"' in caplog.text
    assert all(0 < call.kwargs['timeout'] <= 360 for call in requests.get.call_args_list)


@pytest.mark.parametrize('interval,trim', [(0, Mock()), (300, None)])
def test_no_timer_when_disabled_or_unsupported(interval, trim):
    requests = Mock()
    requests.get.return_value = False
    memory.run_cleanups(requests, trim, interval)
    requests.get.assert_called_once_with(timeout=None)


def test_negative_interval_rejected(monkeypatch):
    monkeypatch.setenv('MEMORY_TRIM_INTERVAL_SECONDS', '-1')
    with pytest.raises(ValueError, match='non-negative'):
        memory.install_cleanup()


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
    monkeypatch.setenv('MEMORY_TRIM_INTERVAL_SECONDS', '300')
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
    requests, trim, interval = thread.call_args.kwargs['args']
    assert requests.get_nowait() is True
    assert trim is None
    assert interval == 300
    assert thread.call_args.kwargs['daemon'] is True
    thread.return_value.start.assert_called_once()
