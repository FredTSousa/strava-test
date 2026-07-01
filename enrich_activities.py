import os
import re
import random
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError
from curl_cffi import requests as curl_requests

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")
BATCH_SIZE = int(os.getenv("ENRICH_BATCH_SIZE", "20"))
# 🟢 No need to burn requests enriching the pre-crawler backlog; only activities from this date onward matter.
MIN_START_DATE = os.getenv("ENRICH_MIN_START_DATE", "2026-06-30")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_current_cookie() -> str:
    res = supabase.table("system_config").select("value").eq("key", "strava_cookie").execute()
    if res.data:
        return res.data[0]["value"]
    raise Exception("No 'strava_cookie' found in system_config table.")


def update_cookie_in_supabase(novo_cookie: str):
    supabase.table("system_config").upsert({"key": "strava_cookie", "value": novo_cookie}).execute()


def build_session(cookie: str):
    # 🟢 Cabeçalhos copiados de uma requisição real (Postman) para /activities/{id},
    # trocando apenas o cookie pelo guardado na DB. chrome146 é o perfil mais próximo
    # do Chrome 149 real disponível no curl_cffi instalado.
    session = curl_requests.Session(impersonate="chrome146")
    session.headers.update({
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "pt-PT,pt;q=0.9,en-PT;q=0.8,en-GB;q=0.7,en-US;q=0.6,en;q=0.5",
        "cache-control": "max-age=0",
        "priority": "u=0, i",
        "referer": f"https://www.strava.com/clubs/{CLUB_ID}/recent_activity?num_entries=60",
        "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Cookie": cookie,
    })
    return session


def extract_activity_detail(html: str):
    # 🟢 Strava embeds the real stats server-side as a plain JS object literal
    # (not JSON, not a separate API call). Some pages call pageView.activity().set(...)
    # more than once (e.g. a later no-op call with just adjusting_elevation/map_start_index),
    # so pick whichever match actually has the fields we need instead of just the first one.
    blocks = re.findall(r"pageView\.activity\(\)\.set\(\{(.*?)\}\);", html, re.S)
    # elev_gain is absent on trainer/indoor activities, so it can't be a required marker here.
    block = next((b for b in blocks if "distance:" in b and "moving_time:" in b), None)
    if not block:
        return None

    def num(key):
        m = re.search(rf"\b{key}:\s*([\d.]+)", block)
        return float(m.group(1)) if m else None

    lightbox_match = re.search(r"var lightboxData\s*=\s*\{(.*?)\}", html, re.S)
    lightbox = lightbox_match.group(1) if lightbox_match else ""

    def text(key, source):
        m = re.search(rf"{key}:\s*[\"']([^\"']*)[\"']", source)
        return m.group(1) if m else None

    distance = num("distance")
    elev_gain = num("elev_gain")
    moving_time = num("moving_time")

    if distance is None or moving_time is None:
        return None

    # 🟢 Strava omite elev_gain para atividades de trainer/indoor (não há elevação real).
    if elev_gain is None:
        elev_gain = 0.0

    title = text("title", lightbox)
    firstname = text("athlete_firstname", lightbox)
    full_name = text("athlete_name", lightbox)
    lastname = full_name[len(firstname):].strip() if firstname and full_name and full_name.startswith(firstname) else full_name

    # 🟢 O tipo de desporto (Run/Ride/etc.) só existe na página da atividade, nunca no feed do clube.
    sport_type_match = re.search(r"Strava\.Labs\.Activities\.Pages\.\w+PageView\(\d+,\s*'([^']+)'", html)
    sport_type = sport_type_match.group(1) if sport_type_match else None
    workout_type = int(num("workout_type")) if num("workout_type") is not None else None

    return {
        "distance": distance,
        "elev_gain": elev_gain,
        "moving_time": int(moving_time),
        "title": title,
        "firstname": firstname,
        "lastname": lastname,
        "sport_type": sport_type,
        "workout_type": workout_type,
    }


