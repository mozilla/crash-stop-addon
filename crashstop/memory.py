# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""Measure manual cleanup and optionally trim idle heap pages periodically."""

import ctypes
import gc
import json
import os
from pathlib import Path
from queue import Empty, SimpleQueue
import random
import signal
import threading
import time

from .logger import logger


def read_memory():
    # ru_maxrss is a historical maximum: it cannot measure a cleanup's effect.
    # smaps_rollup reports current resident/proportional memory and swap in KiB.
    try:
        lines = Path('/proc/self/smaps_rollup').read_text().splitlines()
    except OSError:
        return None
    fields = {'Rss:': 'rss_kib', 'Pss:': 'pss_kib', 'Swap:': 'swap_kib'}
    return {
        fields[parts[0]]: int(parts[1])
        for line in lines
        if (parts := line.split()) and parts[0] in fields
    }


def load_malloc_trim():
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (OSError, AttributeError):
        # Local development may use macOS or a libc other than glibc.
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


def collect_memory(trim, *, collect_python=True):
    started = time.monotonic()
    before = read_memory()
    collected = gc.collect() if collect_python else None
    after_gc = read_memory() if collect_python else None
    trimmed = bool(trim(0)) if trim is not None else None
    after_trim = read_memory()
    return {
        'pid': os.getpid(),
        'dyno': os.getenv('DYNO'),
        'before': before,
        'after_gc': after_gc,
        'after_trim': after_trim,
        'collected_objects': collected,
        'trim_released_memory': trimmed,
        'duration_ms': round((time.monotonic() - started) * 1000, 2),
    }


def run_cleanups(requests, trim, interval=0):
    def next_deadline():
        if interval > 0 and trim is not None:
            # Workers boot together; spread their allocator work over time.
            return time.monotonic() + random.uniform(0.8, 1.2) * interval
        return None

    deadline = next_deadline()
    while True:
        automatic = False
        timeout = max(0, deadline - time.monotonic()) if deadline is not None else None
        try:
            if not requests.get(timeout=timeout):
                return
        except Empty:
            automatic = True
        try:
            # Automatic trimming releases free libc pages. Keep Python's GC on
            # its normal schedule; a full collection remains a manual diagnostic.
            if automatic:
                result = collect_memory(trim, collect_python=False)
            else:
                result = collect_memory(trim)
            result['trigger'] = 'timer' if automatic else 'signal'
            logger.info('memory_cleanup %s', json.dumps(result, sort_keys=True))
        except Exception:
            # A failed diagnostic must not terminate the worker or listener.
            logger.exception('memory_cleanup failed pid=%s', os.getpid())
        deadline = next_deadline()


def install_cleanup():
    interval = int(os.getenv('MEMORY_TRIM_INTERVAL_SECONDS', '0'))
    if interval < 0:
        raise ValueError('MEMORY_TRIM_INTERVAL_SECONDS must be non-negative')
    requests = SimpleQueue()
    # Resolve libc before taking measurements, so loading it does not skew them.
    trim = load_malloc_trim()

    def request_cleanup(signum, frame):
        # Never call gc.collect() in a signal handler: it could interrupt a GC
        # already in progress. CPython's SimpleQueue.put is reentrant; a separate
        # thread handles the actual work once it can acquire the interpreter.
        requests.put(True)

    # Gunicorn does not use SIGURG. Keep its reload/shutdown/log signals intact.
    signal.signal(signal.SIGURG, request_cleanup)
    signal.siginterrupt(signal.SIGURG, False)
    threading.Thread(
        target=run_cleanups,
        args=(requests, trim, interval),
        name='memory-cleanup',
        daemon=True,
    ).start()
    logger.info(
        'memory_cleanup ready pid=%s signal=SIGURG trim_interval_seconds=%s',
        os.getpid(), interval if trim is not None else 0,
    )
