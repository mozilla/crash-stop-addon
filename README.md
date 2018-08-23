# crash-stop-addon

crash-stop addon is used to display crash data and patch information in Bugzilla.
The addon gets an iframe containing these information from a server hosted on Heroku.
So here we've code for the server (Python) and the code for the addon (Javascript).

Crash data are coming from https://crash-stats.mozilla.com and patch information are coming from https://hg.mozilla.org.
The WebExtension is available at https://addons.mozilla.org/firefox/addon/bugzilla-crash-stop/


## Setup

Install the prerequisites via `pip`:
```sh
sudo pip install -r requirements.txt
```

## Running tests

Install test prerequisites via `pip`:
```sh
sudo pip install -r test-requirements.txt
```

Run tests:
```sh
pytest tests/
```

## Bugs

https://github.com/mozilla/crash-stop-addon/issues/new

## Contact

Email: calixte@mozilla.com
