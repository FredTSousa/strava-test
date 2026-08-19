import os
import re
import time
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client
from curl_cffi import requests

load_dotenv()

# Config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

# 🟢 One-off catch-up for the 2026-08-17 keep-alive outage. Walks back further
# than strava_keep_alive.py's normal 4-page reach until the feed cursor crosses
# this date (with margin before the last known-good run at 09:30 UTC), or until
# Strava says there are no more pages. Safe to re-run: everything is upserted.
BACKFILL_UNTIL_DATE = os.getenv("BACKFILL_UNTIL_DATE", "2026-08-17T00:00:00+00:00")
MAX_PAGES = int(os.getenv("BACKFILL_MAX_PAGES", "300"))  # safety cap so a bad cutoff can't loop forever

if not SUPABASE_URL or not SUPABASE_KEY or not CLUB_ID:
    raise Exception("❌ Faltam variáveis de ambiente essenciais (Supabase ou Strava ID).")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_current_cookie() -> str:
    res = supabase.table("system_config").select("value").eq("key", "strava_cookie").execute()
    if res.data:
        return res.data[0]["value"]
    raise Exception("❌ Não foi encontrado nenhum 'strava_cookie' na tabela system_config.")


def update_cookie_in_supabase(novo_cookie: str):
    supabase.table("system_config").upsert({
        "key": "strava_cookie",
        "value": novo_cookie
    }).execute()


def cutoff_epoch() -> int:
    dt = datetime.fromisoformat(BACKFILL_UNTIL_DATE)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# 🟢 Same parsing logic as strava_keep_alive.py (kept in sync deliberately —
# this is a one-off script, not imported, to avoid running keep_alive.py's
# module-level side effects/prints).
def parse_entries_block(json_data):
    bloco_atividades = []
    ultimo_timestamp = None

    entries = json_data.get("entries", [])
    for entry in entries:
        if entry.get("cursorData") and entry.get("cursorData").get("updated_at"):
            ultimo_timestamp = entry.get("cursorData").get("updated_at")

        entity_type = entry.get("entity")

        if entity_type == "Activity":
            act = entry.get("activity")
            if not act:
                continue

            athlete_data = act.get("athlete", {})
            stats_list = act.get("stats", [])

            act_id = act.get("id")
            act_name = act.get("activityName")
            ath_id = athlete_data.get("athleteId")
            ath_name = athlete_data.get("athleteName")
            first_name = athlete_data.get("firstName")
            device_name = act.get("deviceName", "Desconhecido")
            start_date = act.get("startDate")
            elapsed_time = act.get("elapsedTime")

        elif entity_type == "GroupActivity":
            group_data = entry.get("rowData", {})
            if not group_data or not isinstance(group_data.get("activities"), list):
                continue

            print(f"👥 Detetada atividade de grupo com {len(group_data['activities'])} atletas. A processar árvore de grupo...")

            for act in group_data.get("activities"):
                if not act:
                    continue

                stats_list = act.get("stats", [])

                act_id = act.get("activity_id")
                act_name = act.get("name") or "Corrida"
                ath_id = act.get("athlete_id")
                ath_name = act.get("athlete_name")
                first_name = act.get("athlete_firstname")

                device_name = act.get("device_name") or "Desconhecido"

                start_date = act.get("start_date")
                elapsed_time = act.get("elapsed_time")

                distancia_bruta = "0"
                if isinstance(stats_list, list):
                    for stat in stats_list:
                        if stat.get("key") == "stat_one":
                            match = re.search(r"([0-9.]+)", stat.get("value", ""))
                            if match:
                                distancia_bruta = match.group(1)
                            break

                if not act_id or str(act_id).lower() == "none":
                    continue

                bloco_atividades.append({
                    "activity_id": int(act_id),
                    "activity_name": act_name,
                    "athlete_id": int(ath_id) if ath_id and str(ath_id).lower() != "none" else None,
                    "athlete_name": ath_name,
                    "first_name": first_name,
                    "start_date": start_date,
                    "elapsed_time": int(elapsed_time or 0),
                    "device_name": device_name,
                    "distance": float(distancia_bruta)
                })
            continue
        else:
            continue

        if not act_id or str(act_id).lower() == "none":
            continue

        distancia_bruta = "0"
        if isinstance(stats_list, list):
            for stat in stats_list:
                if stat.get("key") == "stat_one":
                    match = re.search(r"([0-9.]+)", stat.get("value", ""))
                    if match:
                        distancia_bruta = match.group(1)
                    break

        bloco_atividades.append({
            "activity_id": int(act_id),
            "activity_name": act_name,
            "athlete_id": int(ath_id) if ath_id and str(ath_id).lower() != "none" else None,
            "athlete_name": ath_name,
            "first_name": first_name,
            "start_date": start_date,
            "elapsed_time": int(elapsed_time or 0),
            "device_name": device_name,
            "distance": float(distancia_bruta)
        })

    has_more = json_data.get("pagination", {}).get("hasMore", False)
    return bloco_atividades, ultimo_timestamp if has_more else None


