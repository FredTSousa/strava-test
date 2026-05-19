import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from cron_sync import get_valid_access_token

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")
# ... (garante que a tua função get_valid_access_token está aqui)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_club_members():
    access_token = get_valid_access_token()
    url = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/members"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Puxar todos os membros do Strava
    strava_members = []
    page = 1
    while True:
        res = requests.get(url, headers=headers, params={"page": page, "per_page": 200})
        data = res.json()
        if not data:
            break
        strava_members.extend(data)
        page += 1

    print(f"📋 Total de membros no Strava atualmente: {len(strava_members)}")

    # 2. Contar as ocorrências de cada nome no Strava
    strava_counts = {}
    for m in strava_members:
        fname = m.get("firstname", "").strip()
        lname = m.get("lastname", "").strip()
        if fname and lname:
            nome_chave = f"{fname} {lname}"
            strava_counts[nome_chave] = strava_counts.get(nome_chave, 0) + 1

    # 3. Comparar com o Banco de Dados
    for nome_completo, qte_no_strava in strava_counts.items():
        partes = nome_completo.split(" ", 1)
        firstname = partes[0]
        lastname = partes[1] if len(partes) > 1 else ""

        # Contar quantos já temos guardados
        db_res = supabase.table("club_members") \
            .select("id", count="exact") \
            .eq("firstname", firstname) \
            .eq("lastname", lastname) \
            .execute()
        
        qte_no_db = db_res.count if db_res.count is not None else 0

        # Se houver um membro novo (ou um clone novo), inserimos com is_validated = False
        if qte_no_strava > qte_no_db:
            clones_a_criar = qte_no_strava - qte_no_db
            print(f"⚠️ Novo registo detetado para {nome_completo}. A criar {clones_a_criar} membro(s) pendente(s).")
            
            for _ in range(clones_a_criar):
                supabase.table("club_members").insert({
                    "firstname": firstname,
                    "lastname": lastname,
                    "is_validated": False # Entra como pendente de revisão!
                }).execute()

    print("🏁 Sincronização de membros terminada.")

if __name__ == "__main__":
    sync_club_members()
