# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
from . import config


app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', config.get_database()
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def setup():
    from . import models, signatures

    models.clear()
    models.create()
    signatures.update()


@app.route('/sumup.html')
def sumup_html():
    from crashstop import html

    return html.sumup()


@app.route('/')
def help_html():
    return send_from_directory('../static', 'help.html')


@app.route('/<path:filename>')
def something(filename):
    return send_from_directory(app.static_folder, filename)
