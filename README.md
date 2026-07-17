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

## Contact

Email: calixte@mozilla.com
