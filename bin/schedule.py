# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from apscheduler.schedulers.blocking import BlockingScheduler
from crashstop import signatures


sched = BlockingScheduler()


@sched.scheduled_job('cron', hour='0/2')
def timed_job():
    signatures.update()


sched.start()