def get_processed_id_virtuals() -> set:
    # 🟢 strava_raw_feed é write-once (trigger de DB impede update/delete), por isso os
    # resultados do enriquecimento vivem numa tabela à parte, nunca no próprio raw_feed.
    processed = set()
    page_size = 1000
    offset = 0
    while True:
        res = supabase.table("strava_activity_enrichment") \
            .select("id_virtual") \
            .range(offset, offset + page_size - 1) \
            .execute()
        rows = res.data or []
        if not rows:
            break
        processed.update(r["id_virtual"] for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return processed


def fetch_candidates(processed_ids: set, batch_size: int):
    candidates = []
    page_size = 500
    offset = 0
    while len(candidates) < batch_size:
        res = supabase.table("strava_raw_feed") \
            .select("id_virtual, raw_json") \
            .gte("raw_json->>start_date", MIN_START_DATE) \
            .order("fetched_at") \
            .range(offset, offset + page_size - 1) \
            .execute()
        rows = res.data or []
        if not rows:
            break

        for row in rows:
            if row["id_virtual"] not in processed_ids:
                candidates.append(row)
                if len(candidates) >= batch_size:
                    break

        if len(rows) < page_size:
            break
        offset += page_size

    return candidates


def record_enrichment(id_virtual: str, status: str, detail=None):
    payload = {"id_virtual": id_virtual, "status": status}
    if detail:
        payload.update({
            "distance": detail["distance"],
            "moving_time": detail["moving_time"],
            "total_elevation_gain": detail["elev_gain"],
            "name": detail["title"],
            "athlete_firstname": detail["firstname"],
            "athlete_lastname": detail["lastname"],
            "sport_type": detail["sport_type"],
            "workout_type": detail["workout_type"],
        })

    try:
        supabase.table("strava_activity_enrichment").insert(payload).execute()
    except APIError as db_err:
        if db_err.code == "23505":
            # Já foi registado por outro run em paralelo -- nada a fazer.
            print(f"  {id_virtual} already recorded, skipping insert.")
            return
        raise


def enrich_pending_activities():
    # 🟢 Corre em lotes de BATCH_SIZE até esgotar tudo o que ainda não foi tentado
    # (ou até o cookie expirar), em vez de parar depois de um único lote.
    permanently_processed_ids = get_processed_id_virtuals()
    attempted_this_run = set()

    total_enriched = 0
    total_skipped = 0
    stop = False

    while not stop:
        exclude_ids = permanently_processed_ids | attempted_this_run
        rows = fetch_candidates(exclude_ids, BATCH_SIZE)

        if not rows:
            print("Nothing left to enrich.")
            break

        print(f"Processing a batch of {len(rows)} activities...")
        cookie = get_current_cookie()
        session = build_session(cookie)

        for i, row in enumerate(rows):
            id_virtual = row["id_virtual"]
            # Marca já como tentada nesta run, quer corra bem quer não --
            # evita reprocessar o mesmo item várias vezes na mesma run se ele falhar.
            attempted_this_run.add(id_virtual)

            raw_json = row.get("raw_json") or {}
            activity_id = raw_json.get("activity_id")

            if not activity_id:
                print(f"  [SKIP] {id_virtual} has no activity_id stored, recording as permanently unenrichable.")
                record_enrichment(id_virtual, "no_activity_id")
                permanently_processed_ids.add(id_virtual)
                total_skipped += 1
                continue

            if i > 0:
                delay = random.uniform(5, 7)
                print(f"  Waiting {delay:.1f}s before next visit...")
                time.sleep(delay)

            url = f"https://www.strava.com/activities/{activity_id}"
            print(f"  Visiting activity {activity_id}...")

            try:
                response = session.get(url, allow_redirects=False, timeout=30)
            except Exception as req_err:
                print(f"  Request failed for activity {activity_id}: {req_err} (will retry on a future run)")
                total_skipped += 1
                continue

            if response.status_code in (301, 302):
                print("  Redirected (cookie likely expired). Stopping.")
                stop = True
                break

            if response.status_code != 200:
                print(f"  Unexpected status {response.status_code} for activity {activity_id}. Skipping.")
                total_skipped += 1
                continue

            detail = extract_activity_detail(response.text)
            if not detail:
                print(f"  Could not parse activity {activity_id} (may be private/group/removed). Recording as unparseable.")
                record_enrichment(id_virtual, "unparseable")
                permanently_processed_ids.add(id_virtual)
                total_skipped += 1
                continue

            record_enrichment(id_virtual, "enriched", detail)
            permanently_processed_ids.add(id_virtual)

            print(f"  [ENRICHED] {id_virtual} -> elev_gain={detail['elev_gain']}m")
            total_enriched += 1

            novo_cookie_cookies = session.cookies.get_dict()
            if novo_cookie_cookies.get("_strava4_session"):
                novo_cookie = f"_strava4_session={novo_cookie_cookies['_strava4_session']};"
                if novo_cookie != cookie:
                    update_cookie_in_supabase(novo_cookie)
                    cookie = novo_cookie

    print(f"Done. Enriched: {total_enriched}, Skipped: {total_skipped}")


if __name__ == "__main__":
    enrich_pending_activities()