def run_gap_backfill():
    cutoff_ts = cutoff_epoch()
    print(f"🕳️  A preencher o buraco do feed do clube até {BACKFILL_UNTIL_DATE} (epoch {cutoff_ts})...")

    cookie_atual = get_current_cookie()
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,pt-PT;q=0.9,pt;q=0.8",
        "referer": f"https://www.strava.com/clubs/{CLUB_ID}/recent_activity",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-requested-with": "XMLHttpRequest",
        "Cookie": cookie_atual
    })

    jitter = random.randint(5, 20)
    print(f"🎲 [Jitter] Aguardando {jitter}s antes do primeiro pedido...")
    time.sleep(jitter)

    proximo_cursor = None
    page = 1
    total_saved = 0

    while True:
        print(f"\n🔄 --- PÁGINA {page} ---")
        if page == 1:
            url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
        else:
            url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}&before={proximo_cursor}&cursor={proximo_cursor}"
            time.sleep(random.uniform(1.5, 3.5))

        response = session.get(url, allow_redirects=False)
        print(f"📥 Código de Resposta do Strava: {response.status_code}")

        if response.status_code in (301, 302):
            print(f"🚨 Redirecionado para: {response.headers.get('Location')}. Cookie expirado! A parar.")
            break
        if response.status_code != 200:
            print(f"⚠️ Status inesperado na página {page}: {response.status_code}. A parar.")
            break

        try:
            dados_do_feed = response.json()
        except Exception as e:
            print(f"⚠️ Erro ao ler JSON da página {page}: {e}")
            break

        atividades_bloco, proximo_cursor = parse_entries_block(dados_do_feed)
        print(f"📦 Extraídas {len(atividades_bloco)} atividades desta página.")

        if atividades_bloco:
            try:
                supabase.table("atividades_clube").upsert(
                    atividades_bloco,
                    on_conflict="activity_id"
                ).execute()
                total_saved += len(atividades_bloco)
                print(f"💾 Guardadas/atualizadas {len(atividades_bloco)} atividades (total acumulado: {total_saved}).")
            except Exception as e:
                print(f"❌ Erro ao gravar página {page} no Supabase: {e}")

        # Renova o cookie de sessão se o Strava emitiu um novo
        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_atual = f"_strava4_session={cookies_na_sessao['_strava4_session']};"

        if not proximo_cursor:
            print("🏁 O Strava não devolveu mais páginas (fim do histórico disponível no feed). A parar.")
            break

        cursor_dt = datetime.fromtimestamp(proximo_cursor, tz=timezone.utc)
        print(f"🔍 Próximo cursor: {proximo_cursor} ({cursor_dt.isoformat()})")

        if proximo_cursor < cutoff_ts:
            print(f"🏁 Cursor já ultrapassou o alvo ({BACKFILL_UNTIL_DATE}). Buraco coberto, a parar.")
            break

        if page >= MAX_PAGES:
            print(f"🛑 Atingido o limite de segurança de {MAX_PAGES} páginas antes de cobrir o alvo. A parar por segurança.")
            break

        page += 1

    if session.cookies.get_dict().get("_strava4_session"):
        novo_cookie = f"_strava4_session={session.cookies.get_dict()['_strava4_session']};"
        if novo_cookie != get_current_cookie():
            update_cookie_in_supabase(novo_cookie)
            print("🔄 Cookie global renovado guardado no Supabase!")

    print("\n" + "═" * 40)
    print(f"🎉 Backfill do buraco concluído. Total de atividades guardadas/atualizadas: {total_saved}")
    print("═" * 40)


if __name__ == "__main__":
    run_gap_backfill()
