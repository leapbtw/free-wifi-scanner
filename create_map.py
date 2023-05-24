import folium
from folium.plugins import BeautifyIcon
import csv
import sys
import subprocess
import math
from geopy import distance

def main(csv_path):
    # array[] of the coordinates traveled 
    route_coordinates = parse_coords(csv_path)
    # Create a map centered around the first coordinate
    map_center = [route_coordinates[0][0], route_coordinates[0][1]]
    m = folium.Map(location=map_center, zoom_start=13)
    
    # a 'waypoint' is a point on the map with a minimum distance of 15m from the last one    
    waypoints = create_waypoints(route_coordinates)

    # Add the polyline representing the route
    folium.PolyLine(locations=waypoints, color='red').add_to(m)
    
    # drawing a circle that represents the area where a free network is available
    circles = geolocate_networks(csv_path)
    for c in circles:
        # c[0] is the name of the network
        # c[1] is an array of coordinates (the center point of the circle)
        # c[2] is the radius (in meters?) of the circle
        
        # drawing the circle itself
        circle_center = [c[1][0], c[1][1]]  
        circle_radius = c[2]
        circle = folium.Circle(
            location=circle_center,
            radius=circle_radius,
            color='blue',
            fill_color='#ADD8E6',
            fill_opacity=0.4,
        )
        circle.add_to(m)
        m.fit_bounds(circle.get_bounds())
        
        # writing the name of the free network inside of the circle
        folium.Marker(
            location=circle_center,
            icon=folium.DivIcon(
                icon_size=(150,36),
                icon_anchor=(75,18),
                html=f'<div style="font-weight:bold; font-size:16px; text-align:center;">{c[0]}</div>',
            )
        ).add_to(m)
       

    # Save the map as an HTML file
    m.save('cartina.html')




def geolocate_networks(filename):
    '''
        Parsing data related to circles
        From the <file>.csv, we parse unique network names
        We then collect all the coordinate points in which the network is available
            and we try to find the 'middle' point, which should be roughly where
            the access point is located. This will be the center of our circle
        Lastly, we find the radius by calculating the distance between the center
            and the outer point in which the network is available
    '''
    unique_network_names = []
    result = []
    
    # finding unique network names
    with open(filename, mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            # row[0] are coordinates, row[1] are network names
            unique_network_names.append(row[1])
        unique_network_names = list(set(unique_network_names))           # lists do not contain duplicates 
        unique_network_names.remove("NO_FREE_NETWORKS_FOUND")       # this is just a placeholder, needs to be ignored
        unique_network_names = [x for x in  unique_network_names]   # list to array
    
    # collecting points in which a network is available, and doing the math
    for net in unique_network_names:
        points_where_net_is_availavle = []
        with open(filename, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                # from the csv, collecting only data related to 'net'
                if row[1] == net:
                    # vaules = [coord1, coord2]
                    values = [float(coord) for coord in row[0].split(',')]
                    points_where_net_is_availavle.append(values)
        # doing the math
        circle_arr = create_circle(points_where_net_is_availavle)
        # [[network_name, [center_coord1, center_coord2], radius], ... ]
        result.append([net, circle_arr[0], circle_arr[1]]) 
    return result
        
def parse_coords(filename):
    # parsing all the coordinates
    with open(filename, mode='r') as file:
        reader = csv.reader(file)
        result = []
        for row in reader:
            coordinates = row[0].split(',')
            values = [float(coord) for coord in coordinates]
            result.append(values)
        return result

def create_waypoints(list_of_coords):
    '''
        to avoid creating many points of the line stacked upon each other, 
        we check that they've got a minimum distance of 15m between each other
    '''
    result = []
    result.append(list_of_coords[0])
    last_waypoint = list_of_coords[0]
    for coord in list_of_coords:
        if distance_between_2_points(last_waypoint, coord) > 15:
            result.append(coord)
            last_waypoint = coord
    return result

def distance_between_2_points(coord1, coord2):
    lat1 = coord1[0]
    lon1 = coord1[1]
    lat2 = coord2[0]
    lon2 = coord2[1]

    earth_radius = 6378.137 # Radius of earth in KM
    dLat = lat2 * math.pi / 180 - lat1 * math.pi / 180
    dLon = lon2 * math.pi / 180 - lon1 * math.pi / 180
    a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(lat1 * math.pi / 180) * math.cos(lat2 * math.pi / 180) * math.sin(dLon/2) * math.sin(dLon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a));
    d = earth_radius * c;
    return d * 1000;

def create_circle(points):
    # Calculate centroid
    centroid_x = sum(point[0] for point in points) / len(points)
    centroid_y = sum(point[1] for point in points) / len(points)
    centroid = (centroid_x, centroid_y)

    distances = [distance.distance(centroid, point).meters for point in points]
    radius = max(distances)
    if radius < 10:
        radius = 10
    # Return center and radius of the circle
    return centroid, radius

if __name__ == "__main__": 
    if len(sys.argv) < 2:
        print("Usage: python main.py <file path.csv>")
        exit(1)
    
    try:
        output = subprocess.check_output(["file", sys.argv[1]], universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing 'file' command: {e}")
        exit(1)
    
    if not output.__contains__("CSV"):
        print(f"Only CSV file accepted.")
        exit(1)

    main(sys.argv[1])

