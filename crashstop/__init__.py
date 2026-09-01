# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from libmozdata import hgmozilla, socorro
from libmozdata.connection import Connection
import os
from . import config


# Socorro throttles anonymous callers hard and libmozdata retries 429s, so
# without a token a burst of SuperSearch queries ends up sleeping past the
# Heroku router timeout.
socorro.Socorro.TOKEN = os.getenv('SOCORRO_TOKEN', socorro.Socorro.TOKEN)

# Keep a request within Heroku's 30s router timeout. libmozdata's defaults
# (30s timeout, 256 retries with a 1s backoff factor) let a single throttled
# query sleep for minutes. urllib3 counts read timeouts against the same retry
# budget, and hg.mozilla.org 302s to hg-edge.mozilla.org so each hg query pays
# the timeout twice -- which is 20s of the budget already. Retrying inside a
# request is not where the remaining seconds are best spent: the value is
# cached for 10min once it lands, so a failure is cheaper to retry on the next
# request than to sit on here.
#
# These have to be set on the class rather than passed to the constructors:
# Connection.__init__ builds the session and the Retry policy from the class
# attributes *before* it reads the max_retries/max_workers kwargs, so those
# kwargs are silently ignored.
Connection.TIMEOUT = 10
Connection.MAX_RETRIES = 0
# The default is cpu_count(), which on a dyno reports the host's CPUs, and a
# fresh pool is created per SuperSearch instance (one per product, plus one
# per leftover buildid).
Connection.MAX_WORKERS = 8

# hg.mozilla.org 302s to hg-edge.mozilla.org and each hop gets the full
# timeout, so query the edge directly. `remote` has to be set alongside it:
# libmozdata derives it from HG_URL == 'https://hg.mozilla.org' and, when it
# comes out false, get_repo_url() returns the bare host without the repo path.
hgmozilla.Mercurial.HG_URL = 'https://hg-edge.mozilla.org'
hgmozilla.Mercurial.remote = True

app = Flask(__name__, template_folder='../templates', static_folder='../static')

uri = os.getenv('DATABASE_URL', config.get_database())
# Workaround for Heroku
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
engine_options = {'pool_recycle': 300, 'pool_pre_ping': True}
if uri.startswith('postgresql'):
    # QueuePool-only knobs (sqlite gets a Static/SingletonThreadPool, which
    # rejects them). essential-0 allows 20 connections and there are 6 web
    # processes (2 dynos * 3 workers) plus the clock dyno, so cap each process
    # at 2: 12 + clock leaves headroom. A request only needs the DB for one
    # indexed select, so the threads barely contend -- and pool_timeout makes
    # a saturated pool fail fast instead of blocking for the default 30s,
    # which would be a router timeout.
    engine_options.update({'pool_size': 1, 'max_overflow': 1, 'pool_timeout': 5})
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
db = SQLAlchemy(app)

from . import html  # noqa: E402  (must import after db/app are defined)


def setup():
    from . import models, signatures

    with app.app_context():
        models.clear()
        models.create()
        signatures.update()


@app.route('/sumup.html')
def sumup_html():
    return html.sumup()


@app.route('/')
def help_html():
    return send_from_directory('../static', 'help.html')


@app.route('/<path:filename>')
def something(filename):
    return send_from_directory(app.static_folder, filename)
