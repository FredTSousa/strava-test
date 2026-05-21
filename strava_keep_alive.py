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
    
    # 1. Copiamos todos os headers do teu Postman, MAS SEM O COOKIE AQUI
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US",
        "baggage": "sentry-environment=production,sentry-release=d29a634aab6043b7b8279d4da97b1d9d332748f6,sentry-public_key=6ffc1c27d92347b49d7659886aab9deb,sentry-trace_id=7526e228ad004a27a02585f138b0032f,sentry-org_id=352714,sentry-sampled=false,sentry-sample_rand=0.7808152430404058,sentry-sample_rate=0",
        "priority": "u=1, i",
        "referer": f"https://www.strava.com/clubs/{CLUB_ID}/recent_activity?num_entries=75",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sentry-trace": "7526e228ad004a27a02585f138b0032f-af970c7c315b8da2-0",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "x-csrf-token": "BAIHJmyrSsY9R3I12QOK0v1SDl3d3bNaSCIgGWLyLYsAgwNJLXognYzZYMOh9P447pXJcQWnai9HcPZvVTHfIw",
        "x-requested-with": "XMLHttpRequest"
    })
    
    # 2. 🟢 A MAGIA: Limpar o valor do cookie de espaços e injetar nativamente no jar da sessão
    # Isto extrai apenas o valor limpo da hash do _strava4_session
    cookie_limpo = cookie_atual.replace("_strava4_session=", "").replace(";", "").strip()
    session.cookies.set("_strava4_session", cookie_limpo, domain=".strava.com")
    
    url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
    
    # Mantemos allow_redirects=False para travar o 301/302 se falhar
    response = session.get(url, allow_redirects=False)
    
    print(f"📥 Código de Resposta do Strava: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Conexão bem-sucedida! O Strava aceitou o request nativo.")
        
        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_renovado = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
            if cookie_renovado != cookie_atual:
                update_cookie_in_supabase(cookie_renovado)
                print("🔄 Cookie renovado guardado no Supabase!")
            else:
                print("ℹ️ O cookie atual ainda é o mais recente.")
                
    elif response.status_code in [301, 302]:
        print(f"🚨 Redirecionamento (Status {response.status_code}) para: {response.headers.get('Location')}")
    elif response.status_code in [401, 403]:
        print(f"🚨 Erro de Autenticação/Bloqueio (Status {response.status_code})")
    else:
        print(f"⚠️ Resposta inesperada: Status {response.status_code}")

if __name__ == "__main__":
    run_keep_alive()
