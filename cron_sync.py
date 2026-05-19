import os
import requests
import hashlib
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
INITIAL_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_valid_access_token():
    """Uses the refresh token to get a live, short-lived access token."""
    print("Refreshing Strava Access Token...")
    url = "https://www.strava.com/api/v3/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": INITIAL_REFRESH_TOKEN
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        data = res.json()
        # In a production app, you'd save the *new* refresh token back to your env/db if it rotates
        return data.get("access_token")
    else:
        raise Exception(f"Failed to refresh token: {res.text}")

def sync_club_feed():
    try:
        access_token = get_valid_access_token()
    except Exception as e:
        print(e)
        return

    url = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": 200} # Get a safe chunk of recent activities

    print("Fetching club feed from Strava...")
    res = requests.get(url, headers=headers, params=params)
    
    if res.status_code != 200:
        print(f"Strava API Error: {res.status_code}")
        return

    activities = res.json()
    new_items_count = 0

    for act in activities:
        # Build the virtual fingerprint
        atleta = f"{act.get('athlete', {}).get('firstname', '')}_{act.get('athlete', {}).get('lastname', '')}"
        titulo = act.get('name', '')
        distancia = str(act.get('distance', 0))
        tempo = str(act.get('moving_time', 0))
        elevacao = str(act.get('total_elevation_gain', 0))
        
        string_unica = f"{atleta}_{titulo}_{distancia}_{tempo}_{elevacao}"
        id_virtual = hashlib.md5(string_unica.encode('utf-8')).hexdigest()

        # Check if this virtual ID already exists in our raw database table
        existing = supabase.table("strava_raw_feed").select("id_virtual").eq("id_virtual", id_virtual).execute()
        
        if len(existing.data) > 0:
            # We hit an item we already saved last time.
            # Because the feed is strictly ordered by time, everything after this is old news.
            print("Reached previously synced data. Stopping execution loop safely.")
            continue

        # It's unique! Save the entire raw JSON payload into our table
        payload = {
            "id_virtual": id_virtual,
            "raw_json": act 
        }
        
        supabase.table("strava_raw_feed").insert(payload).execute()
        new_items_count += 1
        print(f"Successfully saved raw data for new activity: '{titulo}'")

    print(f"Sync complete. Added {new_items_count} brand new activities to 'strava_raw_feed'.")

if __name__ == "__main__":
    sync_club_feed()
