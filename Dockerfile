FROM alpine

RUN apk update && apk add openssl
RUN openssl req \
    -newkey rsa:4096 -nodes -sha256 -keyout server.key \
    -x509 -days 365 -out server.crt \
    -subj "/C=FR/ST=Paris/L=Paris/O=Crash-Stop/OU=Crash/CN=crash-stop.org"

FROM python:3.14-slim

# Bring in the uv binary (https://docs.astral.sh/uv/guides/integration/docker/).
COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV DATABASE_URL=postgresql://crash:stop@postgres:5432/crashstop
ENV MEMCACHEDCLOUD_SERVERS=memcached:11211
ENV MEMCACHEDCLOUD_USERNAME=
ENV MEMCACHEDCLOUD_PASSWORD=
ENV PORT=8081
ENV PYTHONPATH=.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install the locked dependencies (plus the test extra) into a dedicated venv
# and put it on PATH, so gunicorn/honcho/python/pytest resolve to it regardless
# of the working directory (docker-compose mounts the source at /code).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1

WORKDIR /tmp

ADD pyproject.toml uv.lock .python-version /tmp/

RUN uv sync --locked --no-install-project --extra test

WORKDIR /

COPY --from=0 server.* /
ADD Procfile .

WORKDIR /code

EXPOSE 8081
