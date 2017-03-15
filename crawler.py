# -*- coding: utf-8 -*-

import yaml
import sys
import time
import calendar

import datetime as dt
import numpy as np
import pandas as pd
import skyscanner.skyscanner as skc

from collections import defaultdict
from operator import itemgetter

pd.set_option('display.width', 500)
pd.set_option('display.max_rows', 1000)


# helpers

def _add_days(date, days):
    return date + dt.timedelta(days=days)


# api

def _query(module, method, params):
    api     = module(SETTINGS['api']['api_key'])
    kwargs  = dict( SETTINGS['defaults'].items() + params.items() )
    results = getattr(api, method)(**kwargs)
    return results.parsed

def api_get_place(name):
    results = _query(skc.Transport, 'location_autosuggest', { 'query': name })
    return results['Places'][0]['PlaceId']

def api_live_query(**query):
    time.sleep(3)
    results = _query(skc.Flights, 'get_result', query)
    if results is None: return []

    prices  = [  r['PricingOptions'][0] for r in results['Itineraries'] ]
    return prices

def api_cache_query(**query):
    results = _query(skc.FlightsCache, 'get_cheapest_quotes', query)
    if results is None: return []

    results = [ r for r in results['Quotes'] if query['stops'] > 0 or r['Direct'] ]
    results = sorted(results, key=itemgetter('MinPrice'))
    return results


# assembling the grid

def get_dates():
    dates   = []
    current = _add_days(dt.datetime.today(), CRITERIA['days_begin'])
    ending  = _add_days(dt.datetime.today(), CRITERIA['days_end'])
    while current < ending:
        if calendar.day_name[ current.weekday() ] in CRITERIA['flying_day']:
            for l in CRITERIA['length']:
                dates += [ (current.strftime('%Y-%m-%d'), _add_days(current, l-1).strftime('%Y-%m-%d') ) ]
        current = _add_days(current, 1)
    return dates

def get_places():
    destinations = []
    for _from in CRITERIA[ 'place_from' ]:
        _from_iata = api_get_place(_from)
        for _to in CRITERIA[ 'place_to' ]:
            _to_iata = api_get_place(_to)
            print "IATA:", _to, _to_iata
            destinations += [ (_from_iata, _to_iata ) ]
    return destinations

def get_best_price(d, p, only_direct=False):
    params = dict(originplace=p[0], destinationplace=p[1], outbounddate=d[0], inbounddate=d[1], locationschema='Sky', adults=2)
    if only_direct: params['stops'] = 0

    if SETTINGS['api']['live_api']:
        results = api_live_query(**params)
        param   = 'Price'
    else:
        results = api_cache_query(**params) 
        param   = 'MinPrice'

    if results:
        return results[0][param]

    return None


# execution

with open('config.yml') as f:
    SETTINGS = yaml.safe_load(f)
    CRITERIA = SETTINGS[ sys.argv[1] ]

dates  = get_dates()
places = get_places()
print "%d destinations x %d days" % (len(places), len(dates)) 

grid = pd.DataFrame(
    index=range(len(dates)),
    columns=[ 'Takeoff', 'Return' ] + CRITERIA['place_to'] )

for i,d in enumerate(dates):
    prices = [ get_best_price(d, p, only_direct=CRITERIA['direct']) for p in places ]
    grid.ix[i] = [ d[0], d[1] ] + prices

    if (i+1) % 5 == 0: print "%d combinations" % ((i+1) * len(places))

print grid

