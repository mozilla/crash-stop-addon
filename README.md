# crash-stop-addon

[![Build Status](https://api.travis-ci.org/mozilla/crash-stop-addon.svg?branch=master)](https://travis-ci.org/mozilla/crash-stop-addon)
[![Coverage Status](https://coveralls.io/repos/github/mozilla/crash-stop-addon/badge.svg?branch=master)](https://coveralls.io/r/mozilla/crash-stop-addon)
[![Updates](https://pyup.io/repos/github/mozilla/crash-stop-addon/shield.svg)](https://pyup.io/repos/github/mozilla/crash-stop-addon/)


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
Then you can test in your browser: https://localhost:8080/sumup.html?s=OOM%20|%20small.

## Running tests

In using docker:
```sh
docker-compose -f docker-compose-test.yml run tests
```

## Bugs

https://github.com/mozilla/crash-stop-addon/issues/new

## Contact

Email: calixte@mozilla.com
