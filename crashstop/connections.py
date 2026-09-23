# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from contextlib import contextmanager, ExitStack


def close_connection(connection):
    try:
        # Finish running callbacks before dropping their futures. close() also
        # cancels queued work and joins the FuturesSession's worker threads.
        connection.session.close()
    finally:
        # libmozdata keeps completed futures. Each response's request holds a
        # callback that captures the connection, forming a cycle:
        # connection -> future -> response -> request -> callback -> connection.
        # Closing the session alone leaves response bodies in this cycle until
        # cyclic GC runs. We only need the data extracted by the handlers.
        connection.results.clear()


@contextmanager
def managed_connections():
    """Close every registered connection, including when setup or wait fails."""
    connections = []
    try:
        yield connections
    finally:
        # ExitStack still runs the other callbacks if a close itself raises.
        with ExitStack() as cleanup:
            for connection in connections:
                cleanup.callback(close_connection, connection)
