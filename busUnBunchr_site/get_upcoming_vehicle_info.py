# General
import datetime

# web input parsing
import json
from urllib2 import urlopen
from pyquery import PyQuery as pq

# Math and data analysis
from math import radians, cos, sin, asin, sqrt
from scipy import stats
import pandas as pd
import numpy as np

from get_frequency_for_route import get_frequency_for_route


# Grab json from Google Maps API
def get_googlemaps_json(start_loc, end_loc):
    print 'in get_googlemaps_json start_loc is '+str(start_loc)
    print 'in get_googlemaps_json end_loc is '+str(end_loc)
    my_googlemaps_auth = 'AIzaSyDWQv6WWQptI-6rjbavkoZ1TpVZhHKOm4w'
    googlemaps_url = 'https://maps.googleapis.com/maps/api/directions/json?origin='+str(start_loc).replace(' ','+')+'&destination='+str(end_loc).replace(' ','+')+'&mode=transit&key='+str(my_googlemaps_auth)
    print googlemaps_url
    tmp = urlopen(googlemaps_url)
    return json.load(tmp)



# Compute distance between two (lat,lon)s in meters
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    meters = 6367 * c * 1000
    return meters

# Compute the percentile score of two (lat,lon)s based upon distribution of distances for that route
def compute_distance(route_num, lat1, lon1, lat2, lon2):
        tmp_dist = haversine(lat1,lon1,lat2,lon2)
        return tmp_dist
		# comment out if you only want dist
        #path_to_dist_distribution = '../muni_route_distance_distributions/route_'+str(route_num)+'_distribution.npy'
        #route_dist_distribution = np.load(path_to_dist_distribution)
        #percentile_score = 1 - stats.percentileofscore(route_dist_distribution, tmp_dist)/100
        #return percentile_score




######################################################################
# Main function to get next two buses' data and return a dataframe entry with that information
# BREAK THIS FUNCTION UP TO HANDLE ALL THE EXCEPTIONS IT CAN THROW
# BUT DO THAT ONCE EVERYTHING ELSE IS WORKING
######################################################################
def subsequent_bus_info(starting_loc, ending_loc):
	data = get_googlemaps_json(starting_loc, ending_loc)
	'''Returns a dataframe that is a pair of subsequent buses
	   and their distance percentile score
	'''

	# Get route name, (lat,lon), and stop name from Google maps
	# For now this only gets the first transit option
	# To look at the other transit options, you can iterate over the 'legs' key 
	# (or maybe 'routes, figure that out)
	# Do that last
	try:
		steps = data['routes'][0]['legs'][0]['steps']
