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
    # 🟢 ADICIONAR JITTER (Ruído aleatório)
    # Gera um tempo de espera aleatório entre 10 segundos e 15 minutos (900 segundos)
    tempo_espera = random.randint(10, 400)
    print(f"🎲 [Segurança] A simular comportamento humano. A aguardar {tempo_espera // 60} minutos e {tempo_espera % 60} segundos antes de disparar...")
    time.sleep(tempo_espera)
    print("📡 A iniciar verificação e renovação do cookie do Strava...")
    
    # 1. Obter o cookie que temos atualmente guardado
    cookie_atual = get_current_cookie()
    
    # 2. Configurar a sessão HTTP do requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-PT,pt;q=0.9",
        "Cookie": cookie_atual
    })
    
    # 3. Fazer um request simples à página do clube para forçar o Keep-Alive
    url = f"https://www.strava.com/clubs/{CLUB_ID}/recent_activity"
    response = session.get(url, allow_redirects=False)
    
    if response.status_code == 200:
        print("✅ Conexão bem-sucedida! A sessão no Strava está ativa.")
        
        # O requests.Session captura automaticamente se o Strava enviou um novo 'Set-Cookie'
        cookies_na_sessao = session.cookies.get_dict()
        if "_strava4_session" in cookies_na_sessao:
            cookie_renovado = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
            
            # Se o cookie mudou face ao que tínhamos no Supabase, guardamos o novo
            if cookie_renovado != cookie_atual:
                update_cookie_in_supabase(cookie_renovado)
                print("🔄 O Strava emitiu uma nova sessão. Cookie atualizado no Supabase!")
            else:
                print("ℹ️ O cookie atual ainda é válido e não precisou de alteração.")
    
    elif response.status_code in [302, 401, 403]:
        print("🚨 Erro: O cookie expirou completamente ou a sessão foi derrubada pelo Strava.")
        print("Ação necessária: Copia um cookie novo do browser e cola na tabela 'system_config'.")
    else:
        print(f"⚠️ Resposta inesperada do Strava. Status Code: {response.status_code}")

if __name__ == "__main__":
    run_keep_alive()
