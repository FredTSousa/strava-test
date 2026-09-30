import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from supabase import create_client, Client

load_dotenv()

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

# 🟢 Modo incremental: se definido, só lê os utilizadores criados nas últimas N horas
# (cada doc lido no Firestore é faturado, por isso não se faz scan completo a cada sync).
# Sem esta variável faz o scan completo (corrida diária), que também apanha edições,
# docs sem 'criadoEm' e qualquer utilizador perdido enquanto o pipeline esteve parado.
LOOKBACK_HOURS = os.getenv("FIRESTORE_USERS_LOOKBACK_HOURS")
UPSERT_CHUNK_SIZE = 500

def build_row(doc):
    user_data = doc.to_dict()
    user_id = doc.id # O UID gerado pelo Firebase Auth/Firestore

    # Mapeia os campos do teu Firestore para as colunas do Supabase
    email = user_data.get("email", "")
    # Tenta obter display_name ou name, dependendo de como guardas no Firebase
    display_name = user_data.get("display_name") or user_data.get("nome") or "Unknown User"
    # TRATAMENTO DA DATA DO FIRESTORE:
    creation_date_raw = user_data.get("criadoEm")
    creation_date_iso = None

    if creation_date_raw:
        try:
            # Se for um objeto datetime do Firebase/Python, converte para String ISO
            if hasattr(creation_date_raw, "isoformat"):
                creation_date_iso = creation_date_raw.isoformat()
            else:
                # Caso já venha como string por algum motivo
                creation_date_iso = str(creation_date_raw)
        except Exception as dt_err:
            print(f"⚠️ Warning: Could not parse date for user {user_id}: {dt_err}")

    # Só estas colunas: o upsert não mexe no athlete_id atribuído pelo dashboard
    return {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "created_at_firestore": creation_date_iso
    }

def sync_users():
    # 1. Puxar utilizadores do Firestore
    # NOTA: Altera 'users' para o nome exato da tua coleção no Firestore
    users_ref = db_firestore.collection("users")

    if LOOKBACK_HOURS:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=float(LOOKBACK_HOURS))
        print(f"🚀 Starting incremental Firestore to Supabase users sync (criadoEm >= {cutoff.isoformat()})...")
        docs = users_ref.where(filter=firestore.FieldFilter("criadoEm", ">=", cutoff)).stream()
    else:
        print("🚀 Starting full Firestore to Supabase users sync...")
        docs = users_ref.stream()

    rows = [build_row(doc) for doc in docs]

    # 2. Faz Upsert no Supabase em lotes (um pedido por lote, não um por utilizador)
    for i in range(0, len(rows), UPSERT_CHUNK_SIZE):
        supabase.table("users_firestore").upsert(rows[i:i + UPSERT_CHUNK_SIZE]).execute()

    print(f"🏁 Sync complete. Mirrored {len(rows)} users to Supabase.")

if __name__ == "__main__":
    sync_users()