#		steps
	except:
		df_empty = pd.DataFrame()
		print 'steps was none!'
		return df_empty
	for i, step in enumerate(steps):
		if step['travel_mode'] == 'TRANSIT':
			transit_step = i
			break
	 
	try:
		route_name = str(steps[transit_step]['transit_details']['line']['short_name'])
		departure_stop = str(steps[transit_step]['transit_details']['departure_stop']['name'])
		departure_lat = round(float(steps[transit_step]['transit_details']['departure_stop']['location']['lat']),5)
		departure_lon = round(float(steps[transit_step]['transit_details']['departure_stop']['location']['lng']),5)
		vehicle_type = str(steps[transit_step]['transit_details']['line']['vehicle']['type'])
	except:
		df_empty = pd.DataFrame()
		print 'variables not properly read from steps[transit_step]! Perhaps non-Muni route, or a route google doesn\'t know is running?'
		return df_empty


	# Get stopID from Nextbus 'routeConfig'
	url_get_route_config='http://webservices.nextbus.com/service/publicXMLFeed?command=routeConfig&a=sf-muni&r='+str(route_name)
	route_config = pq(urlopen(url_get_route_config).read())	
	
	for bus_stop_obj in route_config('stop'):
		bus_stop = pq(bus_stop_obj)
		if bus_stop.attr('lat') is not None:
			stop_name = str(bus_stop.attr('title'))
			stop_lat = round(float(bus_stop.attr('lat')),5)
			stop_lon = round(float(bus_stop.attr('lon')),5)
			# Matching on name is not robust because Google will occasionally return different names from NextBus
			# So match only on coordinates
			if stop_lat == departure_lat and stop_lon == departure_lon:
				stop_id = str(bus_stop.attr('stopId'))
				# get full stop name too, useful for UI
				stop_full_name = stop_name

	# do a check that stop_id was actually captured
	#if stop_id is None:
	try:
		stop_id
	except:
		df_empty = pd.DataFrame()
		return df_empty

	# Get next two vehicle from Nextbus 'predictions'	
	url_get_stop_info='http://webservices.nextbus.com/service/publicXMLFeed?command=predictions&a=sf-muni&stopId='+stop_id+'&r='+str(route_name)
	print 'Getting predictions for: '+url_get_stop_info
	stop_config = pq(urlopen(url_get_stop_info).read())
	
	vehicle_array = []
	arrival_time_array = []
	for prediction in stop_config('prediction'):
	    vehicle_array.append(pq(prediction).attr.vehicle)
	    arrival_time_array.append(pq(prediction).attr.minutes)
	
	try:
		vehicle_1 = vehicle_array[0]
	except:
		print 'vehicle_1 not located'
		df_empty = pd.DataFrame()
		return df_empty
	try:
		vehicle_2 = vehicle_array[1]
	except:
		print 'vehicle_2 not located'
		df_empty = pd.DataFrame()
		return df_empty
	try:
		arrival_time_1 = arrival_time_array[0]
	except:
		print 'arrival_time_1 not located'
		df_empty = pd.DataFrame()
		return df_empty
	try:
		arrival_time_2 = arrival_time_array[1]
	except:
		print 'arrival_time_2 not located'
		df_empty = pd.DataFrame()
		return df_empty

	# Get both vehicles' information from Nextbus 'vehicleLocations'
	url_get_realtime_info='http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=sf-muni&r='+str(route_name)+'&t=0'
	realtime_posits = pq(urlopen(url_get_realtime_info).read())

	time_stamp = datetime.datetime.utcfromtimestamp(int(pq(pq(realtime_posits('vehicle')[-1]).siblings()[-1]).attr('time'))/1000)
	for vehicle in realtime_posits('vehicle'):
		v = pq(vehicle)
		if v.attr.id == vehicle_1:
			df1 = pd.DataFrame({'ind': 0,'time': time_stamp,'lat_x': float(v.attr.lat), \
					'lon_x': float(v.attr.lon), 'speed_x': float(v.attr.speedKmHr), \
					'route_x': str(v.attr.routeTag), 'stop_name': stop_full_name, \
					'vehicle_type': vehicle_type},index=[0])
		elif v.attr.id == vehicle_2:
			df2 = pd.DataFrame({'ind': 0,'lat_y': float(v.attr.lat), 'lon_y': float(v.attr.lon), 'speed_y': float(v.attr.speedKmHr)},index=[0])

	try:
		df1
	except:
		print 'first vehicle record not located'
		df_empty = pd.DataFrame()
		return df_empty
	try:
		df2
	except:
		print 'second vehicle record not located'
		df_empty = pd.DataFrame()
		return df_empty

	# Merge the dataframes and compute the distance percentile score for each bus
	bus_pair  = pd.merge(left=df1, right=df2)
	bus_pair['dist'] = compute_distance(route_name, float(bus_pair['lat_x'][0]), float(bus_pair['lon_x'][0]), float(bus_pair['lat_y'][0]), float(bus_pair['lon_y'][0]))	
	# if using dist_percentile
	#bus_pair['dist_percentile'] = compute_distance(route_name, float(bus_pair['lat_x'][0]), float(bus_pair['lon_x'][0]), float(bus_pair['lat_y'][0]), float(bus_pair['lon_y'][0]))	
	bus_pair['arrival_x'] = arrival_time_1
	bus_pair['arrival_y'] = arrival_time_2

	# one hot encode the columns

	# Now we need to get the frequency at this time for this route
	print 'route is ', bus_pair['route_x'][0]
	print 'time is ', bus_pair['time'][0]
	# include this only when running updated RF
	# Must subtract 8 hours from 'time', since that is actually UTC time
	bus_pair['freq'] = get_frequency_for_route(bus_pair['route_x'][0], bus_pair['time'][0] - pd.Timedelta(hours=8))


	# Necessary only for patsy
	#bus_pair['bunched'] = 0

	# Return the dataframe (do processing in bunch_predictor.py)
	return bus_pair
