import os
import json
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# ==========================================
# 1. INICIALIZAÇÃO DO FIRESTORE
# ==========================================
firebase_secret = os.getenv("FIREBASE_SERVICE_ACCOUNT")
if not firebase_secret:
    raise Exception("Missing FIREBASE_SERVICE_ACCOUNT environment variable.")

cred_dict = json.loads(firebase_secret)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# 2. DADOS DOS DOCUMENTOS AFETADOS (JSON)
# ==========================================
DATA_AFETADOS = [
  
  { "id_virtual": "", "user_id_afetado": "", "nome_no_movera": "" }
]

# ==========================================
# 3. PROCESSO DE REMOÇÃO SELETA (SÓ DRAFTS)
# ==========================================
def purge_corrupted_drafts():
    print(f"🧹 Starting Firestore cleanup for {len(DATA_AFETADOS)} workouts (Safe Mode)...")
    success_count = 0
    protected_count = 0
    skipped_count = 0

    for item in DATA_AFETADOS:
        user_id = item["user_id_afetado"]
        id_virtual = item["id_virtual"]
        nome_user = item["nome_no_movera"]

        try:
            doc_ref = db.collection("users").document(user_id) \
                        .collection("treinos").document(id_virtual)
            
            doc_snapshot = doc_ref.get()
            
            if doc_snapshot.exists:
                doc_data = doc_snapshot.to_dict() or {}
                status_atual = doc_data.get("status")

                # 🔒 BARREIRA DE SEGURANÇA: Só apaga se for estritamente 'draft'
                if status_atual == "draft":
                    doc_ref.delete()
                    print(f"   🗑️ [DELETED] Workout {id_virtual} (status: draft) removed from user '{nome_user}'")
                    success_count += 1
                else:
                    # Se o utilizador já validou o treino na app, o status mudou. Protegemos o registo!
                    print(f"   🛡️ [PROTECTED] Workout {id_virtual} skipped. Status is '{status_atual}' for user '{nome_user}'")
                    protected_count += 1
            else:
                print(f"   ℹ️ [SKIPPED] Workout {id_virtual} not found on Firestore for '{nome_user}'.")
                skipped_count += 1
                
        except Exception as err:
            print(f"   ❌ [ERROR] Failed to verify/delete workout {id_virtual} for user {nome_user}: {err}")

    print("\n🏁 Cleanup process finished!")
    print(f"   ↳ Total deleted (drafts): {success_count}")
    print(f"   ↳ Total protected (user updated): {protected_count}")
    print(f"   ↳ Total skipped (not found): {skipped_count}")

if __name__ == "__main__":
    purge_corrupted_drafts()
