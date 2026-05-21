import os
import time
import random  
import requests
from supabase import create_client, Client

# Inicializa Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CLUB_ID = os.getenv("STRAVA_CLUB_ID")

if not SUPABASE_URL or not SUPABASE_KEY or not CLUB_ID:
    raise Exception("❌ Faltam variáveis de ambiente essenciais (Supabase ou Strava ID).")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_current_cookie() -> str:
    """Procura o cookie guardado na tabela do Supabase."""
    res = supabase.table("system_config").select("value").eq("key", "strava_cookie").execute()
    if res.data:
        return res.data[0]["value"]
    raise Exception("❌ Não foi encontrado nenhum 'strava_cookie' na tabela system_config.")

def update_cookie_in_supabase(novo_cookie: str):
    """Atualiza o cookie no Supabase usando a lógica de Upsert."""
    supabase.table("system_config").upsert({
        "key": "strava_cookie",
        "value": novo_cookie
    }).execute()

def run_keep_alive():
    # Jitter curto para segurança
    tempo_espera = random.randint(10, 15)
    print(f"🎲 [Segurança] A aguardar {tempo_espera} segundos...")
    time.sleep(tempo_espera)
    
    print("📡 A iniciar verificação do cookie...")
    cookie_atual = get_current_cookie()
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*", # Mudado para aceitar JSON
        "Accept-Language": "pt-PT,pt;q=0.9",
        "x-requested-with": "XMLHttpRequest",          # Cabeçalho que usaste no Postman
        "Cookie": cookie_atual
    })
    
    # 🟢 MUDANÇA AQUI: Batemos direto no feed que aceita o cookie
    url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
    
    # Deixamos o allow_redirects=False para apanhar se ele nos tentar mandar para o /login (302)
    response = session.get(url, allow_redirects=False)
    
    if response.status_code == 200:
        print("✅ Conexão bem-sucedida! O feed respondeu com sucesso.")
        
        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_renovado = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
            
            if cookie_renovado != cookie_atual:
                update_cookie_in_supabase(cookie_renovado)
                print("🔄 Cookie renovado guardado no Supabase!")
            else:
                print("ℹ️ O cookie atual ainda é o mais recente.")
                
    elif response.status_code in [302, 401, 403]:
        print(f"🚨 A sessão expirou ou foi rejeitada (Status {response.status_code}).")
        print("Redirecionado para o login. Atualiza o cookie no Supabase.")
    else:
        print(f"⚠️ Resposta inesperada do Strava. Status Code: {response.status_code}")

if __name__ == "__main__":
    run_keep_alive()
