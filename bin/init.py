# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from crashstop import models, signatures


while True:
    try:
        models.create()
        break
    except Exception as exc:
        print(f"Something happened... {exc}")

signatures.update()
print("Done init")
