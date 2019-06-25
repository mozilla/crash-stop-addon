# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import datetime
from dateutil.relativedelta import relativedelta
import functools
from libmozdata import hgmozilla, socorro, utils as lmdutils
from libmozdata.connection import Query
from . import config, utils


def get_useful_bids(buildhub_bids, socorro_bids):
    """Get the useful nightly buildids.
       The strategy is the following:
         - keep the last builds (even if the volume is pretty low)
         - remove the builds with a low volume of crashes
           (they're erroneous or have been respined)
    """
    res = []
    N = len(buildhub_bids)
    n = -1

    # first we keep the last elements: it doesn't matter
    # if they have not enough crashes since at the beginning
    # a build has almost no crashes.
    for n in range(N - 1, -1, -1):
        x = buildhub_bids[n]
        res.append(x)
        # once we've a "true" build we can break...
        if x[0] in socorro_bids:
            break

    # ... and this time add only "true" builds.
    for i in range(n - 1, -1, -1):
        x = buildhub_bids[i]
        if x[0] in socorro_bids:
            res.append(x)

    return res[::-1]


def filter_by_crashes_num(channel, json, data):
    """Keep the builds with a volume of crashes gt a threshold.
    """
    if not json['facets']['product']:
        return
    for facets in json['facets']['product']:
        prod = facets['term']
        data_prod = data[prod]
        threshold = config.get_min_total(prod, channel)
        for facet in facets['facets']['build_id']:
            # keep only the builds where crashes # is gt threshold
            if facet['count'] >= threshold:
                bid = str(facet['term'])
                data_prod.add(bid)


def get_filter_query(fa_bids, fx_bids, channel):
    min_bid = fa_bids[0][0] if fa_bids else '30000101000000'
    min_bid = min(min_bid, fx_bids[0][0]) if fx_bids else min_bid
    date = max(
        utils.get_build_date(min_bid),
        lmdutils.get_date_ymd('today') - relativedelta(days=364),
    )
    date = date.strftime('%Y-%m-%d')
    if channel == 'beta':
        channel = ['beta', 'aurora']

    return {
        'product': ['FennecAndroid', 'Firefox'],
        'date': '>=' + date,
        'build_id': '>=' + min_bid,
        'release_channel': channel,
        '_aggs.product': 'build_id',
        '_results_number': 0,
        '_facets': 'release_channel',
        '_facets_size': 1000,
    }


def filter_buildids_helper(fa_bids, fx_bids, channel):
    """Filter the builds to keep only the relevant ones.
    """
    data = {'Firefox': set(), 'FennecAndroid': set()}
    params = get_filter_query(fa_bids, fx_bids, channel)
    socorro.SuperSearch(
        params=params,
        handler=functools.partial(filter_by_crashes_num, channel),
        handlerdata=data,
    ).wait()

    fa_bids = get_useful_bids(fa_bids, data['FennecAndroid'])
    fx_bids = get_useful_bids(fx_bids, data['Firefox'])

    return fa_bids, fx_bids


def filter_buildids(buildids, channel):
    """Filter the builds to keep only the relevant ones.
    """
    fa_bids = buildids['FennecAndroid'][channel]
    fx_bids = buildids['Firefox'][channel]

    fa_bids, fx_bids = filter_buildids_helper(fa_bids, fx_bids, channel)

    buildids['FennecAndroid'][channel] = fa_bids
    buildids['Firefox'][channel] = fx_bids


def get_data_for_stats(data, sgn):
    """Init a data structure to collect stats.
    """
    nums = data[sgn]
    if isinstance(nums, tuple):
        nums = nums[0]
        L = len(nums)
        raw = [0] * L
        installs = [0] * L
        startup = [0] * L

        data[sgn] = [raw, installs, startup, nums]

        return raw, installs, startup, nums

    return nums[0], nums[1], nums[2], nums[3]


def filter_signatures_data(limit, product, platforms, sgn, bids_chan, json, data):
    """Collect the stats from the json got from Socorro.
    """
    if not json['facets']['build_id']:
        return

    data_prod = data[product]
    platforms_prod = platforms[product]

    for facets in json['facets']['build_id']:
        rawbid = facets['term']
        bid = utils.get_build_date(rawbid)
        chan = bids_chan[bid]
        dpc = data_prod[chan]
        raw, installs, startup, index = get_data_for_stats(dpc, sgn)
        if bid in index:
            n = index[bid]
            raw[n] = facets['count']
            facets = facets['facets']
            N = len(facets['install_time'])
            installs[n] = (
                max(limit, facets['cardinality_install_time']['value'])
                if N == limit
                else N
            )
            startup[n] = utils.startup_crash_rate(facets['startup_crash'])
            utils.analyze_platforms(
                platforms_prod[chan][sgn], facets['platform_pretty_version']
            )


