import os
import math
from supabase import create_client
from firebase_admin import credentials, firestore, initialize_app

# ==========================================
# CONFIGURAÇÕES E INICIALIZAÇÃO
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 🔒 Barreira de segurança: Apenas o teu ID avança para o Firestore
MEU_USER_ID_TESTE = "vIgrcNOyXieB3D1oE57OIhR0EW33"

if not len(initialize_app.__self__._apps):
    cred = credentials.Certificate("caminho/para/o-teu-firebase-key.json")
    initialize_app(cred)

db_firestore = firestore.client()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def run_batch_sync():
    print("⚡ A iniciar varrimento de atividades pendentes (Modo de Teste: Draft Forçado)...")
    
    try:
        # Procurar metadados com utilizador atribuído e por sincronizar
        resposta_meta = supabase.table("strava_activities_metadata") \
            .select("id_virtual, assigned_firestore_user_id, challenge_id") \
            .not_.is_("assigned_firestore_user_id", "null") \
            .eq("synced_to_firestore", False) \
            .execute()
        
        atividades_pendentes = resposta_meta.data
        
        if not atividades_pendentes:
            print("✨ Nenhuma atividade pendente para sincronizar.")
            return

        sync_count = 0

        for registo in atividades_pendentes:
            id_virtual = registo["id_virtual"]
            user_id = registo["assigned_firestore_user_id"]
            challenge_id = registo["challenge_id"]

            # 🛑 CLÁUSULA DE BARREIRA: Se não for o teu ID de teste, ignora
            if user_id != MEU_USER_ID_TESTE:
                continue

            # Procurar os dados detalhados na View do Supabase
            resposta_view = supabase.table("view_strava_activities") \
                .select("raw_json") \
                .eq("id_virtual", id_virtual) \
                .single() \
                .execute()
            
            if not resposta_view.data:
                print(f"⚠️ Dados brutos não encontrados para a atividade {id_virtual}. A saltar...")
                continue
                
            raw = resposta_view.data.get("raw_json", {})
            moving_seconds = raw.get("moving_time", 0)
            
            # Conversões matemáticas de tempo
            horas = moving_seconds // 3600
            minutos = (moving_seconds % 3600) // 60
            segundos = moving_seconds % 60
            dur_min = round(moving_seconds / 60)
            
            # Mapeamento estrito do desporto
            tipo = "outro"
            sport_type = raw.get("sport_type")
            if sport_type == "Run":
                tipo = "corrida"
            elif sport_type == "TrailRun":
                tipo = "trail"

            # 📂 Payload exato para o Firestore (Esquema NoSQL dinâmico)
            treino_payload = {
                "criadoEm": firestore.SERVER_TIMESTAMP,
                "data": raw.get("start_date"),
                "durMin": dur_min,
                "elev": round(raw.get("total_elevation_gain", 0)),
                "km": round((raw.get("distance", 0) / 1000), 2),
                "horas": horas,
                "minutos": minutes,
                "segundos": segundos,
                "nome": raw.get("name", "Treino Sem Nome"),
                "tipo": tipo,
                "externalId": id_virtual,
                "challengeId": challenge_id,
                "estado": "draft"  # 👈 Regra de Ouro: Entra sempre como rascunho bloqueado
            }

            # Referência do documento: users -> {MEU_USER_ID_TESTE} -> treinos -> {id_virtual}
            treino_ref = db_firestore.collection("users").document(MEU_USER_ID_TESTE) \
                                     .collection("treinos").document(id_virtual)
            
            # Grava ou atualiza mantendo outros campos intocados caso existam
            treino_ref.set(treino_payload, merge=True)

            # Validar e fechar a flag no Supabase para não repetir no próximo ciclo
            supabase.table("strava_activities_metadata") \
                    .update({"synced_to_firestore": True}) \
                    .eq("id_virtual", id_virtual) \
                    .execute()
            
            sync_count += 1
            print(f"   ↳ [ID: {id_virtual}] Sincronizado como DRAFT no Firestore.")

        if sync_count > 0:
            print(f"🎉 Processo concluído! {sync_count} treinos guardados em modo rascunho.")
        else:
            print("✨ Varrimento terminado: Nenhuma atividade elegível pertencia ao teu ID.")

    except Exception as e:
        print(f"❌ Erro crítico no lote: {e}")

if __name__ == "__main__":
    run_batch_sync()
