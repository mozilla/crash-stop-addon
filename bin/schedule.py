# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from apscheduler.schedulers.blocking import BlockingScheduler
from libmozdata.connection import Connection
from crashstop import app, signatures


# crashstop/__init__.py tightens these so a web request fits in the Heroku
# router timeout. This job runs every two hours with no deadline and would
# rather be slow than leave the build data stale, so be patient here.
Connection.TIMEOUT = 60
Connection.MAX_RETRIES = 5

sched = BlockingScheduler(timezone="GMT")


@sched.scheduled_job('cron', hour='0/2')
def timed_job():
    with app.app_context():
        signatures.update()


sched.start()
