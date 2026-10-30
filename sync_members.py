import os
import re
import random
import time
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from supabase import create_client, Client
from curl_cffi import requests as curl_requests

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_current_cookie() -> str:
    res = supabase.table("system_config").select("value").eq("key", "strava_cookie").execute()
    if res.data:
        return res.data[0]["value"]
    raise Exception("No 'strava_cookie' found in system_config table.")


def build_session(cookie: str):
    # 🟢 Mesma "impressão digital" usada em enrich_activities.py, validada contra uma
    # requisição real (Postman) para /clubs/{id}/members.
    session = curl_requests.Session(impersonate="chrome146")
    session.headers.update({
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "pt-PT,pt;q=0.9,en-PT;q=0.8,en-GB;q=0.7,en-US;q=0.6,en;q=0.5",
        "cache-control": "max-age=0",
        "priority": "u=0, i",
        "referer": f"https://www.strava.com/clubs/{CLUB_ID}/members",
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


def parse_members_page(html: str):
    # 🟢 Página server-rendered normal (não é XHR/JSON). "Administradores" e "Membros" são
    # duas secções separadas com o mesmo layout; a lista pequena na sidebar (ul.grid) é só
    # uma pré-visualização e não deve ser confundida com a lista paginada real (ul.list-athletes).
    # 🟢 O href de cada atleta ("/athletes/<id>") expõe o athlete_id real do Strava -- é a
    # ÚNICA identidade estável que existe aqui. O nome sozinho não chega: o Strava mostra
    # apelidos truncados ("Magda J.") nalgumas alturas e completos ("Magda Jorge Coelho")
    # noutras, e várias pessoas usam o mesmo nome. Sem o id, cada mudança de como o nome é
    # mostrado parecia um membro novo e criava um clone.
    soup = BeautifulSoup(html, "html.parser")
    entries = []

    for h2 in soup.find_all("h2"):
        heading = h2.get_text(strip=True)
        if heading not in ("Administradores", "Membros"):
            continue

        ul = h2.find_next_sibling("ul", class_="list-athletes")
        if not ul:
            continue

        for li in ul.find_all("li", recursive=False):
            a = li.find("a", href=True)
            if not a or "/athletes/" not in a["href"]:
                continue
            name = a.get_text(strip=True)
            id_match = re.search(r"/athletes/(\d+)", a["href"])
            if name and id_match:
                entries.append({"name": name, "athlete_id": int(id_match.group(1))})

    max_page = 1
    for a in soup.select("nav .pagination a[href]"):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))

    return entries, max_page


def fetch_all_members():
    cookie = get_current_cookie()
    session = build_session(cookie)

    all_entries = []
    page = 1
    max_page = 1

    while page <= max_page:
        url = f"https://www.strava.com/clubs/{CLUB_ID}/members?page={page}&page_uses_modern_javascript=true"
        print(f"📡 A ler página {page}{f'/{max_page}' if max_page > 1 else ''}...")

        response = session.get(url, allow_redirects=False, timeout=30)
        if response.status_code != 200:
            print(f"⚠️ Status inesperado {response.status_code} na página {page}. A parar.")
            break

        entries, detected_max_page = parse_members_page(response.text)
        all_entries.extend(entries)

        if page == 1:
            max_page = detected_max_page

        page += 1
        if page <= max_page:
            time.sleep(random.uniform(3, 5))

    # 🟢 Um membro pode aparecer duas vezes na mesma leitura (ex: admins listados tanto em
    # "Administradores" como em "Membros") -- o athlete_id é que diz se é a mesma pessoa.
    by_athlete_id = {}
    for entry in all_entries:
        by_athlete_id[entry["athlete_id"]] = entry
    return list(by_athlete_id.values())


def fetch_existing_members_by_athlete_id():
    rows = []
    page_size = 1000
    offset = 0
    while True:
        res = supabase.table("club_members") \
            .select("id, firstname, lastname, athlete_id") \
            .not_.is_("athlete_id", "null") \
            .order("id") \
            .range(offset, offset + page_size - 1) \
            .execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return {r["athlete_id"]: r for r in rows}


def sync_club_members():
    # 🟢 requer a coluna club_members.athlete_id (ver backfill_and_collapse.sql) -- sem ela
    # esta função falha ao tentar gravar/ler por athlete_id.
    strava_members = fetch_all_members()
    print(f"📋 Total de membros detetados no Strava: {len(strava_members)}")

    existing_by_athlete_id = fetch_existing_members_by_athlete_id()
    print(f"📋 Membros já identificados por athlete_id na base de dados: {len(existing_by_athlete_id)}")

    updated = 0
    created = 0

    for entry in strava_members:
        athlete_id = entry["athlete_id"]
        nome_completo = entry["name"]
        partes = nome_completo.split(" ", 1)
        firstname = partes[0]
        lastname = partes[1] if len(partes) > 1 else ""

        if not firstname or not lastname:
            continue

        existing = existing_by_athlete_id.get(athlete_id)

        if existing is None:
            # 🟢 athlete_id novo = pessoa nova, sem ambiguidade possível -- entra sempre validado.
            supabase.table("club_members").insert({
                "firstname": firstname,
                "lastname": lastname,
                "athlete_id": athlete_id,
                "is_validated": True,
            }).execute()
            created += 1
            print(f"   ✅ Novo membro: {nome_completo} (athlete_id={athlete_id})")
            continue

        if existing["firstname"] != firstname or existing["lastname"] != lastname:
            # 🟢 Mesma pessoa (mesmo athlete_id), o Strava só mudou como mostra o nome
            # (ex: revelou o apelido completo) -- atualiza o registo em vez de clonar.
            supabase.table("club_members").update({
                "firstname": firstname,
                "lastname": lastname,
            }).eq("id", existing["id"]).execute()
            updated += 1
            print(f"   🔄 Nome atualizado para athlete_id={athlete_id}: '{existing['firstname']} {existing['lastname']}' -> '{nome_completo}'")

    print(f"🏁 Sincronização terminada. Novos: {created}, Atualizados: {updated}.")


if __name__ == "__main__":
    sync_club_members()
