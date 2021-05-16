from datetime import datetime, timedelta
from math import sin, cos, sqrt, atan2, radians
import argparse
import concurrent.futures

import requests

# Script Parameters
parser = argparse.ArgumentParser(description='Scan for Covid-19 vaccination appointments - Quebec')
parser.add_argument('-p', '--postal_code', type=str, required=True, help='Your postal code.')
parser.add_argument('-d', '--in_the_next', type=int, required=True, help='Look for appointments in the next X days.')
parser.add_argument('-m', '--max_distance', type=int, required=True,
					help='Look for appointments within X km of postal code.')

# Global Variables
api_url = 'https://api3.clicsante.ca/v3/'
required_headers = {
	'product': 'clicsante',
	'authorization': 'Basic cHVibGljQHRyaW1vei5jb206MTIzNDU2Nzgh',
	'x-trimoz-role': 'public'
}


def calc_distance(coord1, coord2):
	# Calculate distance between two coordinates

	lat1 = radians(coord1['latitude'])
	lon1 = radians(coord1['longitude'])
	lat2 = radians(coord2['latitude'])
	lon2 = radians(coord2['longitude'])

	dlon = lon2 - lon1
	dlat = lat2 - lat1

	a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
	c = 2 * atan2(sqrt(a), sqrt(1 - a))

	return 6373.0 * c


def get_user_location(postal_code):
	# Retrieve user latitude and longitude from postal code
	r = requests.get(api_url + 'geocode', params={'address': postal_code}, headers=required_headers)

	assert r.status_code == 200, "Received invalid response for get_user_location"

	lat_lng = r.json()['results'][0]['geometry']['location']

	return {'postal_code': postal_code, 'latitude' : lat_lng['lat'], 'longitude': lat_lng['lng']}


def get_service_id(establishment_id):
	# Retrieve the service id for a given establishment

	r = requests.get(api_url + f'establishments/{establishment_id}/services', headers=required_headers)

	assert r.status_code == 200, "Can't retrieve service id"

	service_id = [s['id'] for s in r.json() if '1st' in s['name_en']]

	assert len(service_id) > 0, "Can't retrieve service id"

	return service_id[0]


def get_establishments(location_infos, start_date, end_date, max_distance):
	# Retrieve a list of all establishment within max_distance km

	places = []

	page_nb = 0
	# Query until we get a 204 (No more pages)
	while True:
		params = {
			'dateStart': start_date,
			'dateStop': end_date,
			'latitude': location_infos['latitude'],
			'longitude': location_infos['longitude'],
			'maxDistance': max_distance,
			'serviceUnified': 237,
			'postalCode': location_infos['postal_code'],
			'page': page_nb
		}

		r = requests.get(api_url + 'availabilities', params=params, headers=required_headers)

		if r.status_code == 204:
			# No more pages to retrieve
			break
		places += r.json()['places']
		page_nb += 1

	places_with_avail = []
	for place in places:
		availabilities = place['availabilities']['su237']
		if availabilities['t07'] > 0 or availabilities['ta7'] > 0 or True:
			place['distance'] = calc_distance(place, location_infos)
			places_with_avail.append(place)	

	sorted_places = sorted(places_with_avail, key=lambda x: x['distance'])

	return sorted_places


def get_times(day, establishment_id, service_id, place_id):
	# Retrieve the time slots for a given date in a given establishment

	current_date = datetime.strptime(day, '%Y-%m-%d')
	next_day = current_date + timedelta(days=1)
	params = {
		'dateStart': current_date.strftime('%Y-%m-%d'),
		'dateStop': next_day.strftime('%Y-%m-%d'),
		'service': service_id,
		'timezone': 'America/Toronto',			# This is broken, seems like the api return times in UTC
		'places': place_id,
		'filter1': 1,
		'filter2': 0
	}

	r = requests.get(api_url + f'establishments/{establishment_id}/schedules/day', params=params, headers=required_headers)

	time_slots = []
	if r.status_code == 200:
		for slot in r.json()['availabilities']:
			slot_datetime = datetime.strptime(slot['start'], '%Y-%m-%dT%H:%M:%S+00:00')

			# For some reason, the api return time in UTC timezone even if we specify america/toronto... let's substract 4h..
			slot_datetime = slot_datetime - timedelta(hours=4)

			time_slots.append(slot_datetime)

	return sorted(set(time_slots))


