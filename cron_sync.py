import os
import requests
import hashlib
from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError

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
        return res.json().get("access_token")
    else:
        raise Exception(f"Failed to refresh token: {res.text}")

def sync_club_feed():
    try:
        access_token = get_valid_access_token()
    except Exception as e:
        print(e)
        return

    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 🔄 VARIÁVEIS DE PAGINAÇÃO
    page = 1
    per_page = 100  # 100 é o limite recomendado por página pelo Strava para estabilidade
    
    new_items_count = 0
    duplicate_items_count = 0
    failed_items_count = 0

    print("Starting deep sync of club feed from Strava...")

    while True:
        url = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities"
        params = {"page": page, "per_page": per_page}
        
        print(f"📡 Fetching page {page}...")
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code != 200:
            print(f"Strava API Error on page {page}: {res.status_code}")
            break

        activities = res.json()
        
        # 🏁 CONDIÇÃO DE PARAGEM DA API: Se a página vier vazia, terminámos o feed!
        if not activities or len(activities) == 0:
            print("Reached the end of the Strava club feed.")
            break

        print(f"Processing {len(activities)} activities from page {page}...")

        for act in activities:
            # Build the virtual fingerprint
            firstname = act.get('athlete', {}).get('firstname', '')
            lastname = act.get('athlete', {}).get('lastname', '')
            atleta = f"{firstname}_{lastname}"
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
            
            # 🚀 TENTATIVA DIRETA DE INSERÇÃO
            try:
                supabase.table("strava_raw_feed").insert(payload).execute()
                new_items_count += 1
                print(f"  [NEW] Saved: '{titulo}' ({firstname})")
                
            except APIError as db_err:
                # Se o erro for 23505 (Chave Duplicada), ignoramos em silêncio e CONTINUAMOS o loop!
                if db_err.code == "23505":
                    duplicate_items_count += 1
                    continue
                
                # Qualquer outro erro real (ex: crash de triggers, etc.) entra aqui para auditoria
                failed_items_count += 1
                print("\n" + "="*60)
                print("🚨 ERRO DETETADO NO POSTGRESQL!")
                print(f"  Mensagem: {db_err.message}")
                print(f"  Código:   {db_err.code}")
                print(f"  Atividade: '{titulo}' de {firstname}")
                print("="*60 + "\n")
                continue
                
            except Exception as general_err:
                failed_items_count += 1
                print(f"Unexpected Python Error: {general_err}")
                continue

        # Avança para a página seguinte do Strava
        page += 1

    print("\n" + "═"*40)
    print("🏁 SYNC PROCESS COMPLETE")
    print(f"   📥 Total New Saved: {new_items_count}")
    print(f"   🔄 Total Duplicates Skipped: {duplicate_items_count}")
    print(f"   ❌ Total Failed Errors: {failed_items_count}")
    print("═"*40)

if __name__ == "__main__":
    sync_club_feed()
