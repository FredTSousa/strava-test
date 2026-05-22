import os
import time
import random  
import re
import json
from supabase import create_client, Client
from curl_cffi import requests # Mantemos a tua curl_cffi para o bypass

# Prints de diagnóstico (podes apagar mais tarde se quiseres limpar o log)
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

# 🟢 NOVA FUNÇÃO: Processa o JSON dinâmico e faz Upsert das atividades
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
        
    if sorted(atividades_limpas, key=lambda x: x['activity_id']):
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
    
    print(f"🎲 [Jitter] Para segurança,
