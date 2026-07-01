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
            if name:
                entries.append(name)

    max_page = 1
    for a in soup.select("nav .pagination a[href]"):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            max_page = max(max_page, int(m.group(1)))

    return entries, max_page


def fetch_all_member_names():
    cookie = get_current_cookie()
    session = build_session(cookie)

    all_names = []
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
        all_names.extend(entries)

        if page == 1:
            max_page = detected_max_page

        page += 1
        if page <= max_page:
            time.sleep(random.uniform(3, 5))

    return all_names


def sync_club_members():
    strava_member_names = fetch_all_member_names()

    print(f"📋 Total de membros detetados no Strava: {len(strava_member_names)}")

    # Contar as ocorrências de cada nome na lista vinda do Strava
    strava_counts = {}
    for nome_completo in strava_member_names:
        strava_counts[nome_completo] = strava_counts.get(nome_completo, 0) + 1

    # Comparar com o Banco de Dados e inserir APENAS a diferença
    for nome_completo, qte_no_strava in strava_counts.items():
        partes = nome_completo.split(" ", 1)
        firstname = partes[0]
        lastname = partes[1] if len(partes) > 1 else ""

        if not firstname or not lastname:
            continue

        # Descobrir quantos registos idênticos já existem na tabela
        db_res = supabase.table("club_members") \
            .select("id", count="exact") \
            .eq("firstname", firstname) \
            .eq("lastname", lastname) \
            .execute()

        qte_no_db = db_res.count if db_res.count is not None else 0

        # 🟢 SEGUNDA BARREIRA DE SEGURANÇA: Só age se o Strava tiver MAIS do que o DB
        if qte_no_strava > qte_no_db:
            clones_a_criar = qte_no_strava - qte_no_db
            print(f"⚠️ Incremento detetado para {nome_completo}: Strava ({qte_no_strava}) vs DB ({qte_no_db}). A criar {clones_a_criar} novo(s) registo(s).")

            # Criamos exatamente o número de linhas em falta
            for _ in range(clones_a_criar):
                # Se a base de dados estava a zeros E no Strava só existe 1, é um utilizador único legítimo
                if qte_no_db == 0 and qte_no_strava == 1:
                    status_validacao = True
                    print(f"   ✅ Novo membro único: {nome_completo} entra como Validado.")
                else:
                    # Se o DB já tinha registos, ou se o Strava enviou múltiplos de uma vez, é ambíguo
                    status_validacao = False
                    print(f"   🚨 Homónimo/Clone detetado: {nome_completo} entra como Pendente.")

                # Inserir o novo elemento incremental
                supabase.table("club_members").insert({
                    "firstname": firstname,
                    "lastname": lastname,
                    "is_validated": status_validacao
                }).execute()

    print("🏁 Sincronização incremental terminada.")


if __name__ == "__main__":
    sync_club_members()
