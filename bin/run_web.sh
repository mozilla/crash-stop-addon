#!/bin/bash

set -euo pipefail

# Periodically return free libc pages to the OS. The worker adds 20% jitter;
# set this to 0 to disable automatic trimming while retaining manual SIGURG.
export MEMORY_TRIM_INTERVAL_SECONDS="${MEMORY_TRIM_INTERVAL_SECONDS:-300}"

# Use threads for concurrent requests while waiting on external services.
# Cache calls use one thread per worker to limit memcached connections.
# Recycle workers to limit memory growth; jitter staggers restarts.
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
