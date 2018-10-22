# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import request, render_template
import json
from . import cache, config


def sumup():
    # cache.clear()
    sgns = request.args.getlist('s')
    hgurls = request.args.getlist('h')
    addon_version = request.args.get('v', '')
    extra = dict(request.args)
    for x in 'shv':
        if x in extra:
            del extra[x]

    data, affected, has_extra = cache.get_sumup(hgurls, sgns, extra)
    if addon_version <= '0.3.0':
        affected = {k: max(v) for k, v in affected.items()}

    return render_template(
        'sumup.html',
        data=data,
        affected=affected,
        has_extra=has_extra,
        products=config.get_products(),
        addon_version=addon_version,
        enumerate=enumerate,
        zip=zip,
        jsonify=json.dumps,
    )
