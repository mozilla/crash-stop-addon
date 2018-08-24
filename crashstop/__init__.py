# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import logging
import os
from . import config


app = Flask(__name__, template_folder='../templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', config.get_database()
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
log = logging.getLogger(__name__)


@app.route('/sumup.html')
def sumup_html():
    from crashstop import html

    return html.sumup()


@app.route('/')
def help_html():
    return send_from_directory('../static', 'help.html')


@app.route('/clouseau.ico')
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('../static', 'clouseau.ico')


@app.route('/<image>.png')
def image(image):
    return send_from_directory('../static', image + '.png')


@app.route('/stop.js')
def stop_js():
    return send_from_directory('../static', 'stop.js')


@app.route('/stop.css')
def stop_css():
    return send_from_directory('../static', 'stop.css')
