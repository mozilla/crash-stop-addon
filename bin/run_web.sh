#!/bin/bash

set -euo pipefail

# gthread rather than the default sync worker: a /sumup.html miss is almost
# entirely spent waiting on crash-stats, so 3 sync workers meant only 3
# requests in flight and the rest queueing at the router until it gave up.
# --timeout is just under Heroku's 30s so we get a logged failure instead of
# an opaque H12. --max-requests is deliberately low: at ~50 requests per
# worker per 5h, 500 meant a worker lived ~2 days, long enough for the slow
# memory growth we saw (R14 for 3.5h+ on one dyno until gunicorn killed the
# worker) to eat the whole 1GB. 100 recycles a worker about twice a day and
# bounds how far a leak can get; the jitter keeps the workers from all
# recycling at once. 4 threads gives 2 dynos * 3 workers * 4 = 24 concurrent
# requests, up from 6. Each thread holds its own memcached connection
# (bmemcached's Protocol is a threading.local), which the cache plan handles
# comfortably; the limit on going higher is really Socorro, since every extra
# in-flight request is another fan-out of SuperSearch queries.
ARGS="--config gunicorn.conf.py -b 0.0.0.0:$PORT --limit-request-line 8190 \
      --worker-class gthread --workers 3 --threads 4 \
      --timeout 25 --graceful-timeout 5 \
      --max-requests 100 --max-requests-jitter 20 \
      crashstop:app"

if [ -f /server.crt ] && [ -f /server.key ]
then
    echo "Running with HTTPS"
    gunicorn --reload --reload-extra-file static --reload-extra-file templates --certfile=/server.crt --keyfile=/server.key $ARGS
else
    echo "Running with HTTP"
    gunicorn $ARGS
fi
