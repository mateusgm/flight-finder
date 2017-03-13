# -*- coding: utf-8 -*-

import time
import calendar
import datetime as dt
import numpy as np
import pandas as pd
import skyscanner.skyscanner as skc
import yaml
import sys

from GeoBases import *
from collections import defaultdict
from operator import itemgetter

pd.set_option('display.width', 500)
pd.set_option('display.max_rows', 1000)


# helpers

def _add_days(date, days):
    return date + dt.timedelta(days=days)

geo = GeoBase(data='ori_por', verbose=False)
def _get_code(name):
    scr, id = geo.fuzzyFind(name, 'city_name_utf')[0]
    place   = geo.get( id )
    return place[ 'city_code' ]

def _api_query(**query):
    api = skc.FlightsCache(SETTINGS['api']['api_key'])
    kwargs = dict( SETTINGS['defautls'].items() + query.items() )
    return api.get_cheapest_quotes(**kwargs).parsed

def _get_dates():
    dates   = []
    current = _add_days(dt.datetime.today(), CRITERIA['days_begin'])
    ending  = _add_days(dt.datetime.today(), CRITERIA['days_end'])
    while current < ending:
        if calendar.day_name[ current.weekday() ] in CRITERIA['flying_day']:
            for l in CRITERIA['length']:
                dates += [ (current.strftime('%Y-%m-%d'), _add_days(current, l-1).strftime('%Y-%m-%d') ) ]
        current = _add_days(current, 1)
    return dates

def _get_places():
    destinations = []
    for _from in CRITERIA[ 'place_from' ]:
        _from = _get_code(_from)
        for _to in CRITERIA[ 'place_to' ]:
            _to = _get_code(_to)
            destinations += [ (_from, _to ) ]
    return destinations

def _get_best_quote(d, p, only_direct=False):
    results = _api_query( originplace=p[0], destinationplace=p[1], outbounddate=d[0], inbounddate=d[1])
    best = { 'MinPrice': None }
    for q in results['Quotes']:
        if only_direct and not q['Direct']: continue
        if best['MinPrice'] is None or q['MinPrice'] < best['MinPrice']: best = q
    if SETTINGS['api']['verbose']: print "{} > {}: {}".format(p[0], p[1], best['MinPrice'])
    return best


# execution

with open('config.yml') as f:
    SETTINGS = yaml.safe_load(f)
    CRITERIA = SETTINGS[ sys.argv[1] ]

dates  = _get_dates()
places = _get_places()
print "%d destinations x %d days" % (len(places), len(dates)) 

prices = pd.DataFrame(
    index=range(len(dates)),
    columns=[ 'Takeoff', 'Return' ] + CRITERIA['place_to'] )

for i,d in enumerate(dates):
    quotes = [ _get_best_quote(d, p, only_direct=CRITERIA['direct']) for p in places ]
    prices.ix[i] = [ d[0], d[1] ] + [ q['MinPrice'] for q in quotes ]

    if (i+1) % 10 == 0: print "%d combinations" % ((i+1) * len(places))
    time.sleep( float(SETTINGS['api']['limit_per_minute']) / len(places))

print prices

