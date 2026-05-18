import os
import requests
import hashlib
import time
from dotenv import load_dotenv
from supabase import create_client, Client

# Load your local secrets from the .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_live_access_token():
    """Exchange the permanent refresh token for a live, short-lived access token."""
    print("🔄 Requesting short-lived Access Token from Strava...")
    url = "https://www.strava.com/api/v3/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        return res.json().get("access_token")
    else:
        raise Exception(f"Failed to authenticate with Strava: {res.text}")

def run_historical_backfill():
    try:
        access_token = get_live_access_token()
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        return

    url = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    page = 1
    per_page = 200 # Maximize batch sizes to respect API rate limits
    total_inserted_or_updated = 0

    print("\n🚀 Starting historical backfill loop. Scraping backward in time...")
    print("-----------------------------------------------------------------")

    while True:
        print(f"Fetching page {page} (Looking for up to 200 older activities)...")
        params = {"page": page, "per_page": per_page}
        
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code != 200:
            print(f"❌ Strava returned an error on page {page}: {res.status_code}")
            break

        activities = res.json()
        
        # If Strava returns an empty list, we have reached the end of available history!
        if not activities:
            print("\n🏁 Reached the end of Strava's available historical feed window.")
            break

        print(f"-> Found {len(activities)} entries on page {page}. Saving to Supabase...")
        
        for act in activities:
            # Generate the unique virtual MD5 fingerprint
            atleta = f"{act.get('athlete', {}).get('firstname', '')}_{act.get('athlete', {}).get('lastname', '')}"
            titulo = act.get('name', '')
            distancia = str(act.get('distance', 0))
            tempo = str(act.get('moving_time', 0))
            elevacao = str(act.get('total_elevation_gain', 0))
            
            string_unica = f"{atleta}_{titulo}_{distancia}_{tempo}_{elevacao}"
            id_virtual = hashlib.md5(string_unica.encode('utf-8')).hexdigest()

            payload = {
                "id_virtual": id_virtual,
                "raw_json": act
            }

            try:
                # Upsert updates the row if it exists, or creates it if it's brand new
                supabase.table("strava_raw_feed").upsert(payload).execute()
                total_inserted_or_updated += 1
            except Exception as e:
                print(f"⚠️ Failed to upsert activity '{titulo}': {e}")

        print(f"✅ Finished processing page {page}.\n")
        
        # Respect API Rate limits: pause for 1.5 seconds between page requests
        time.sleep(1.5)
        page += 1

    print("-----------------------------------------------------------------")
    print(f"🎉 Backfill Complete! Synchronized {total_inserted_or_updated} activities into Supabase.")

if __name__ == "__main__":
    run_historical_backfill()