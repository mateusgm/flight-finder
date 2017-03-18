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
    time.sleep(SETTINGS['api']['live_sleep'])
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

def _get_flight_times(checkin, los, **flight_times):
    flight = dict(
        _ref=dict( los=los, in_period=flight_times['inbound'][0], out_period=flight_times['outbound'][0] ),
        outbounddate=checkin.strftime('%Y-%m-%d'), 
        inbounddate=_add_days(checkin, los).strftime('%Y-%m-%d'),
        adults=2 )

    for f in [ 'inbound', 'outbound' ]:
        for p in [ 'start', 'end' ]:
            if p in SETTINGS['defaults'][ flight_times[f] ]:
                flight["%sdepart%stime" % (f,p)] = SETTINGS['defaults'][ flight_times[f] ][p]

    return flight

def _generate_stays(checkin, loss, **flight_times):
    return [ _get_flight_times(checkin, l, **flight_times) for l in loss ]

def get_dates():
    dates   = []
    current = _add_days(dt.datetime.today(), CRITERIA['days_begin'])
    ending  = _add_days(dt.datetime.today(), CRITERIA['days_end'])
    while current < ending:
        previous = _add_days(current, -1)
        if calendar.day_name[ current.weekday() ] in CRITERIA['flying_day']:
            dates += _generate_stays( current,  CRITERIA['length'], outbound="morning", inbound="afternoon" )
            dates += _generate_stays( previous, CRITERIA['length'] + 1, outbound="evening", inbound="afternoon" )
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

def get_best_price(dates, places, only_direct=False):
    location = dict(originplace=places[0], destinationplace=places[1], locationschema='Sky')
    params   = dict(location.items() + dates.items())
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
    CRITERIA['length'] = np.array(CRITERIA['length'])

dates  = get_dates()
places = get_places()
print "%d destinations x %d days" % (len(places), len(dates)) 

grid = pd.DataFrame(
    index=range(len(dates)),
    columns=[ 'Takeoff', 'Return' ] + CRITERIA['place_to'] )

for i,d in enumerate(dates):
    prices = [ get_best_price(d, p, only_direct=CRITERIA['direct']) for p in places ]
    grid.ix[i] = [ "%s_%s" % ( d['outbounddate'], d['_ref']['in_period'] ), d['_ref']['los'] ] + prices
    print grid.ix[i]

    if (i+1) % 5 == 0: print "%d combinations" % ((i+1) * len(places))

print grid