def get_availabilities(place, start_date, end_date, postal_code):
	# Retrieve available dates and time slots for a given establishment

	place_infos = {
		'name': place['name_en'],
		'distance': place['distance'],
		'url': f'https://clients3.clicsante.ca/{place["establishment"]}/take-appt?unifiedService=237&portalPlace={place["id"]}&portalPostalCode={postal_code.replace(" ", "%20")}',
		'availabilities': []
	}

	service_id = get_service_id(place['establishment'])
	params = {
		'dateStart': start_date,
		'dateStop': end_date,
		'service': service_id,
		'timezone': 'America/Toronto',
		'places': place['id'],
		'filter1': 1,
		'filter2': 0
	}

	r = requests.get(api_url + f'establishments/{place["establishment"]}/schedules/public', params=params, headers=required_headers)

	resp = r.json()

	if len(resp['availabilities']) > 0 or len(resp['upcomingAvailabilities']) > 0:
		for date in resp['availabilities']:
			available_time_slots = get_times(date, place['establishment'], service_id, place['id'])
			if len(available_time_slots) > 0:
				# Might happen that the spot get reserved
				# between the time we requested availabilities and the time we requested time slots..
				place_infos['availabilities'].append({
					'date': date,
					'time_slots': available_time_slots
				})

	return place_infos


def print_place_availabilities(place_infos):
	# Print availabilities

	nb_availabilities = 0
	if len(place_infos['availabilities']) > 0:

		print("---------------------------")
		print(place_infos['name'], f'  ---  {place_infos["distance"]:0.2f} km')
		print(place_infos['url'])

		for availability in place_infos['availabilities']:
			print("    ", availability['date'])
			for time_slot in availability['time_slots']:
				print("        ", time_slot.strftime("%H:%M"))
				nb_availabilities += 1

	return nb_availabilities


if __name__ == "__main__":
	args = parser.parse_args()
	if ' ' not in args.postal_code:
		args.postal_code = f'{args.postal_code[:3]} {args.postal_code[3:]}'

	args.postal_code = args.postal_code.upper()

	if len(args.postal_code) != 7:
		print(f"[ERROR] Invalid postal code {args.postal_code}")
		exit(1)

	current_date = datetime.today()
	end_date = current_date + timedelta(days=args.in_the_next)
	current_date = current_date.strftime('%Y-%m-%d')
	end_date = end_date.strftime('%Y-%m-%d')

	print(f"Looking for available appointments in the next {args.in_the_next} days (up to {end_date})")
	print(f"Within {args.max_distance} km of postal code {args.postal_code}")

	location_infos = get_user_location(args.postal_code)
	places = get_establishments(location_infos, current_date, end_date, args.max_distance)

	print(f"Querying {len(places)} vaccination center... This might take a little while...")

	processed_places = []

	# Launch requests in ThreadPool
	with concurrent.futures.ThreadPoolExecutor() as executor:
		futures = []

		for place in places:
			futures.append(executor.submit(get_availabilities, place, current_date, end_date, args.postal_code))

		for future in concurrent.futures.as_completed(futures):
			processed_places.append(future.result())

	# Print results
	nb_availabilities = 0
	for processed_place in sorted(processed_places, key=lambda x: x['distance']):
		nb_availabilities += print_place_availabilities(processed_place)

	if nb_availabilities == 0:
		print("\nWe didn't find any availabilities with the specified criteria, try again later, places open frequently")
	else:
		print(f"\n\nWe found {nb_availabilities} availabilities !")
		print("Click on the provided link and fill up the forms quickly before these places get taken...")
		print("Thanks to the Quebec government for not implementing a good reservation system...")

