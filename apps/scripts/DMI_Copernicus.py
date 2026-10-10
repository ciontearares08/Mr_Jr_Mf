import requests
import os
import json  # NEW: Added json import for saving the DMI data
from datetime import datetime, timezone, timedelta
from requests.auth import AuthBase

# 1. Custom Auth Handler (Fixes Redirect 401s)
class BearerAuth(AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = "Bearer " + self.token
        return r

# 2. DMI API: Fetching Weather Data (Open)
def fetch_dmi_weather(bbox, param="temp_dry"):
    url = "https://opendataapi.dmi.dk/v2/metObs/collections/observation/items"
    
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=1)
    time_str = f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    params = {
        "bbox": bbox, 
        "parameterId": param,
        "datetime": time_str,
        "limit": 1
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"DMI Error: {response.status_code}\n{response.text}")
        return None

# 3. Copernicus API: Authentication & Metadata
def get_copernicus_token(username, password):
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password"
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Auth Error: {response.status_code}\n{response.text}")
        return None

def fetch_copernicus_metadata(bbox):
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    polygon = f"POLYGON(({bbox[0]} {bbox[1]}, {bbox[2]} {bbox[1]}, {bbox[2]} {bbox[3]}, {bbox[0]} {bbox[3]}, {bbox[0]} {bbox[1]}))"
    
    filters = (
        "Collection/Name eq 'SENTINEL-2' and "
        "contains(Name,'MSIL2A') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')"
    )
    
    params = {
        "$filter": filters,
        "$top": 1, 
        "$orderby": "ContentDate/Start desc"
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

# 4. Copernicus API: Downloading the Image
def download_copernicus_scene(download_url, token, data_dir, filename="sentinel_scene.zip"):
    print(f"Starting download of {filename} (This may take a while...)")
    
    # Construct the full path where the file will be saved
    filepath = os.path.join(data_dir, filename)
    
    # Use auth=BearerAuth(token) instead of passing headers manually
    with requests.get(download_url, auth=BearerAuth(token), stream=True) as response:
        response.raise_for_status()
        with open(filepath, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
    
    print(f"\nDownload complete: {filepath}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Copenhagen Bounding Box
    cph_bbox_dmi = "12.4,55.6,12.7,55.8"
    cph_bbox_cop = [12.4, 55.6, 12.7, 55.8]
    
    # --- 1. GET DMI WEATHER ---
    print("\n--- Fetching Open DMI Weather ---")
    temp_data = fetch_dmi_weather(cph_bbox_dmi, "temp_dry")
    if temp_data and 'features' in temp_data and temp_data['features']:
        latest_temp = temp_data['features'][0]['properties']
        print(f"Current Temp: {latest_temp['value']}°C at {latest_temp['observed']}")
        
        dmi_filepath = os.path.join(data_dir, "dmi_weather.json")
        with open(dmi_filepath, "w") as file:
            json.dump(temp_data, file, indent=4)
        print(f"DMI data saved to: {dmi_filepath}")
    
    # --- 2. GET SATELLITE METADATA ---
    print("\n--- Fetching Sentinel-2 Metadata ---")
    scenes = fetch_copernicus_metadata(cph_bbox_cop)
    if scenes and 'value' in scenes and scenes['value']:
        latest_scene = scenes['value'][0]
        scene_id = latest_scene['Id']
        scene_name = latest_scene['Name']
        
        download_url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({scene_id})/$value"
        
        print(f"Found latest scene: {scene_name}")
        
        # --- 3. AUTHENTICATE & DOWNLOAD --- 
        # Please use environment variables for this in the future!
        USERNAME = "EMAIL" 
        PASSWORD = "PASSWORD" 
        
        print("\nAuthenticating with Copernicus...")
        token = get_copernicus_token(USERNAME, PASSWORD)
        
        if token:
            download_copernicus_scene(download_url, token, data_dir, f"{scene_name}.zip")
        else:
            print("Failed to get token. Check your credentials.")