# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import OrderedDict
import datetime
from libmozdata import socorro
import re
from sqlalchemy.exc import OperationalError
import time
from . import datacollector as dc
from . import buildhub, config, models, utils
from .logger import logger


FIRST_RELEASE_PAT = re.compile(r'^[0-9]+\.0$')


def update():
    d = datetime.datetime.now(datetime.timezone.utc)
    logger.info('Update data for {}: started.'.format(d))
    bids = buildhub.get()
    models.Buildid.add_buildids(bids)
    logger.info('Update data for {}: finished.'.format(d))


def get_all_versions(products, channels):
    for _ in range(5):
        try:
            return models.Buildid.get_versions(products, channels)
        except OperationalError:
            time.sleep(0.1)

    raise Exception('Not able to get all the versions from the DB')


def init_platforms(signatures, channels, products):
    return {p: {c: {s: {} for s in signatures} for c in channels} for p in products}


def get_for_urls_sgns(hg_urls, signatures, extra={}):
    chan_rev = utils.get_channel_revision(hg_urls)
    towait, pushdates = dc.get_pushdates(chan_rev)
    if towait:
        towait = [towait]
    else:
        towait = []

    data = {}
    versions = {}
    res = {'data': data, 'versions': versions}

    if not signatures:
        return res
    if utils.is_java(signatures):
        products = ['FennecAndroid']
    else:
        products = config.get_products()

    dates = {}
    channels = config.get_channels()
    all_versions = get_all_versions(products, channels)
    platforms = init_platforms(signatures, channels, products)
    sgns_data = dc.get_sgns_data(
        channels, all_versions, platforms, signatures, extra, products, towait
    )

    for product in products:
        all_versions_prod = all_versions[product]
        dates[product] = dates_prod = {}
        versions[product] = versions_prod = {}
        for chan in channels:
            # all_versions_pc is a list: [bid, version, unique, unique_prod] * N
            all_versions_pc = all_versions_prod[chan]
            dates_prod[chan] = [b[0] for b in all_versions_pc]
            versions_prod[chan] = {
                utils.get_buildid(b): ver for b, ver, _, _ in all_versions_pc
            }

    for tw in towait:
        tw.wait()
        tw.session.close()

    for chan, pds in pushdates.items():
        if pds:
            pushdates[chan] = max(pds)

    hasData = False
    for product, i in sgns_data.items():
        data[product] = data_prod = {}
        platforms_prod = platforms[product]
        dates_prod = dates[product]
        for chan, j in i.items():
            dates_pc = dates_prod[chan]
            if not dates_pc:
                continue

            platforms_pc = platforms_prod[chan]
            data_prod[chan] = data_pc = {}
            if product == 'FennecAndroid' and chan == 'nightly':
                pushdate = pushdates.get('esr68')
            else:
                pushdate = pushdates.get(chan)
            buildids = [utils.get_buildid(d) for d in dates_pc]
            position = utils.get_position(pushdate, dates_pc)
            min_date = min(dates_pc).strftime('%Y-%m-%d')
            for sgn, numbers in j.items():
                if isinstance(numbers, tuple):
                    continue

                hasData = True
                data_pc[sgn] = {
                    'position': position,
                    'buildids': buildids,
                    'min_date': min_date,
                    'raw': numbers[0],
                    'installs': numbers[1],
                    'startup': numbers[2],
                    'platforms': utils.percentage_platforms(platforms_pc[sgn]),
                }

    return res if hasData else {}


def get_affected(data, versions):
    affected = {}

    for prod, i in data.items():
        versions_prod = versions[prod]
        for chan, j in i.items():
            if chan not in affected:
                affected[chan] = set()
            versions_pc = versions_prod[chan]
            for k in j.values():
                non_zero = [n for n, e in enumerate(k['raw']) if e != 0]
                if non_zero:
                    vers = [versions_pc[k['buildids'][n]] for n in non_zero]
                    majors = set(utils.get_major(v) for v in vers)
                    affected[chan] |= majors

    affected = {c: list(sorted(v)) for c, v in affected.items()}
    return affected


def prepare_bug_for_html(data, extra={}):
    if not data:
        return {}, {}, False

    params = utils.get_params_for_link()
    has_extra = utils.update_params(params, extra)
    all_versions = data['versions']
    data = data['data']
    affected = get_affected(data, all_versions)

    for prod, i in data.items():
        params['product'] = prod
        all_versions_prod = all_versions[prod]
        for chan, j in i.items():
            all_versions_pc = all_versions_prod[chan]

            # we can have several time the same version for different builids
            # (e.g. in nightly) so we use a list(set(...))
            vers = list(sorted(set(all_versions_pc.values())))

            params['release_channel'] = ['beta', 'aurora'] if chan == 'beta' else chan
            for sgn, info in j.items():
                buildids = info['buildids']
                if not buildids:
                    continue

                params['date'] = '>=' + info['min_date']
                params['version'] = vers
                params['signature'] = '=' + sgn
                info['socorro_url'] = (
                    socorro.SuperSearch.get_link(params) + '#facet-build_id'
                )
                info['buildid_links'] = links = []
                info['versions'] = versions = []

                pos = info['position']
                if pos == -2:
                    info['buildid_classes'] = ['no-info bu ildid'] * len(buildids)
                    info['buildid_tooltip'] = buildids
                else:
                    info['buildid_classes'] = ['without'] * (pos + 1) + ['with'] * (
                        len(buildids) - pos
                    )
                    tooltips = ['Without Patch, '] * (pos + 1) + ['With Patch, '] * (
                        len(buildids) - pos
                    )
                    info['buildid_tooltip'] = [prefix + bid for prefix, bid in zip(tooltips, buildids)]

                for bid in buildids:
                    params['build_id'] = '=' + bid
                    v = all_versions_pc[bid]
                    versions.append(v)
                    if chan == 'release' and 'rc' in v:
                        # Special case for release rc: it's released in the beta channel
                        params['version'] = [v]
                        params['release_channel'] = ['beta']
                        links.append(
                            socorro.SuperSearch.get_link(params) + '#crash-reports'
                        )
                        params['release_channel'] = 'release'
                    else:
                        params['version'] = v
                        links.append(
                            socorro.SuperSearch.get_link(params) + '#crash-reports'
                        )

                del params['build_id']

    # order the data
    results = OrderedDict()
    for prod in config.get_products():
        if prod not in data:
            continue
        results[prod] = d = OrderedDict()
        for chan in config.get_channels():
            if chan in data[prod]:
                d[chan] = OrderedDict(sorted(data[prod][chan].items()))

    return results, affected, has_extra
