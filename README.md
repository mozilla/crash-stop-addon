# crash-stop-addon

[![CI](https://github.com/mozilla/crash-stop-addon/actions/workflows/ci.yml/badge.svg)](https://github.com/mozilla/crash-stop-addon/actions/workflows/ci.yml)


crash-stop addon is used to display crash data and patch information in Bugzilla.
The addon gets an iframe containing these information from a server hosted on Heroku.
So here we've code for the server (Python) and the code for the addon (Javascript).

Crash data are coming from https://crash-stats.mozilla.org and patch information are coming from https://hg.mozilla.org.
The WebExtension is available at https://addons.mozilla.org/firefox/addon/bugzilla-crash-stop/.
You can find more explanations here: https://crash-stop-addon.herokuapp.com/.

## Setup

Install docker and docker-compose and then:
```sh
docker-compose up --build
```
Then you can test in your browser: https://localhost:8081/sumup.html?s=OOM%20|%20small.

## Running tests

In using docker:
```sh
docker-compose -f docker-compose-test.yml run tests
```

## Bugs

https://github.com/mozilla/crash-stop-addon/issues/new

## Memory cleanup

Web workers return free glibc heap pages to the OS approximately every five
minutes, with 20% jitter to spread work across workers. This calls
`malloc_trim(0)` in a background thread and leaves Python's normal GC schedule
unchanged. Configure `MEMORY_TRIM_INTERVAL_SECONDS` to change the interval;
set it to `0` to disable automatic trimming. Automatic trimming is disabled
when `malloc_trim` is unavailable, including on macOS.

The `memory_cleanup` JSON logs include `trigger: "timer"`, memory before and
after trimming, and elapsed time. `after_gc` and `collected_objects` are null
when the cleanup skipped a forced Python collection.

### Manual diagnostic

Each web worker accepts `SIGURG` to run a full Python garbage collection,
then glibc's `malloc_trim(0)`. The `memory_cleanup` JSON log records
`trigger: "signal"`, the worker PID, dyno,
current RSS/PSS/swap in KiB before cleanup, after GC, and after trimming.
`trim_released_memory: null` means this platform does not support trimming.

Use `heroku ps:exec --app crash-stop-addon --dyno web.1` to enter an existing
dyno, identify the worker PIDs with `ps -eo pid,ppid,args`, and send
`kill -URG <worker-pid>` to each worker to measure. Repeat on `web.2`.
Choose the Gunicorn children, not the master. Startup logs also identify them
with `memory_cleanup ready pid=...`. Read results with
`heroku logs --app crash-stop-addon --source app --tail`.

Run this during quiet traffic: other requests in the same worker can affect
the measurements. An ordinary `heroku run` process has a separate heap and
cannot clean up web workers. No HTTP endpoint exposes this diagnostic.

## Contact

Email: calixte@mozilla.com
