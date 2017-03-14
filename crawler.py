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
from operator import attrgetter

pd.set_option('display.width', 500)
pd.set_option('display.max_rows', 1000)


# helpers

def _add_days(date, days):
    return date + dt.timedelta(days=days)

geo = GeoBase(data='ori_por', verbose=False)
def _get_place(name):
    ids  = geo.fuzzyFind(name, 'city_name_utf')
    objs = [ geo.get(i) for _, i in ids if geo.get(i)['fcode'] == 'AIRP' ]
    return objs[0]

def _api_live_query(**query):
    api = skc.Flights(SETTINGS['api']['api_key'])
    kwargs  = dict( SETTINGS['defaults'].items() + query.items() )
    results = api.get_result(**kwargs).parsed
    prices  = [  r['PricingOptions'][0] for r in results['Itineraries'] ]
    return prices

def _api_cache_query(**query):
    api = skc.FlightsCache(SETTINGS['api']['api_key'])
    kwargs  = dict( SETTINGS['defaults'].items() + query.items() )
    results = api.get_cheapest_quotes(**kwargs).parsed
    if query['stops'] == 0: results = [ r for r in results if r['Direct'] ]
    results = sorted(results, key=attrgetter('MinPrice'))
    return results

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
        _from_iata = _get_place(_from)['iata_code']
        for _to in CRITERIA[ 'place_to' ]:
            _to_iata = _get_place(_to)['iata_code']
            print "IATA:", _to, _to_iata
            destinations += [ (_from_iata, _to_iata ) ]
    return destinations

def _get_best_price(d, p, only_direct=False, live=True):
    params = dict(originplace=p[0], destinationplace=p[1], outbounddate=d[0], 
            inbounddate=d[1], locationschema='Iata', adults=2, stops=0)
    if live:
        results = _api_live_query(**params)
        best    = results[0]['Price']
    else:
        results = _api_cache_query(**params) 
        best    = results[0]['MinPrice']

    return best


# execution

with open('config.yml') as f:
    SETTINGS = yaml.safe_load(f)
    CRITERIA = SETTINGS[ sys.argv[1] ]

dates  = _get_dates()
places = _get_places()
print "%d destinations x %d days" % (len(places), len(dates)) 

grid = pd.DataFrame(
    index=range(len(dates)),
    columns=[ 'Takeoff', 'Return' ] + CRITERIA['place_to'] )

for i,d in enumerate(dates):
    prices = [ _get_best_price(d, p, only_direct=CRITERIA['direct']) for p in places ]
    grid.ix[i] = [ d[0], d[1] ] + prices

    if (i+1) % 5 == 0: print "%d combinations" % ((i+1) * len(places))
    # time.sleep( float(SETTINGS['api']['limit_per_minute']) / len(places))

print grid

