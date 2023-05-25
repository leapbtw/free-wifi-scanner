import sys
import os
import subprocess
import requests
from datetime import datetime
import json
import csv
import signal
import math

def main(wireless_interface):
    # getting the date to create a unique file
    now = datetime.now()
    complete_array = []                             # array that gets printed to the CSV file
    printed_networks = ["NO_FREE_NETWORKS_FOUND"]   # not to be printed (again), check create_map.py
    
    # running until CTRL + C
    try:
        while True:
            try:
                should_print = True                     # this is so i can print every network we find ONLY 1 time
                wifis = get_nearby_wifis()              # get nearby wifi networks
                pos = get_pos(wireless_interface)       # get current position coordinates of the device using Google's APIs
                
                for w in wifis:
                    for already_printed in printed_networks:        # check if we already printed that we've found this network
                        if w == already_printed:
                            should_print = False
                    if should_print:
                        printed_networks.append(w)
                        print("New free network found: " + w)
                    
                    new_wifi = [pos, w]
                    complete_array.append(new_wifi)                # appending new found wifi to the array that gets written to the CSV
            except Exception as e:
                print(wireless_interface + " seems busy, or something... ignoring it. If you see this message often, there might be a problem with it.")
                pass
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Exiting...")
    
    if complete_array != []:
        nome_file = now.strftime("%d-%m-%Y+%H:%M:%S") + ".csv"
        os.system('touch ' + nome_file)
        write_array_to_csv(complete_array, nome_file)               # when CTRL + C, writing the CSV to the current directory

def get_wireless_interface():
    result = subprocess.run(['iw', 'dev'], capture_output=True, text=True)
    if result.returncode == 0:
        output_lines = result.stdout.splitlines()
    
        # parsing the output of 'iw dev' and looking for a wireless interface
        wireless_interface = None
        for line in output_lines:
            if 'Interface' in line:
                wireless_interface = line.split()[-1]
                break
    
        if wireless_interface:
            print("Wireless interface found:", wireless_interface)
            return wireless_interface
        else:
            print("No wireless interface found. Maybe try providing one with -i <wireless-interface>")
            exit(1)
    else:
        print("Error executing 'iw dev'. Is 'iw' installed? command:", result.stderr)
        exit(1)
    
def check_wireless_interface_exists(interface_name):
    # like get_wireless_interface(), but checking if said wireless interface exists or not
    output = subprocess.check_output(['iw', 'dev'], universal_newlines=True)
    lines = output.split('\n')
    for line in lines:
        if line.strip().startswith('Interface'):
            line_parts = line.split(' ')
            existing_interface_name = line_parts[1]
            if existing_interface_name == interface_name:
                return True
    return False

def get_pos(interface):
    # get an API key from https://console.cloud.google.com/marketplace/product/google/geolocation.googleapis.com (you can use free trial)
    with open(".api.txt", "r") as file:
        api_key = file.read().strip()

    # getting nearby wifi network names: needs sudo, will ask for password
    try:
        iw_output = subprocess.check_output(["sudo", "iw", "dev", interface, "scan"], universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing 'iw', is 'iw' installed? command: {e}")
        exit(1)

    # Step 3: Parse the output to extract Wi-Fi network information
    networks = []
    current_network = {}
    for line in iw_output.split("\n"):
        line = line.strip()
        if line.startswith("BSS"):
            if current_network:
                networks.append(current_network)
                current_network = {}
            current_network["bssid"] = line.split(" ")[1]
        elif line.startswith("SSID"):                       # TODO: sometimes crashes here (no clue why)
            current_network["ssid"] = line.split(": ")[1]
        elif line.startswith("signal"):
            signal_strength = line.split(": ")[1].split(" dBm")[0]
            current_network["signal_strength"] = float(signal_strength)

    # Add the last network after loop completion
    if current_network:
        networks.append(current_network)

    # Step 4: Prepare payload for Geolocation API request
    wifi_access_points = []
    for network in networks:
        if "bssid" in network and "signal_strength" in network:
            wifi_access_points.append({
                "macAddress": network["bssid"],
                "signalStrength": network["signal_strength"]
            })

    payload = {
        "considerIp": "true",
        "wifiAccessPoints": wifi_access_points
    }

    # Step 5: Send request to Geolocation API
    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={api_key}"
    response = requests.post(url, json=payload)
    response_data = json.loads(response.text)

    latitude = response_data["location"]["lat"]
    longitude = response_data["location"]["lng"]
    accuracy = response_data["accuracy"]            # not doing anything with this, but might be useful so leaving it here
    # print(f"lat: {latitude}\tlong: {longitude}\taccuracy: {accuracy}m")
    return(f"{latitude},{longitude}")
   
def get_nearby_wifis():
    # will output nearby wifi networks
    try:
        iw_output = subprocess.check_output(["nmcli", "dev", "wifi", "list"], universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing 'iw' command: {e}")
        exit(1)
    
    output = []  
    for line in iw_output.split("\n"):
        line = line.strip()
        if line.__contains__("--"):         # 'nmcli dev wifi list' will write '--' when there's no WEP/WPA security on a network, we're looking for this
            if (line.startswith("*")):
                output.append(line[27:line.find("Infra")].strip())
            else:
                output.append(line[19:line.find("Infra")].strip())
    
    # dumb workaround, otherwise won't be printed in CSV
    # could have left it like
    #   45.123,10.123, <empty>
    # but it would probably be a problem when parsing it in create_map.py
    if output == []:
        output.append("NO_FREE_NETWORKS_FOUND")
    return(output)

def write_array_to_csv(array, filename):
    print(f"Writing to file " + filename + " ...")
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(array)
        for row in array:
            writer.writerow([row[0], row[1]])

    # workaround, otherwise will print whole array in first row for some reason. Deleting first row
    with open(filename, 'r') as file2:
        lines = file2.readlines()
        new_lines = lines[1:]
    with open(filename, 'w') as file3:
        file3.writelines(new_lines)

if __name__ == "__main__": 
    if len(sys.argv) < 3:
        print(f"No wireless interface provided. Trying to find one automatically...")
        main(get_wireless_interface())     
    elif sys.argv[1] == "-i":
        if check_wireless_interface_exists(sys.argv[2]):
            print(f"Using interface " + sys.argv[2])
            main(sys.argv[2])
        else:
            print(f"Interface " + sys.argv[2] + " not found with 'iw'.")
