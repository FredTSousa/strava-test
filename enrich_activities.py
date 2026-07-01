import os
import re
import random
import time
from dotenv import load_dotenv
from supabase import create_client, Client
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
    # (not JSON, not a separate API call) in these two <script> blocks.
    set_match = re.search(r"pageView\.activity\(\)\.set\(\{(.*?)\}\);", html, re.S)
    if not set_match:
        return None
    block = set_match.group(1)

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

    if distance is None or elev_gain is None or moving_time is None:
        return None

    title = text("title", lightbox)
    firstname = text("athlete_firstname", lightbox)
    full_name = text("athlete_name", lightbox)
    lastname = full_name[len(firstname):].strip() if firstname and full_name and full_name.startswith(firstname) else full_name

    return {
        "distance": distance,
        "elev_gain": elev_gain,
        "moving_time": int(moving_time),
        "title": title,
        "firstname": firstname,
        "lastname": lastname,
    }


def enrich_pending_activities():
    print(f"Looking for up to {BATCH_SIZE} not-yet-enriched activities...")

    res = supabase.table("strava_raw_feed") \
        .select("id_virtual, raw_json") \
        .eq("enriched", False) \
        .gte("raw_json->>start_date", MIN_START_DATE) \
        .limit(BATCH_SIZE) \
        .execute()

    rows = res.data or []
    if not rows:
        print("Nothing to enrich.")
        return

    cookie = get_current_cookie()
    session = build_session(cookie)

    enriched_count = 0
    skipped_count = 0

    for i, row in enumerate(rows):
        id_virtual = row["id_virtual"]
        raw_json = row.get("raw_json") or {}
        activity_id = raw_json.get("activity_id")

        if not activity_id:
            print(f"  [SKIP] {id_virtual} has no activity_id stored, marking enriched to avoid retrying forever.")
            supabase.table("strava_raw_feed").update({"enriched": True}).eq("id_virtual", id_virtual).execute()
            skipped_count += 1
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
            print(f"  Request failed for activity {activity_id}: {req_err}")
            skipped_count += 1
            continue

        if response.status_code in (301, 302):
            print("  Redirected (cookie likely expired). Stopping this run.")
            break

        if response.status_code != 200:
            print(f"  Unexpected status {response.status_code} for activity {activity_id}. Skipping.")
            skipped_count += 1
            continue

        detail = extract_activity_detail(response.text)
        if not detail:
            print(f"  Could not parse activity {activity_id} (may be private/group/removed). Marking enriched to avoid retrying forever.")
            supabase.table("strava_raw_feed").update({"enriched": True}).eq("id_virtual", id_virtual).execute()
            skipped_count += 1
            continue

        existing_athlete = raw_json.get("athlete") or {}
        merged_raw_json = dict(raw_json)
        merged_raw_json.update({
            "name": detail["title"] or merged_raw_json.get("name"),
            "distance": detail["distance"],
            "moving_time": detail["moving_time"],
            "total_elevation_gain": detail["elev_gain"],
            "athlete": {
                "firstname": detail["firstname"] or existing_athlete.get("firstname"),
                "lastname": detail["lastname"] or existing_athlete.get("lastname"),
            },
        })

        supabase.table("strava_raw_feed").update({
            "raw_json": merged_raw_json,
            "enriched": True,
        }).eq("id_virtual", id_virtual).execute()

        print(f"  [ENRICHED] {id_virtual} -> elev_gain={detail['elev_gain']}m")
        enriched_count += 1

        novo_cookie_cookies = session.cookies.get_dict()
        if novo_cookie_cookies.get("_strava4_session"):
            novo_cookie = f"_strava4_session={novo_cookie_cookies['_strava4_session']};"
            if novo_cookie != cookie:
                update_cookie_in_supabase(novo_cookie)
                cookie = novo_cookie

    print(f"Done. Enriched: {enriched_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    enrich_pending_activities()
