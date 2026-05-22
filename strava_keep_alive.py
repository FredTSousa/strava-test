import os
import time
import random  
import re
import json
from supabase import create_client, Client
from curl_cffi import requests # Mantemos a curl_cffi para o bypass da Cloudflare

# Prints de diagnóstico para o terminal/GitHub Actions log
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

def process_and_save_activities(json_data):
    """Varre as entries do feed, limpa a distância com Regex e envia para o Supabase."""
    atividades_limpas = []
    entries = json_data.get("entries", [])
    
    for entry in entries:
        if entry.get("entity") != "Activity":
            continue
            
        activity_data = entry.get("activity", {})
        athlete_data = activity_data.get("athlete", {})
        stats_list = activity_data.get("stats", [])
        
        # Regex para capturar apenas o número decimal de dentro do HTML da distância
        distancia_bruta = "0"
        for stat in stats_list:
            if stat.get("key") == "stat_one":
                match = re.search(r"([0-9.]+)", stat.get("value", ""))
                if match:
                    distancia_bruta = match.group(1)
                break
        
        dados_formatados = {
            "activity_id": activity_data.get("id"),
            "activity_name": activity_data.get("activityName"),
            "athlete_id": athlete_data.get("athleteId"),
            "athlete_name": athlete_data.get("athleteName"),
            "first_name": athlete_data.get("firstName"),
            "start_date": activity_data.get("startDate"),
            "elapsed_time": activity_data.get("elapsedTime"),
            "device_name": activity_data.get("deviceName", "Desconhecido"),
            "distance": float(distancia_bruta)
        }
        atividades_limpas.append(dados_formatados)
        
    # 🟢 CORREÇÃO CRUCIAL DA SINTAXE AQUI:
    if len(atividades_limpas) > 0:
        try:
            print(f"🚀 A enviar {len(atividades_limpas)} atividades extraídas para o Supabase...")
            supabase.table("atividades_clube").upsert(atividades_limpas).execute()
            print("✅ Sincronização de atividades concluída na base de dados!")
        except Exception as e:
            print(f"❌ Erro ao fazer upsert no Supabase: {e}")
    else:
        print("ℹ️ Nenhuma atividade desportiva nova encontrada para processar.")

def run_keep_alive():
    print("📡 A iniciar verificação com emulador de browser...")
    tempo_espera = random.randint(10, 180)
    
    print(f"🎲 [Jitter] Para segurança, o script vai fingir-se de humano e aguardar {tempo_espera} segundos...")
    time.sleep(tempo_espera)
    
    print("📡 Atraso concluído. A disparar pedido para o Strava...")
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
    
    url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
    
    response = session.get(url, allow_redirects=False)
    print(f"📥 Código de Resposta do Strava: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ CONSEGUIMOS! O Strava achou que o Python era o Chrome real.")
        
        try:
            dados_do_feed = response.json()
            json_bonito = json.dumps(dados_do_feed, indent=2, ensure_ascii=False)
            
            # Executa o processamento do feed dinâmico e salva no Supabase
            process_and_save_activities(dados_do_feed)
            
            # Só cria ficheiros locais se NÃO estiver a correr no GitHub Actions
            if not os.getenv("GITHUB_ACTIONS"):
                print("\n📦 --- CONTEÚDO DO FEED COMPLETO (JSON) ---")
                print(json_bonito[:1000] + "... (cortado para o log)")
                with open("resposta_strava.json", "w", encoding="utf-8") as f:
                    f.write(json_bonito)
                print("💾 Gravação concluída localmente em 'resposta_strava.json'")
                
        except Exception as e:
            html_completo = response.text
            print(f"⚠️ Resposta não era o JSON esperado: {e}")
            if not os.getenv("GITHUB_ACTIONS"):
                with open("resposta_strava.html", "w", encoding="utf-8") as f:
                    f.write(html_completo)
                print("💾 Conteúdo HTML guardado em 'resposta_strava.html'")
                
        # Mantém a verificação e renovação original do cookie intacta
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
