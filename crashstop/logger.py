# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
from logging.config import dictConfig


dictConfig(
    {
        "version": 1,
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
            },
        },
        "root": {
            "level": logging.INFO,
            "handlers": ["wsgi"],
        },
    }
)


logger = logging.getLogger()
