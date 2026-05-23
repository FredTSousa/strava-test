import os
import time
import random  
import re
import json
from supabase import create_client, Client
from curl_cffi import requests

# Prints de diagnóstico
print("📂 Pasta atual onde o Python está a rodar:", os.getcwd())
print("📄 Ficheiros que o Python consegue ver nesta pasta:", os.listdir('.'))
print(f"🔍 O que foi lido do SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"🔍 O que foi lido do SUPABASE_KEY: {os.getenv('SUPABASE_KEY')}")
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

# 🟢 FUNÇÃO MELHORADA: Processa um bloco de entradas e extrai o próximo cursor
def parse_entries_block(json_data):
    """Varre as entries de um request, desmembra GroupActivities e extrai tudo de forma plana."""
    bloco_atividades = []
    ultimo_timestamp = None
    
    entries = json_data.get("entries", [])
    for entry in entries:
        # Guarda o timestamp do cursor para a paginação
        if entry.get("cursorData") and entry.get("cursorData").get("updated_at"):
            ultimo_timestamp = entry.get("cursorData").get("updated_at")
            
        entity_type = entry.get("entity")
        
        # Criamos uma lista temporária para normalizar os dados, quer venham de atividade individual ou grupo
        atividades_para_processar = []
        
        # CENÁRIO 1: É uma atividade individual normal
        if entity_type == "Activity":
            if entry.get("activity"):
                atividades_para_processar.append(entry.get("activity"))
                
        # CENÁRIO 2: É uma atividade de grupo (Vários atletas juntos) 🏃‍♂️🏃‍♀️
        elif entity_type == "GroupActivity":
            group_data = entry.get("rowData", {})
            if group_data and isinstance(group_data.get("activities"), list):
                print(f"👥 Detetada atividade de grupo com {len(group_data['activities'])} atletas. A desmembrar...")
                atividades_para_processar.extend(group_data.get("activities"))
        else:
            continue
            
        # Agora processamos a lista normalizada (seja 1 ou várias)
        for act in atividades_para_processar:
            if not act:
                continue
                
            athlete_data = act.get("athlete", {})
            stats_list = act.get("stats", [])
            
            # Extração limpa da distância
            distancia_bruta = "0"
            if isinstance(stats_list, list):
                for stat in stats_list:
                    if stat.get("key") == "stat_one":
                        match = re.search(r"([0-9.]+)", stat.get("value", ""))
                        if match:
                            distancia_bruta = match.group(1)
                        break
            
            # Formata o dicionário exatamente como a tua tabela Supabase espera
            dados_formatados = {
                "activity_id": str(act.get("activity_id") or act.get("id")), # Suporta as duas nomenclaturas do JSON
                "activity_name": act.get("name") or act.get("activityName"),
                "athlete_id": str(athlete_data.get("athlete_id") or athlete_data.get("athleteId")),
                "athlete_name": athlete_data.get("athlete_name") or athlete_data.get("athleteName"),
                "first_name": athlete_data.get("athlete_firstname") or athlete_data.get("firstName"),
                "start_date": act.get("start_date") or act.get("startDate"),
                "elapsed_time": int(act.get("elapsed_time") or act.get("elapsedTime") or 0),
                "device_name": act.get("device_name") or act.get("deviceName") or "Desconhecido",
                "distance": float(distancia_bruta)
            }
            
            bloco_atividades.append(dados_formatados)
        
    has_more = json_data.get("pagination", {}).get("hasMore", False)
    return bloco_atividades, ultimo_timestamp if has_more else None
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
    
    # Lista onde vamos acumular TODOS os treinos dos 4 requests antes de mandar para a DB
    todas_atividades_encontradas = []
    
    # Variáveis de controlo da paginação
    proximo_cursor = None
    MAX_REQUESTS = 4
    
    for i in range(1, MAX_REQUESTS + 1):
        print(f"\n🔄 --- A EXECUTAR REQUISIÇÃO {i} DE {MAX_REQUESTS} ---")
        
        # Constrói o URL dinâmico: na primeira ronda vai limpo, nas seguintes leva o cursor
        if i == 1:
            url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}"
        else:
            url = f"https://www.strava.com/clubs/{CLUB_ID}/feed?feed_type=club&club_id={CLUB_ID}&before={proximo_cursor}&cursor={proximo_cursor}"
            # Pequena pausa humana entre requests seguidos para não levantar suspeitas
            time.sleep(random.uniform(1.5, 3.5))
            
        print(f"📡 A disparar request para: {url}")
        response = session.get(url, allow_redirects=False)
        print(f"📥 Código de Resposta do Strava: {response.status_code}")
        
        if response.status_code == 200:
            try:
                dados_do_feed = response.json()
                
                # Intercetamos e processamos o bloco atual
                atividades_bloco, proximo_cursor = parse_entries_block(dados_do_feed)
                todas_atividades_encontradas.extend(atividades_bloco)
                print(f"📦 Extraídas {len(atividades_bloco)} atividades deste bloco.")
                
                # Apenas para o teu Debug local na primeira página
                if i == 1 and not os.getenv("GITHUB_ACTIONS"):
                    with open("resposta_strava.json", "w", encoding="utf-8") as f:
                        json.dump(dados_do_feed, f, indent=2, ensure_ascii=False)
                
                # Se o Strava disser que já não há mais páginas no feed, paramos o loop mais cedo
                if not proximo_cursor:
                    print("ℹ️ O Strava indicou que não há mais atividades antigas no histórico. A parar paginação.")
                    break
                    
                print(f"🔍 Próximo cursor detetado para a ronda seguinte: {proximo_cursor}")
                
                # Verifica renovação do cookie (só precisamos de guardar o Set-Cookie da última sessão válida)
                cookies_na_sessao = session.cookies.get_dict()
                if "_strava4_session" in cookies_na_sessao:
                    cookie_atual = f"_strava4_session={cookies_na_sessao['_strava4_session']};"
                    
            except Exception as e:
                print(f"⚠️ Erro ao processar dados da ronda {i}: {e}")
                break
                
        elif response.status_code in [301, 302]:
            print(f"🚨 Redirecionado para: {response.headers.get('Location')}. Cookie expirado!")
            break
        else:
            print(f"⚠️ Status inesperado na ronda {i}: {response.status_code}")
            break

    # 🟢 NO FINAL DOS REQUESTS: Fazemos um único Upsert massivo para o Supabase
    if len(todas_atividades_encontradas) > 0:
        try:
            print(f"\n🚀 Concluído! A enviar o total acumulado de {len(todas_atividades_encontradas)} atividades para o Supabase...")
            # 🟢 CORREÇÃO: Força o Supabase a fazer UPDATE sempre que o activity_id já existir na tabela
            supabase.table("atividades_clube").upsert(
                todas_atividades_encontradas, 
                on_conflict="activity_id"
            ).execute()
            print("✅ Sincronização em massa concluída com sucesso na base de dados!")
        except Exception as e:
            print(f"❌ Erro ao fazer upsert na DB: {e}")
    else:
        print("\nℹ️ Nenhuma atividade recolhida para salvar.")

    # Se o cookie mudou ao longo do processo, atualiza-o no fim
    if session.cookies.get_dict().get("_strava4_session"):
        novo_cookie = f"_strava4_session={session.cookies.get_dict()['_strava4_session']};"
        if novo_cookie != get_current_cookie():
            update_cookie_in_supabase(novo_cookie)
            print("🔄 Cookie global renovado guardado no Supabase!")

if __name__ == "__main__":
    run_keep_alive()
