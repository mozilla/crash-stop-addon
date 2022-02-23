# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import pytz
import six
from sqlalchemy import inspect
from . import config
from . import db, app


CHANNEL_TYPE = db.Enum(*config.get_channels(), name='CHANNEL_TYPE')
PRODUCT_TYPE = db.Enum(*config.get_products(), name='PRODUCT_TYPE')


class Buildid(db.Model):
    __tablename__ = 'buildid'

    product = db.Column(PRODUCT_TYPE, primary_key=True)
    channel = db.Column(CHANNEL_TYPE, primary_key=True)
    buildid = db.Column(db.DateTime(timezone=True), primary_key=True)
    version = db.Column(db.String(64))
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
    def add_buildids(data):
        if not data:
            return

        qs = db.session.query(Buildid)
        qs.delete()

        for prod, i in data.items():
            for chan, j in i.items():
                for b, v, u, up in j:
                    db.session.add(Buildid(prod, chan, b, v, u, up))

        db.session.commit()

    @staticmethod
    def get_versions(products, channels):
        if isinstance(products, six.string_types):
            products = [products]
        if isinstance(channels, six.string_types):
            channels = [channels]

        res = {p: {c: [] for c in channels} for p in products}
        bids = (
            db.session.query(Buildid)
            .filter(Buildid.product.in_(products), Buildid.channel.in_(channels))
            .order_by(Buildid.buildid.asc())
        )
        for bid in bids:
            d = res[bid.product][bid.channel]
            buildid = bid.buildid.astimezone(pytz.utc)
            d.append([buildid, bid.version, bid.unique, bid.unique_prod])

        return res


def clear():
    db.session.close()
    db.drop_all()
    db.session.commit()


def create():
    engine = db.get_engine(app)
    if not inspect(engine).has_table(engine, 'buildid'):
        db.create_all()
