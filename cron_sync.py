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
# 🟢 Nunca sincronizar atividades anteriores a esta data, independentemente do watermark.
MIN_START_DATE = os.getenv("CRON_SYNC_MIN_START_DATE", "2026-06-30")

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
    res = requests.post(url, data=payload, timeout=30)
    if res.status_code == 200:
        return res.json().get("access_token")
    else:
        raise Exception(f"Failed to refresh token: {res.text}")

def get_last_synced_activity_id():
    res = supabase.table("system_config").select("value").eq("key", "cron_sync_last_activity_id").execute()
    if res.data:
        return int(res.data[0]["value"])
    return 0


def set_last_synced_activity_id(activity_id):
    supabase.table("system_config").upsert({"key": "cron_sync_last_activity_id", "value": str(activity_id)}).execute()


def sync_club_feed():
    # 🟢 Fonte trocada da API oficial (bloqueada pela Strava) para a tabela
    # 'atividades_clube', já alimentada pelo crawler (strava_keep_alive.py).
    # Usa um watermark de activity_id para não reprocessar a tabela toda em cada run
    # (senão fica cada vez mais lento à medida que atividades_clube cresce).
    new_items_count = 0
    duplicate_items_count = 0
    failed_items_count = 0

    last_synced_id = get_last_synced_activity_id()
    max_activity_id_seen = last_synced_id

    print(f"Starting sync of club feed from atividades_clube (activity_id > {last_synced_id}) into strava_raw_feed...")

    page_size = 500
    offset = 0

    while True:
        res = supabase.table("atividades_clube") \
            .select("*") \
            .gt("activity_id", last_synced_id) \
            .gte("start_date", MIN_START_DATE) \
            .order("activity_id") \
            .range(offset, offset + page_size - 1) \
            .execute()
        rows = res.data or []

        if not rows:
            print("No new activities since last sync.")
            break

        print(f"Processing {len(rows)} new activities from atividades_clube (offset {offset})...")

        for row in rows:
            # Build the virtual fingerprint
            firstname = row.get('first_name') or ''
            athlete_name = row.get('athlete_name') or ''
            lastname = athlete_name[len(firstname):].strip() if firstname and athlete_name.startswith(firstname) else athlete_name
            atleta = f"{firstname}_{lastname}"
            titulo = row.get('activity_name') or ''
            # Crawler stores distance in km and doesn't expose elevation gain, unlike the official API.
            distancia = str((row.get('distance') or 0) * 1000)
            tempo = str(row.get('elapsed_time') or 0)
            elevacao = "0"

            string_unica = f"{atleta}_{titulo}_{distancia}_{tempo}_{elevacao}"
            id_virtual = hashlib.md5(string_unica.encode('utf-8')).hexdigest()

            activity_id = row.get('activity_id')
            if activity_id and activity_id > max_activity_id_seen:
                max_activity_id_seen = activity_id

            payload = {
                "id_virtual": id_virtual,
                "raw_json": {
                    "activity_id": row.get('activity_id'),
                    "name": titulo,
                    "distance": float(distancia),
                    "moving_time": row.get('elapsed_time') or 0,
                    "elapsed_time": row.get('elapsed_time') or 0,
                    "total_elevation_gain": 0,
                    "start_date": row.get('start_date'),
                    "device_name": row.get('device_name'),
                    "athlete": {"firstname": firstname, "lastname": lastname},
                },
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

        if len(rows) < page_size:
            print("Reached the end of atividades_clube.")
            break

        offset += page_size

    if max_activity_id_seen > last_synced_id:
        try:
            set_last_synced_activity_id(max_activity_id_seen)
            print(f"Watermark advanced to activity_id {max_activity_id_seen}.")
        except Exception as watermark_err:
            # Não deixar uma falha ao gravar o watermark derrubar o run inteiro:
            # as atividades já foram guardadas em strava_raw_feed nesta altura.
            print(f"⚠️ Warning: failed to persist watermark: {watermark_err}")

    print("\n" + "═"*40)
    print("🏁 SYNC PROCESS COMPLETE")
    print(f"   📥 Total New Saved: {new_items_count}")
    print(f"   🔄 Total Duplicates Skipped: {duplicate_items_count}")
    print(f"   ❌ Total Failed Errors: {failed_items_count}")
    print("═"*40)

if __name__ == "__main__":
    sync_club_feed()
