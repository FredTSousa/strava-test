import os
import json
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from supabase import create_client, Client

load_dotenv()

# ==========================================
# 1. INICIALIZAÇÃO DAS BASES DE DADOS
# ==========================================

# Inicializa Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inicializa Firebase usando o Secret do GitHub (Igual ao teu script de users)
firebase_secret = os.getenv("FIREBASE_SERVICE_ACCOUNT")
if not firebase_secret:
    raise Exception("Missing FIREBASE_SERVICE_ACCOUNT environment variable.")

cred_dict = json.loads(firebase_secret)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)

db_firestore = firestore.client()

# 🔒 Barreira de segurança para a fase de testes
MEU_USER_ID_TESTE = "vIgrcNOyXieB3D1oE57OIhR0EW33"

# ==========================================
# 2. LOGICA DE SYNC DE TREINOS (DRAFT)
# ==========================================

def run_batch_sync():
    print("🚀 Starting Supabase to Firestore workouts sync (Test Mode: Draft)...")
    
    try:
        # Puxar metadados do Supabase elegíveis (com user e por sincronizar)
        resposta_meta = supabase.table("strava_activities_metadata") \
            .select("id_virtual, assigned_firestore_user_id, challenge_id") \
            .not_.is_("assigned_firestore_user_id", "null") \
            .eq("synced_to_firestore", False) \
            .execute()
        
        atividades_pendentes = resposta_meta.data
        
        if not atividades_pendentes:
            print("✨ No pending workouts to sync.")
            return

        sync_count = 0

        for registo in atividades_pendentes:
            id_virtual = registo["id_virtual"]
            user_id = registo["assigned_firestore_user_id"]
            challenge_id = registo["challenge_id"]

            # 🛑 CLÁUSULA DE BARREIRA: Para já, só mexe no teu user
            if user_id != MEU_USER_ID_TESTE:
                continue

            # Puxar dados brutos da View do Supabase
            resposta_view = supabase.table("view_strava_activities") \
                .select("raw_json") \
                .eq("id_virtual", id_virtual) \
                .single() \
                .execute()
            
            if not resposta_view.data:
                print(f"⚠️ Warning: Raw JSON not found for activity {id_virtual}. Skipping...")
                continue
                
            raw = resposta_view.data.get("raw_json", {})
            moving_seconds = raw.get("moving_time", 0)
            
            # Cálculos de tempo para o teu modelo Firestore
            horas = moving_seconds // 3600
            minutos = (moving_seconds % 3600) // 60
            segundos = moving_seconds % 60
            dur_min = round(moving_seconds / 60)
            
            # Mapeamento do tipo de desporto
            tipo = "outro"
            sport_type = raw.get("sport_type")
            if sport_type == "Run":
                tipo = "corrida"
            elif sport_type == "TrailRun":
                tipo = "trail"

            # Payload estruturado para a subcoleção do teu Firestore
            treino_payload = {
                "criadoEm": firestore.SERVER_TIMESTAMP, # Timestamp do Firebase
                "data": raw.get("start_date"),
                "durMin": dur_min,
                "elev": round(raw.get("total_elevation_gain", 0)),
                "km": round((raw.get("distance", 0) / 1000), 2),
                "horas": horas,
                "minutos": minutos,
                "segundos": segundos,
                "nome": raw.get("name", "Treino Sem Nome"),
                "tipo": tipo,
                "externalId": id_virtual,
                "challengeId": challenge_id,
                "estado": "draft" # Entra sempre bloqueado como rascunho
            }

            # Referência direta: users -> {MEU_USER_ID_TESTE} -> treinos -> {id_virtual}
            treino_ref = db_firestore.collection("users").document(MEU_USER_ID_TESTE) \
                                     .collection("treinos").document(id_virtual)
            
            # Upsert seguro no Firestore
            treino_ref.set(treino_payload, merge=True)

            # Validar e fechar a flag no Supabase para não repetir o registo
            supabase.table("strava_activities_metadata") \
                    .update({"synced_to_firestore": True}) \
                    .eq("id_virtual", id_virtual) \
                    .execute()
            
            sync_count += 1
            print(f"   ↳ [ID: {id_virtual}] Workout synced as DRAFT to Firestore.")

        print(f"🏁 Sync complete. Successfully mirrored {sync_count} workouts to Firestore.")

    except Exception as e:
        print(f"❌ Critical error during batch execution: {e}")

if __name__ == "__main__":
    run_batch_sync()
