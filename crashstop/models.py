# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import defaultdict
import pytz
import six
from . import config
from . import db, app


CHANNEL_TYPE = db.Enum(*config.get_channels(), name='CHANNEL_TYPE')
PRODUCT_TYPE = db.Enum(*config.get_products(), name='PRODUCT_TYPE')


class Buildid(db.Model):
    __tablename__ = 'buildid'

    product = db.Column(PRODUCT_TYPE, primary_key=True)
    channel = db.Column(CHANNEL_TYPE, primary_key=True)
    buildid = db.Column(db.DateTime(timezone=True), primary_key=True)
    version = db.Column(db.String(12))
    unique = db.Column(db.Boolean)
    unique_prod = db.Column(db.Boolean)

    def __init__(self, product, channel, buildid, version, unique, unique_prod):
        self.product = product
        self.channel = channel
        self.buildid = buildid
        self.version = version
        self.unique = unique
        self.unique_prod = unique_prod

    @staticmethod
    def add_buildids(data, commit=True):
        if not data:
            return

        qs = db.session.query(Buildid)
        here = defaultdict(lambda: defaultdict(lambda: set()))
        for q in qs:
            here[q.product][q.channel].add(q.buildid)
        for prod, i in data.items():
            here_p = here[prod]
            for chan, j in i.items():
                here_pc = here_p[chan]
                for b, v, u, up in j:
                    if b not in here_pc:
                        db.session.add(Buildid(prod, chan, b, v, u, up))
                    else:
                        here_pc.remove(b)

                if here_pc:
                    q = db.session.query(Buildid)
                    q = q.filter(Buildid.product == prod,
                                 Buildid.channel == chan,
                                 Buildid.buildid.in_(list(here_pc)))
                    q.delete(synchronize_session='fetch')
        if commit:
            db.session.commit()

    @staticmethod
    def get_versions(products=config.get_products(),
                     channels=config.get_channels(),
                     unicity=False):
        if isinstance(products, six.string_types):
            products = [products]
        if isinstance(channels, six.string_types):
            channels = [channels]

        res = {p: {c: [] for c in channels} for p in products}
        bids = db.session.query(Buildid).filter(Buildid.product.in_(products),
                                                Buildid.channel.in_(channels)).order_by(Buildid.buildid.asc())
        for bid in bids:
            d = res[bid.product][bid.channel]
            buildid = bid.buildid.astimezone(pytz.utc)
            if unicity:
                d.append([buildid, bid.version, bid.unique, bid.unique_prod])
            else:
                d.append([buildid, bid.version])
        return res


def clear():
    db.drop_all()
    db.session.commit()


def create():
    engine = db.get_engine(app)
    if not engine.dialect.has_table(engine, 'buildid'):
        db.create_all()
