# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from libmozdata import socorro
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

app = Flask(__name__, template_folder='../templates', static_folder='../static')

uri = os.getenv('DATABASE_URL', config.get_database())
# Workaround for Heroku
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
