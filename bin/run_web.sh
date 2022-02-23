#!/bin/bash

set -euo pipefail

ARGS="-b 0.0.0.0:$PORT --limit-request-line 8190 --max-requests 10 --workers=3 crashstop:app"

if [ -f /server.crt ] && [ -f /server.key ]
then
    echo "Running with HTTPS"
    gunicorn --reload --reload-extra-file static --reload-extra-file templates --certfile=/server.crt --keyfile=/server.key $ARGS
else
    echo "Running with HTTP"
    gunicorn $ARGS
fi
