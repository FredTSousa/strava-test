import os
import time
import random  
import requests

from supabase import create_client, Client




print("📂 Pasta atual onde o Python está a rodar:", os.getcwd())
print("📄 Ficheiros que o Python consegue ver nesta pasta:", os.listdir('.'))
print(f"🔍 O que foi lido do SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"🔍 O que foi lido do SUPABASE_KEY: {os.getenv('SUPABASE_KEY')}")

print(f"🔍 O que foi lido do STRAVA_CLIENT_ID: {os.getenv('STRAVA_CLIENT_ID')}")

print(f"🔍 O que foi lido do STRAVA_REFRESH_TOKEN: {os.getenv('STRAVA_REFRESH_TOKEN')}")

print(f"🔍 O que foi lido do STRAVA_CLUB_ID: {os.getenv('STRAVA_CLUB_ID')}")
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

from curl_cffi import requests 

def run_keep_alive():
    print("📡 A iniciar verificação com emulador de browser...")
    cookie_atual = get_current_cookie()
    
    # Criamos a sessão usando o motor do Chrome limpo
    session = requests.Session(impersonate="chrome120")
    
    # Headers limpos de lixo de telemetria antiga do teu Postman (Sentry, etc.)
    # Deixamos apenas o que o Chrome envia nativamente
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
        "Cookie": cookie_atual # Injetamos a string direta do Supabase
    })
    
    # URL do feed limpo, sem timestamps antigos que possam ter expirado
    url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
    
    # Fazemos o request travando redirecionamentos
    response = session.get(url, allow_redirects=False)
    
    print(f"📥 Código de Resposta do Strava: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ CONSEGUIMOS! O Strava achou que o Python era o Chrome real.")
        # 🟢 PRINT DO RESPONSE BODY EM FORMATO JSON
        # Tenta tratar a resposta como JSON
        try:
            dados_do_feed = response.json()
            import json
            json_bonito = json.dumps(dados_do_feed, indent=2, ensure_ascii=False)
            
            # 1. Faz o print de TUDO no terminal
            print("\n📦 --- CONTEÚDO DO FEED COMPLETO (JSON) ---")
            print(json_bonito)
            print("-------------------------------------------\n")
            
            # 2. Grava num ficheiro local para não perderes nada
            with open("resposta_strava.json", "w", encoding="utf-8") as f:
                f.write(json_bonito)
            print("💾 Gravação concluída! O conteúdo total foi guardado em 'resposta_strava.json'")
            
        except Exception:
            # Se não for JSON, é HTML puro
            html_completo = response.text
            
            # 1. Faz o print de TUDO no terminal
            print("\n📦 --- CONTEÚDO COMPLETO (HTML) ---")
            print(html_completo)
            print("-----------------------------------\n")
            
            # 2. Grava num ficheiro local
            with open("resposta_strava.html", "w", encoding="utf-8") as f:
                f.write(html_completo)
            print("💾 Gravação concluída! O conteúdo total foi guardado em 'resposta_strava.html'")
        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_renovado = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
            if cookie_renovado != cookie_atual:
                update_cookie_in_supabase(cookie_renovado)
                print("🔄 Cookie renovado guardado no Supabase!")
            else:
                print("ℹ️ O cookie atual ainda é o mais recente.")
                
    elif response.status_code in [301, 302]:
        print(f"🚨 Redirecionado para: {response.headers.get('Location')}")
    else:
        print(f"⚠️ Status inesperado: {response.status_code}")

if __name__ == "__main__":
    run_keep_alive()
