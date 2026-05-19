import os
import json
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

def sync_users():
    print("🚀 Starting Firestore to Supabase users sync...")
    
    # 1. Puxar utilizadores do Firestore
    # NOTA: Altera 'users' para o nome exato da tua coleção no Firestore
    users_ref = db_firestore.collection("users")
    docs = users_ref.stream()
    
    count = 0
    for doc in docs:
        user_data = doc.to_dict()
        user_id = doc.id # O UID gerado pelo Firebase Auth/Firestore
        
        # Mapeia os campos do teu Firestore para as colunas do Supabase
        email = user_data.get("email", "")
        # Tenta obter display_name ou name, dependendo de como guardas no Firebase
        display_name = user_data.get("display_name") or user_data.get("name") or "Unknown User"
        
        # 2. Faz Upsert no Supabase
        try:
            supabase.table("users_firestore").upsert({
                "id": user_id,
                "email": email,
                "display_name": display_name
            }).execute()
            count += 1
        except Exception as e:
            print(f"❌ Error syncing user {user_id}: {e}")
            
    print(f"🏁 Sync complete. Mirrored {count} users to Supabase.")

if __name__ == "__main__":
    sync_users()