def get_sgns_data_helper(
    data, platforms, signatures, bids_chan, extra, search_date, product, channel=None
):
    """Get the data from Socorro and collect the stats.
    """
    limit = 80
    base_params = {
        'build_id': [utils.get_buildid(bid) for bid in bids_chan.keys()],
        'date': search_date,
        'product': product,
        '_aggs.build_id': [
            'install_time',
            '_cardinality.install_time',
            'startup_crash',
            'platform_pretty_version',
        ],
        '_results_number': 0,
        '_facets': 'signature',
        '_facets_size': limit,
    }

    if channel:
        base_params['release_channel'] = (
            ['beta', 'aurora'] if channel == 'beta' else channel
        )

    utils.update_params(base_params, extra)
    queries = []

    for signature in signatures:
        params = base_params.copy()
        params['signature'] = '=' + signature
        hdler = functools.partial(
            filter_signatures_data, limit, product, platforms, signature, bids_chan
        )
        queries.append(
            Query(
                socorro.SuperSearch.URL, params=params, handler=hdler, handlerdata=data
            )
        )

    return socorro.SuperSearch(queries=queries)


def get_sgns_data_structure(signatures, products, channels, allbids):
    """Get the base data structure to collect stats.
    """
    data = {}

    for prod in products:
        data[prod] = data_prod = {}
        allbids_prod = allbids[prod]
        for chan in channels:
            allbids_pc = allbids_prod[chan]
            # each signature is mapped with a list of buildids
            # if there is some data for this signature (cf socorro handler)
            # then the list will be replaced by a dict to receive the numbers
            data_prod[chan] = {sgn: (allbids_pc,) for sgn in signatures}

    return data


def get_unicity_stuff(versions):
    """Sort the buildids.
    """
    allbids = {}
    unique = {}
    leftovers = []
    min_buildid = lmdutils.get_date_ymd('today')

    for prod, i in versions.items():
        allbids[prod] = allbids_prod = {}
        unique[prod] = unique_prod = {}
        for chan, j in i.items():
            allbids_prod[chan] = allbids_pc = []
            for bid, version, u, u_prod in j:
                if bid < min_buildid:
                    min_buildid = bid
                allbids_pc.append(bid)
                if u or u_prod:
                    unique_prod[bid] = chan
                else:
                    fake_chan = chan
                    if 'rc' in version:
                        # release rc are delivered in beta channel
                        fake_chan = 'beta'
                    leftovers.append([bid, prod, chan, fake_chan])

    # bids are sorted (because of models.get_versions)
    # so map bids on their index
    for prod, i in allbids.items():
        for chan, j in i.items():
            i[chan] = {bid: k for k, bid in enumerate(j)}

    return min_buildid, allbids, unique, leftovers


def get_sgns_data(channels, versions, platforms, signatures, extra, products, towait):
    """Get the crash stats from Socorro for the given signatures.
    """
    min_buildid, allbids, unique, leftovers = get_unicity_stuff(versions)
    search_date = socorro.SuperSearch.get_search_date(min_buildid)
    data = get_sgns_data_structure(signatures, products, channels, allbids)

    # if a buildid is unique then it's unique for its product too.
    # So we've only 2xN queries (2 == len(['Firefox', 'FennecAndroid']))
    for prod, bids in unique.items():
        towait.append(
            get_sgns_data_helper(
                data, platforms, signatures, bids, extra, search_date, prod
            )
        )

    # handle the leftovers: normally they should be pretty rare
    # we've them when they're not unique within the same product (e.g. a nightly and a beta have the same buildid)
    for bid, prod, chan, fake in leftovers:
        towait.append(
            get_sgns_data_helper(
                data,
                platforms,
                signatures,
                {bid: chan},
                extra,
                search_date,
                prod,
                channel=fake,
            )
        )

    return data


def get_pushdate(json, data):
    """Get the pushdate from the json if the patch has not been backed out.
    """
    if not json.get('backedoutby', False):
        pushdate = json['pushdate'][0]
        pushdate = lmdutils.as_utc(datetime.utcfromtimestamp(pushdate))
        data.append(pushdate)


def get_pushdates(chan_rev):
    """Get the pushdates of the given channel/revision.
    """
    res = []
    data = {}

    for chan, revs in chan_rev.items():
        if chan.startswith('esr'):
            if 'esr' not in data:
                data['esr'] = pd = []
            else:
                pd = data['esr']
        else:
            data[chan] = pd = []

        for rev in revs:
            res.append(
                hgmozilla.Revision(
                    channel=chan,
                    params={'node': rev},
                    handler=get_pushdate,
                    handlerdata=pd,
                )
            )

    return res, data
