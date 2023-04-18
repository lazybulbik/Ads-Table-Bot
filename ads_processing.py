import database
from geopy.distance import geodesic


def find_ads(user_id, category):
    user = database.get_data(user_id, 'users')[0]
    user_coord = tuple(user[4].split(', '))
    ads = database.get_data(table='ads')
    radius = int(user[5])

    result = []

    for ad in ads:
        ad_coord = tuple(ad[11].split(', '))
        distance = geodesic(ad_coord, user_coord).m

        if category == ad[10] and distance <= radius and user[0] != ad[12]:
            result.append(ad[0])

    return result