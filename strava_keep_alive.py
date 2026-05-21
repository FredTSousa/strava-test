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
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-PT,pt;q=0.9",
        "x-requested-with": "XMLHttpRequest",
        "Cookie": cookie_atual
    })
    
    # 🟢 GARANTIR O WWW. (Exatamente como o teu cURL do Postman)
    url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
    
    # 🟢 MUDANÇA: Permitimos o redirecionamento automático (True)
    response = session.get(url, allow_redirects=True)
    
    # Se ele foi redirecionado para a página de login, o URL final vai conter "/login"
    if "login" in response.url:
        print("🚨 A sessão expirou! O Strava redirecionou-nos para a página de login.")
        print("Ação necessária: Atualiza o cookie na tabela 'system_config' do Supabase.")
        return

    if response.status_code == 200:
        print("✅ Conexão bem-sucedida! O feed respondeu com sucesso.")
        
        # Se houve um 301 pelo caminho, o requests seguiu-o e chegou ao destino
        if response.history:
            print(f"ℹ️ Nota: O request passou por um redirecionamento {response.history[0].status_code}")

        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_renovado = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
            
            if cookie_renovado != cookie_atual:
                update_cookie_in_supabase(cookie_renovado)
                print("🔄 Cookie renovado guardado no Supabase!")
            else:
                print("ℹ️ O cookie atual ainda é o mais recente.")
    else:
        print(f"⚠️ Resposta inesperada do Strava. Status Code final: {response.status_code}")

if __name__ == "__main__":
    run_keep_alive()
