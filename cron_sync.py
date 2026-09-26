import os
import requests
import hashlib
from datetime import datetime, timedelta, timezone
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

# 🟢 Quantos dias para trás se re-verifica atividades_clube em cada run.
LOOKBACK_DAYS = int(os.getenv("CRON_SYNC_LOOKBACK_DAYS", "30"))


def get_synced_activity_ids(cutoff: str) -> set:
    """activity_ids que já estão em strava_raw_feed a partir de 'cutoff' (inclusive)."""
    synced = set()
    page_size = 1000
    offset = 0
    while True:
        res = supabase.table("strava_raw_feed") \
            .select("id_virtual, activity_id:raw_json->>activity_id") \
            .gte("raw_json->>start_date", cutoff) \
            .order("id_virtual") \
            .range(offset, offset + page_size - 1) \
            .execute()
        rows = res.data or []
        synced.update(int(r["activity_id"]) for r in rows if r.get("activity_id"))
        if len(rows) < page_size:
            break
        offset += page_size
    return synced


def sync_club_feed():
    # 🟢 Fonte trocada da API oficial (bloqueada pela Strava) para a tabela
    # 'atividades_clube', já alimentada pelo crawler (strava_keep_alive.py).
    # 🟢 Antes usava um watermark de activity_id (só processava activity_id > máximo já visto),
    # mas as atividades NÃO chegam a atividades_clube por ordem de id: uma atividade que entra
    # no feed do clube horas depois de ser carregada (ex: visibilidade/título alterados mais tarde,
    # ou lote do crawler que falhou) já tinha o watermark à frente dela e era saltada para sempre.
    # Agora compara-se uma janela de LOOKBACK_DAYS com o que já existe em strava_raw_feed.
    new_items_count = 0
    duplicate_items_count = 0
    failed_items_count = 0

    lookback_start = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    cutoff = max(lookback_start, MIN_START_DATE)
    synced_ids = get_synced_activity_ids(cutoff)

    print(f"Starting sync of club feed from atividades_clube (start_date >= {cutoff}, {len(synced_ids)} already in strava_raw_feed) into strava_raw_feed...")

    page_size = 500
    offset = 0

    while True:
        res = supabase.table("atividades_clube") \
            .select("*") \
            .gte("start_date", cutoff) \
            .order("activity_id") \
            .range(offset, offset + page_size - 1) \
            .execute()
        page = res.data or []
        rows = [r for r in page if r.get("activity_id") not in synced_ids]

        if not page:
            break

        if rows:
            print(f"Processing {len(rows)} missing activities from atividades_clube (offset {offset})...")

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

        if len(page) < page_size:
            break

        offset += page_size

    print("\n" + "═"*40)
    print("🏁 SYNC PROCESS COMPLETE")
    print(f"   📥 Total New Saved: {new_items_count}")
    print(f"   🔄 Total Duplicates Skipped: {duplicate_items_count}")
    print(f"   ❌ Total Failed Errors: {failed_items_count}")
    print("═"*40)

if __name__ == "__main__":
    sync_club_feed()
