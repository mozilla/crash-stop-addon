FROM alpine

RUN apk update
RUN apk add openssl
RUN openssl req \
    -newkey rsa:4096 -nodes -sha256 -keyout server.key \
    -x509 -days 365 -out server.crt \
    -subj "/C=FR/ST=Paris/L=Paris/O=Crash-Stop/OU=Crash/CN=crash-stop.org"

FROM python:slim

ENV DATABASE_URL=postgresql://crash:stop@postgres:5432/crashstop
ENV MEMCACHEDCLOUD_SERVERS=memcached:11211
ENV MEMCACHEDCLOUD_USERNAME=
ENV MEMCACHEDCLOUD_PASSWORD=
ENV PORT=8080
ENV PYTHONPATH=.
ENV PYTHONUNBUFFERED=1
    
WORKDIR /tmp

ADD requirements.txt /tmp/requirements.txt
ADD test-requirements.txt /tmp/test-requirements.txt

RUN pip install -r requirements.txt
RUN pip install -r test-requirements.txt

WORKDIR /

COPY --from=0 server.* /
ADD Procfile .
RUN sed -i 's/gunicorn/gunicorn --reload --reload-extra-file static --reload-extra-file templates --certfile=\/server.crt --keyfile=\/server.key/g' Procfile

WORKDIR /code

EXPOSE 8080
