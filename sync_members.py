import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
from cron_sync import get_valid_access_token

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def sync_club_members():
    access_token = get_valid_access_token()
    url = f"https://www.strava.com/api/v3/clubs/{CLUB_ID}/members"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Puxar todos os membros do Strava (Gestão de paginação)
    strava_members = []
    page = 1
    while True:
        res = requests.get(url, headers=headers, params={"page": page, "per_page": 200}, timeout=30)
        data = res.json()
        if not data:
            break
        strava_members.extend(data)
        page += 1

    print(f"📋 Total de membros detetados no Strava: {len(strava_members)}")

    # 2. Contar as ocorrências de cada nome na lista vinda do Strava
    strava_counts = {}
    for m in strava_members:
        fname = m.get("firstname", "").strip()
        lname = m.get("lastname", "").strip()
        if fname and lname:
            nome_chave = f"{fname} {lname}"
            strava_counts[nome_chave] = strava_counts.get(nome_chave, 0) + 1

    # 3. Comparar com o Banco de Dados e inserir APENAS a diferença
    for nome_completo, qte_no_strava in strava_counts.items():
        partes = nome_completo.split(" ", 1)
        firstname = partes[0]
        lastname = partes[1] if len(partes) > 1 else ""

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
