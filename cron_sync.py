import os
import requests
import hashlib
import json  # Importado para fazer um print bonito do JSON se necessário
from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError  # Importado para apanhar o erro específico do Supabase

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
    failed_items_count = 0

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

        # Check if this virtual ID already exists in our raw database table
        existing = supabase.table("strava_raw_feed").select("id_virtual").eq("id_virtual", id_virtual).execute()
        
        if len(existing.data) > 0:
            print(f"Reached previously synced data at activity: '{titulo}'. Stopping execution loop safely.")
            break

        # It's unique! Prepare the entire raw JSON payload into our table
        payload = {
            "id_virtual": id_virtual,
            "raw_json": act 
        }
        
        # 🔍 ENVELOPE DE AUDITORIA: Tenta inserir e isola o erro caso aconteça
        try:
            supabase.table("strava_raw_feed").insert(payload).execute()
            new_items_count += 1
            print(f"Successfully saved raw data for new activity: '{titulo}'")
            
        except APIError as db_err:
            failed_items_count += 1
            print("\n" + "="*60)
            print("🚨 ERRO DETETADO AO INSERIR REGISTO NO SUPABASE!")
            print(f"Mensagem do Erro: {db_err.message}")
            print(f"Código do Erro: {db_err.code}")
            print("-"*60)
            print("📊 DADOS DA ATIVIDADE EM CAUSA:")
            print(f"  Atleta:       {firstname} {lastname}")
            print(f"  Título:       {titulo}")
            print(f"  id_virtual:   {id_virtual}")
            print(f"  distance:     {act.get('distance')} metros")
            print(f"  moving_time:  {act.get('moving_time')} segundos")
            print(f"  elapsed_time: {act.get('elapsed_time')} segundos")
            print(f"  device_name:  {act.get('device_name')}")
            print("="*60 + "\n")
            # continue  -> Salta para a próxima atividade sem mandar o script abaixo
            continue
            
        except Exception as general_err:
            failed_items_count += 1
            print(f"Erro inesperado no Python: {general_err}")
            continue

    print(f"Sync complete. Added {new_items_count} brand new activities. Falharam {failed_items_count} devido a erros.")

if __name__ == "__main__":
    sync_club_feed()
