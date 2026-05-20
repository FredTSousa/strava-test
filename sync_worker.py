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

# Inicializa Firebase usando o Secret do GitHub
firebase_secret = os.getenv("FIREBASE_SERVICE_ACCOUNT")
if not firebase_secret:
    raise Exception("Missing FIREBASE_SERVICE_ACCOUNT environment variable.")

cred_dict = json.loads(firebase_secret)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)

db_firestore = firestore.client()



# ==========================================
# 2. LOGICA DE SYNC DE TREINOS (MODO TESTE RESTREITO)
# ==========================================

def run_batch_sync():
    print("🚀 Starting Supabase to Firestore workouts sync (Restricted Test Mode: My User Only)...")
    
    try:
        # Puxar metadados do Supabase elegíveis (com user atribuído e por sincronizar)
        resposta_meta = supabase.table("strava_activities_metadata") \
            .select("id_virtual, assigned_firestore_user_id") \
            .not_.is_("assigned_firestore_user_id", "null") \
            .eq("synced_to_firestore", False) \
            .execute()
        
        atividades_pendentes = resposta_meta.data
        
        if not atividades_pendentes:
            print("✨ No pending workouts to sync.")
            return

        print(f"📦 Found {len(atividades_pendentes)} total pending workouts in database.")
        sync_count = 0

        for registo in atividades_pendentes:
            id_virtual = registo["id_virtual"]
            user_id = registo["assigned_firestore_user_id"]

          

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
            if not raw:
                print(f"⚠️ Warning: raw_json field is empty for activity {id_virtual}. Skipping...")
                continue

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
                "criadoEm": firestore.SERVER_TIMESTAMP,
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
                "status": "draft"  # Mantém a regra de rascunho
            }

            try:
                # Envia estritamente para a tua coleção no Firestore
                treino_ref = db_firestore.collection("users").document(user_id) \
                                         .collection("treinos").document(id_virtual)
                
                treino_ref.set(treino_payload, merge=True)

                # Fecha a flag no Supabase apenas para este treino teu processado
                supabase.table("strava_activities_metadata") \
                        .update({"synced_to_firestore": True}) \
                        .eq("id_virtual", id_virtual) \
                        .execute()
                
                sync_count += 1
                print(f"   ↳ [ID: {id_virtual}] Workout successfully synced to your profile as DRAFT.")

            except Exception as item_error:
                print(f"❌ Error syncing specific workout {id_virtual} for you: {item_error}")
                continue

        print(f"🏁 Sync complete. Successfully mirrored {sync_count} of your workouts to Firestore.")

    except Exception as e:
        print(f"❌ Critical error during batch execution: {e}")

if __name__ == "__main__":
    run_batch_sync()
