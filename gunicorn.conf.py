# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


def post_worker_init(worker):
    # Import in the worker after the application has initialized its logging.
    from crashstop.memory import install_cleanup

    install_cleanup()
