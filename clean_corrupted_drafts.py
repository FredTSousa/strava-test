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
  { "id_virtual": "55abca41792c5424d613a0b3e45853ce", "user_id_afetado": "ZMdA6FvXaQfGXjhti10Pi6dosjA3", "nome_no_movera": "Ana Cortes" },
  { "id_virtual": "37b3cb55832dc58421939b00255ed6c2", "user_id_afetado": "er4PHoP0GsPg46xF7uyK8ZGsVCO2", "nome_no_movera": "Filipe Lopes" },
  { "id_virtual": "1d9f5a62c73a8cb83c43cd33174848c6", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "b2c0c71c565690fe891e241918d00654", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "94cd9f5de43dd126bd49167c4b2c6cc5", "user_id_afetado": "LZEHgMkJBtZ3uu3AhH0gudeMNhi1", "nome_no_movera": "Rodrigo Correia" },
  { "id_virtual": "65e7dbe9a598851c13e57f93e95269ec", "user_id_afetado": "ZMdA6FvXaQfGXjhti10Pi6dosjA3", "nome_no_movera": "Ana Cortes" },
  { "id_virtual": "4d37aad406ba44288d997521648390e9", "user_id_afetado": "tp6ZGoULjHRZkh06TVGwTYXxhQo2", "nome_no_movera": "João Barreiros" },
  { "id_virtual": "d9cec90a1f713d94c4c07a9925785513", "user_id_afetado": "fEbHcGwXqpYUXxmbMyo6Pg2Qk9X2", "nome_no_movera": "Luís Neiva" },
  { "id_virtual": "f9a9ac5d3ac0c00570796d8968e4b97f", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "401fd1291c145f2096152527251a9eee", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "cb39d05ec0c39a85ee220d79b916e379", "user_id_afetado": "ZMdA6FvXaQfGXjhti10Pi6dosjA3", "nome_no_movera": "Ana Cortes" },
  { "id_virtual": "9b86da33e5ab4db3813d338c93ad13e5", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "a8e1864346eb9d14d117cd1edd1cdb55", "user_id_afetado": "LfU0lYQHVJZrn8X4xFYVuJl9r2r2", "nome_no_movera": "João Carvalho" },
  { "id_virtual": "94b9c3982dcfaa9237119836d833da78", "user_id_afetado": "4YaoAHXoTgfZGOA4bYaCwnobXX13", "nome_no_movera": "Luís Glória" },
  { "id_virtual": "63a3d87e34fea73940e5c20f725eb73c", "user_id_afetado": "h76NaMipz4T57JHm69UXvNgltxl2", "nome_no_movera": "Joana Sousa" },
  { "id_virtual": "9245e141f7850c433c711992e144d3cb", "user_id_afetado": "rxYn0NkFiaa3P9euyLUwOvT1WDB2", "nome_no_movera": "Zé Matias" },
  { "id_virtual": "83d72d64c0460104503784d67c8b10be", "user_id_afetado": "rxYn0NkFiaa3P9euyLUwOvT1WDB2", "nome_no_movera": "Zé Matias" },
  { "id_virtual": "13a7623544e80ef47fe3d7c76a6a7e1e", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "1cd285aaa978bc844fe651156d4acf60", "user_id_afetado": "LfU0lYQHVJZrn8X4xFYVuJl9r2r2", "nome_no_movera": "João Carvalho" },
  { "id_virtual": "217db3f1034e4a9c781db0b1cc72ca3b", "user_id_afetado": "k8kIvke9giaWpw9CzJrRuDj15s53", "nome_no_movera": "Diana oliveira" },
  { "id_virtual": "a2398e2b41d848aaa3fab7949f50b18a", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "ab724754170460cf189248a9e382a609", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "8560d80af7425810f00629ccb288e876", "user_id_afetado": "LZEHgMkJBtZ3uu3AhH0gudeMNhi1", "nome_no_movera": "Rodrigo Correia" },
  { "id_virtual": "9104cf884a7703507b5c59861ea6eb9b", "user_id_afetado": "ZMdA6FvXaQfGXjhti10Pi6dosjA3", "nome_no_movera": "Ana Cortes" },
  { "id_virtual": "bad8d3b5dc2fc49c3b57d7e8e8092cea", "user_id_afetado": "LZEHgMkJBtZ3uu3AhH0gudeMNhi1", "nome_no_movera": "Rodrigo Correia" },
  { "id_virtual": "9f1b74535a447095309bfedd60c7fe22", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "5e66309c1ca68641504c06fca81c3c1e", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "0c6c1d2c5ec0c407ed32f12ef9f7cdd1", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "c8d285bacee46733e61725014805a6dc", "user_id_afetado": "er4PHoP0GsPg46xF7uyK8ZGsVCO2", "nome_no_movera": "Filipe Lopes" },
  { "id_virtual": "de925a6750f1753202b9f2fdba960e28", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "7624f45616c15e0de73e916c8a0e82f9", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "962612dce1eb0d1fd05024aabb838243", "user_id_afetado": "4YaoAHXoTgfZGOA4bYaCwnobXX13", "nome_no_movera": "Luís Glória" },
  { "id_virtual": "b66a039228bbf291702c25fed9bca4cd", "user_id_afetado": "UIOoL8BaP4W3a67RKRZE26jpFmF3", "nome_no_movera": "Andreia candeias" },
  { "id_virtual": "3e95d046fa5a05bf521efe6cf93d16ce", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "d092a30d7a364589225d4a95a95769a4", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "1901afc795344dfbc8334a28fd0888a1", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "5eb07ecde81ac7546c63078e03f17874", "user_id_afetado": "vtLVjWi2boZFwEiTCeLRTVG3wX13", "nome_no_movera": "João Mergulho" },
  { "id_virtual": "38961841d72b5c1f7587638e83464945", "user_id_afetado": "h76NaMipz4T57JHm69UXvNgltxl2", "nome_no_movera": "Joana Sousa" },
  { "id_virtual": "90e6d810b04d0c5a95de7777d024ea6a", "user_id_afetado": "98Sr5umkRaNbCthoEtTJ52a23rI3", "nome_no_movera": "Nuno Martinho" },
  { "id_virtual": "defe867ee571c05d9b42cceef57206b9", "user_id_afetado": "LfU0lYQHVJZrn8X4xFYVuJl9r2r2", "nome_no_movera": "João Carvalho" },
  { "id_virtual": "bc604b2c04ee54f5e8336ab2f956242d", "user_id_afetado": "ZMdA6FvXaQfGXjhti10Pi6dosjA3", "nome_no_movera": "Ana Cortes" },
  { "id_virtual": "01be1cf47beda426b142419752c9ef7b", "user_id_afetado": "9omPQpHAuNPLfYJEPasOSMOAs943", "nome_no_movera": "Andreia Isabel Paulo" },
  { "id_virtual": "57c2a42cfca3884b4787a243b49eb08c", "user_id_afetado": "9omPQpHAuNPLfYJEPasOSMOAs943", "nome_no_movera": "Andreia Isabel Paulo" },
  { "id_virtual": "45b1df49f66985cb7ce6f819e7f38d5f", "user_id_afetado": "9omPQpHAuNPLfYJEPasOSMOAs943", "nome_no_movera": "Andreia Isabel Paulo" },
  { "id_virtual": "b28b788f6a693fa982176b52534e0844", "user_id_afetado": "9omPQpHAuNPLfYJEPasOSMOAs943", "nome_no_movera": "Andreia Isabel Paulo" },
  { "id_virtual": "0dcb444bc88155e09ff48db308a2f1fb", "user_id_afetado": "tp6ZGoULjHRZkh06TVGwTYXxhQo2", "nome_no_movera": "João Barreiros" },
  { "id_virtual": "215c552d67013da5e3867e28a4dae88b", "user_id_afetado": "tp6ZGoULjHRZkh06TVGwTYXxhQo2", "nome_no_movera": "João Barreiros" },
  { "id_virtual": "4aab2a67d0d951311ee98fd1602834b5", "user_id_afetado": "tp6ZGoULjHRZkh06TVGwTYXxhQo2", "nome_no_movera": "João Barreiros" }
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
