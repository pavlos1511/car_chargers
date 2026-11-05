import webbrowser
import requests  # You must install this: pip install requests
import sys

# Configuration
API_URL = "http://localhost:9876/api"

def get_station_coordinates(point_id):
    """
    Connects to your Docker API (Part 4) to find a specific charging point.
    """
    url = f"{API_URL}/point/{point_id}"
    
    try:
        print(f"[-] Searching for Station ID: {point_id} in database...")
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            # The API returns 'lat' and 'lon' as strings
            return {
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "name": data.get("provider_name", "Unknown Provider")
            }
        elif response.status_code == 404:
            print("x Error: Station not found in database.")
            return None
        else:
            print(f"x Error: API returned status {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("x Error: Could not connect to Docker. Is 'docker-compose up' running?")
        return None

def open_google_maps(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Constructs the Google Maps URL and opens the default browser.
    """
    base_url = "https://www.google.com/maps/dir/?api=1"
    
    # Construct the query parameters
    # origin: Your location (Point A)
    # destination: The Station location (Point B)
    query = f"{base_url}&origin={origin_lat},{origin_lon}&destination={dest_lat},{dest_lon}&travelmode=driving"
    
    print(f"[-] Opening Google Maps...")
    print(f"[-] URL: {query}")
    
    # Opens the URL in a new tab of the default browser
    webbrowser.open(query)

if __name__ == "__main__":
    print("==========================================")
    print("   EV CHARGING NAVIGATION (CLIENT APP)    ")
    print("==========================================")

    # 1. Get User Location (Point A)
    # Defaulting to Athens Syntagma for easier testing if you hit Enter
    print("\n--- Step 1: Your Location (Point A) ---")
    my_lat = input("Enter Latitude [default 37.9755]: ").strip() or "37.9755"
    my_lon = input("Enter Longitude [default 23.7348]: ").strip() or "23.7348"

    # 2. Get Destination ID (Point B)
    print("\n--- Step 2: Destination Station ---")
    station_id = input("Enter Station ID (e.g., '1' or 'point123'): ").strip()

    if station_id:
        # 3. Fetch details from Docker API
        station_data = get_station_coordinates(station_id)

        if station_data:
            print(f"\n[+] Found Station: {station_data['name']}")
            print(f"[+] Coordinates: {station_data['lat']}, {station_data['lon']}")
            
            # 4. Launch Browser
            open_google_maps(my_lat, my_lon, station_data['lat'], station_data['lon'])
    else:
        print("x Error: You must enter a Station ID.")