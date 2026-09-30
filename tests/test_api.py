import os
import unittest
from fastapi.testclient import TestClient
from main import app
from repositories.fake_repo import FakeAccountRepository, FakeUserRepository
import dependencies

class TestFastAPIBankingAPI(unittest.TestCase):
    def setUp(self):
        # Réinitialise les repositories Fake pour garantir l'indépendance de chaque test
        dependencies._fake_account_repo = FakeAccountRepository()
        dependencies._fake_user_repo = FakeUserRepository()
        os.environ["TRANSFER_DELAY_SECONDS"] = "0"

    def _execute_full_suite(self, mode_name: str, use_sql: bool):
        os.environ["USE_SQL"] = "true" if use_sql else "false"

        with TestClient(app) as client:
            import time
            ts = int(time.time() * 1000)
            prefix = f"{mode_name}_{ts}_"
            user1_email = f"{prefix}alice@test.com"
            user2_email = f"{prefix}bob@test.com"
            pwd = "SecretPassword123!"

            # ---------------------------------------------------------
            # 1. POST /register
            # ---------------------------------------------------------
            res = client.post("/register", json={"email": user1_email, "password": pwd})
            self.assertEqual(res.status_code, 200, f"Register failed: {res.text}")
            self.assertEqual(res.json().get("email"), user1_email)
            user1_id = res.json().get("user_id")

            # Duplicate email rejection
            res_dup = client.post("/register", json={"email": user1_email, "password": pwd})
            self.assertEqual(res_dup.status_code, 400)

            # Register user 2
            res2 = client.post("/register", json={"email": user2_email, "password": pwd})
            self.assertEqual(res2.status_code, 200)
            user2_id = res2.json().get("user_id")

            # ---------------------------------------------------------
            # 2. POST /login
            # ---------------------------------------------------------
            res_login1 = client.post("/login", json={"email": user1_email, "password": pwd})
            self.assertEqual(res_login1.status_code, 200)
            token1 = res_login1.json().get("access_token")
            self.assertIsNotNone(token1)

            res_login2 = client.post("/login", json={"email": user2_email, "password": pwd})
            self.assertEqual(res_login2.status_code, 200)
            token2 = res_login2.json().get("access_token")
            self.assertIsNotNone(token2)

            res_wrong_pwd = client.post("/login", json={"email": user1_email, "password": "WrongPassword"})
            self.assertEqual(res_wrong_pwd.status_code, 400)

            res_nonexistent = client.post("/login", json={"email": f"{prefix}nobody@test.com", "password": pwd})
            self.assertEqual(res_nonexistent.status_code, 400)

            headers1 = {"Authorization": f"Bearer {token1}"}
            headers2 = {"Authorization": f"Bearer {token2}"}

            # ---------------------------------------------------------
            # 3. GET /me
            # ---------------------------------------------------------
            res_me1 = client.get("/me", headers=headers1)
            self.assertEqual(res_me1.status_code, 200)
            self.assertEqual(res_me1.json().get("id"), user1_id)

            res_me_no_token = client.get("/me")
            self.assertEqual(res_me_no_token.status_code, 401)

            res_me_bad_token = client.get("/me", headers={"Authorization": "Bearer bad_token_12345"})
            self.assertEqual(res_me_bad_token.status_code, 401)

            # ---------------------------------------------------------
            # 4. POST /accounts (Sécurisé avec get_current_user)
            # ---------------------------------------------------------
            res_acc1 = client.post("/accounts", json={"name": "Compte Principal Alice"}, headers=headers1)
            self.assertEqual(res_acc1.status_code, 201)
            self.assertEqual(res_acc1.json()["account"]["solde"], 0.0)
            self.assertEqual(res_acc1.json()["account"]["user_id"], user1_id)
            acc1_id = res_acc1.json()["account"]["id"]

            res_acc2 = client.post("/accounts", json={"name": "Compte Principal Bob"}, headers=headers2)
            self.assertEqual(res_acc2.status_code, 201)
            self.assertEqual(res_acc2.json()["account"]["solde"], 0.0)
            self.assertEqual(res_acc2.json()["account"]["user_id"], user2_id)
            acc2_id = res_acc2.json()["account"]["id"]

            res_acc_no_auth = client.post("/accounts", json={"name": "Compte Anonyme"})
            self.assertEqual(res_acc_no_auth.status_code, 401)

            # ---------------------------------------------------------
            # 5. GET /accounts (Filtré par utilisateur connecté)
            # ---------------------------------------------------------
            res_list_acc1 = client.get("/accounts", headers=headers1)
            self.assertEqual(res_list_acc1.status_code, 200)
            acc_ids_user1 = [a["id"] for a in res_list_acc1.json()]
            self.assertIn(acc1_id, acc_ids_user1)
            self.assertNotIn(acc2_id, acc_ids_user1)

            res_list_no_auth = client.get("/accounts")
            self.assertEqual(res_list_no_auth.status_code, 401)

            # ---------------------------------------------------------
            # 6. POST /accounts/{account_id}/deposit (Story 5: DepositRequest + Transaction)
            # ---------------------------------------------------------
            res_dep1 = client.post(f"/accounts/{acc1_id}/deposit", json={"montant": 200.0}, headers=headers1)
            self.assertEqual(res_dep1.status_code, 200)
            self.assertEqual(res_dep1.json().get("nouveau_solde"), 200.0)
            self.assertIsNotNone(res_dep1.json().get("transaction_id"))
            self.assertIsNotNone(res_dep1.json().get("date"))

            # Dépôt interdit par un non-propriétaire (403)
            res_dep_forbidden = client.post(f"/accounts/{acc1_id}/deposit", json={"montant": 50.0}, headers=headers2)
            self.assertEqual(res_dep_forbidden.status_code, 403)

            # Dépôt sur compte inexistant (404)
            res_dep_not_found = client.post("/accounts/999999/deposit", json={"montant": 50.0}, headers=headers1)
            self.assertEqual(res_dep_not_found.status_code, 404)

            # Dépôt avec montant négatif (422 Pydantic Field gt=0)
            res_dep_invalid_amt = client.post(f"/accounts/{acc1_id}/deposit", json={"montant": -10.0}, headers=headers1)
            self.assertEqual(res_dep_invalid_amt.status_code, 422)

            # Dépôt avec montant zéro (422 Pydantic Field gt=0)
            res_dep_zero = client.post(f"/accounts/{acc1_id}/deposit", json={"montant": 0.0}, headers=headers1)
            self.assertEqual(res_dep_zero.status_code, 422)

            # ---------------------------------------------------------
            # 7. GET /accounts/{account_id}
            # ---------------------------------------------------------
            res_info1 = client.get(f"/accounts/{acc1_id}", headers=headers1)
            self.assertEqual(res_info1.status_code, 200)
            self.assertEqual(res_info1.json().get("solde"), 200.0)

            res_info_forbidden = client.get(f"/accounts/{acc1_id}", headers=headers2)
            self.assertEqual(res_info_forbidden.status_code, 403)

            res_info_not_found = client.get("/accounts/999999", headers=headers1)
            self.assertEqual(res_info_not_found.status_code, 404)

            # ---------------------------------------------------------
            # 8. POST /transactions (Virement sécurisé)
            # ---------------------------------------------------------
            # Création d'un second compte pour User 1 pour tester virement vers son propre compte
            res_acc1_bis = client.post("/accounts", json={"name": "Compte Epargne Alice"}, headers=headers1)
            self.assertEqual(res_acc1_bis.status_code, 201)
            acc1_bis_id = res_acc1_bis.json()["account"]["id"]

            # 8.1 Virement réussi vers un tiers (User 1 vers User 2)
            tx_payload_tiers = {"source_id": acc1_id, "destinataire_id": acc2_id, "montant": 50.0}
            res_tx = client.post("/transactions", json=tx_payload_tiers, headers=headers1)
            self.assertEqual(res_tx.status_code, 200)
            self.assertEqual(res_tx.json().get("sender_new_solde"), 150.0)
            self.assertEqual(res_tx.json().get("receiver_new_solde"), 50.0)

            # 8.2 Virement réussi vers son propre autre compte (User 1 vers User 1 bis)
            tx_payload_propre = {"source_id": acc1_id, "destinataire_id": acc1_bis_id, "montant": 25.0}
            res_tx_propre = client.post("/transactions", json=tx_payload_propre, headers=headers1)
            self.assertEqual(res_tx_propre.status_code, 200)
            self.assertEqual(res_tx_propre.json().get("sender_new_solde"), 125.0)
            self.assertEqual(res_tx_propre.json().get("receiver_new_solde"), 25.0)

            # 8.3 Virement sans authentification (401)
            res_tx_no_auth = client.post("/transactions", json=tx_payload_tiers)
            self.assertEqual(res_tx_no_auth.status_code, 401)

            # 8.4 Virement depuis le compte d'un tiers interdit (User 1 tente de débiter le compte de User 2) (403)
            tx_payload_vol = {"source_id": acc2_id, "destinataire_id": acc1_id, "montant": 10.0}
            res_tx_forbidden = client.post("/transactions", json=tx_payload_vol, headers=headers1)
            self.assertEqual(res_tx_forbidden.status_code, 403)

            # 8.5 Virement vers le même compte (400)
            tx_same = {"source_id": acc1_id, "destinataire_id": acc1_id, "montant": 10.0}
            res_tx_same = client.post("/transactions", json=tx_same, headers=headers1)
            self.assertEqual(res_tx_same.status_code, 400)

            # 8.6 Destinataire inexistant (404)
            tx_not_found = {"source_id": acc1_id, "destinataire_id": "999999", "montant": 10.0}
            res_tx_not_found = client.post("/transactions", json=tx_not_found, headers=headers1)
            self.assertEqual(res_tx_not_found.status_code, 404)

            # 8.7 Solde insuffisant (400)
            tx_overdraft = {"source_id": acc1_id, "destinataire_id": acc2_id, "montant": 999999.0}
            res_tx_overdraft = client.post("/transactions", json=tx_overdraft, headers=headers1)
            self.assertEqual(res_tx_overdraft.status_code, 400)

            # 8.8 Montant négatif ou nul (422 via Pydantic gt=0)
            tx_negative = {"source_id": acc1_id, "destinataire_id": acc2_id, "montant": -20.0}
            res_tx_negative = client.post("/transactions", json=tx_negative, headers=headers1)
            self.assertIn(res_tx_negative.status_code, (400, 422))

            tx_zero = {"source_id": acc1_id, "destinataire_id": acc2_id, "montant": 0.0}
            res_tx_zero = client.post("/transactions", json=tx_zero, headers=headers1)
            self.assertIn(res_tx_zero.status_code, (400, 422))

    def test_transaction_floating_window_and_pending_dict(self):
        """Vérifie le stockage de la transaction pending en DB et sa validation après le délai."""
        from transaction.transaction import TransferStatus
        import time

        os.environ["USE_SQL"] = "false"
        os.environ["TRANSFER_DELAY_SECONDS"] = "0.2"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"delay_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte A"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte B"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 40.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["sender_new_solde"], 60.0)

            tx_id = res.json()["transaction_id"]
            tx_in_db = dependencies._fake_account_repo.get_transaction_by_id(tx_id)
            self.assertIsNotNone(tx_in_db)
            self.assertEqual(tx_in_db.statut, TransferStatus.APPROVED.value)

    def test_transaction_cancel_during_floating_window(self):
        """Vérifie l'annulation d'une transaction pendant le moment de flottement avec persistance en base."""
        import threading
        import time
        from transaction.transaction import TransferStatus

        os.environ["USE_SQL"] = "false"
        os.environ["TRANSFER_DELAY_SECONDS"] = "1.0"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"cancel_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte Source"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte Dest"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            def cancel_worker():
                time.sleep(0.2)
                res_pending = client.get("/transactions/pending", headers=headers)
                pending_txs = res_pending.json()
                if pending_txs:
                    client.post(f"/transactions/{pending_txs[0]['id']}/cancel", headers=headers)

            t = threading.Thread(target=cancel_worker)
            t.start()

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 50.0}, headers=headers)
            t.join()

            self.assertEqual(res.status_code, 400)
            self.assertIn("annulée", res.json()["detail"])

            info = client.get(f"/accounts/{acc1['id']}", headers=headers)
            self.assertEqual(info.json()["solde"], 100.0)

            # Vérifie que la transaction n'est plus en attente dans la base
            pending_in_db = dependencies._fake_account_repo.get_pending_transactions()
            self.assertEqual(len(pending_in_db), 0)

    def test_transaction_floating_window_sql_mode(self):
        """Vérifie le stockage de la transaction pending directement en base SQLite et sa validation."""
        from transaction.transaction import TransferStatus
        from sqlmodel import Session
        from db.db import engine
        from transaction.transaction import Transaction
        import time

        os.environ["USE_SQL"] = "true"
        os.environ["TRANSFER_DELAY_SECONDS"] = "0.2"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"delay_sql_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte SQL A"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte SQL B"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 40.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["sender_new_solde"], 60.0)

            tx_id = res.json()["transaction_id"]
            with Session(engine) as session:
                session.expire_all()
                tx_in_db = session.get(Transaction, tx_id)
                self.assertIsNotNone(tx_in_db)
                self.assertEqual(tx_in_db.statut, TransferStatus.APPROVED.value)

    def test_transaction_cancel_during_floating_window_sql_mode(self):
        """Vérifie l'annulation d'une transaction pendant le moment de flottement en mode SQL SQLite."""
        import threading
        import time
        from sqlmodel import Session
        from db.db import engine
        from transaction.transaction import Transaction, TransferStatus

        os.environ["USE_SQL"] = "true"
        os.environ["TRANSFER_DELAY_SECONDS"] = "1.0"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"cancel_sql_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte SQL Source"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte SQL Dest"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            def cancel_worker():
                time.sleep(0.2)
                res_pending = client.get("/transactions/pending", headers=headers)
                pending_txs = res_pending.json()
                if pending_txs:
                    client.post(f"/transactions/{pending_txs[0]['id']}/cancel", headers=headers)

            t = threading.Thread(target=cancel_worker)
            t.start()

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 50.0}, headers=headers)
            t.join()

            self.assertEqual(res.status_code, 400)
            self.assertIn("annulée", res.json()["detail"])

            info = client.get(f"/accounts/{acc1['id']}", headers=headers)
            self.assertEqual(info.json()["solde"], 100.0)

            # Vérifie dans SQLite que la transaction est bien marquée CANCELLED
            with Session(engine) as session:
                session.expire_all()
                pending_txs = client.get("/transactions/pending", headers=headers).json()
                self.assertNotIn(acc1["id"], [p.get("source_id") for p in pending_txs])

    def test_all_routes_fake_mode(self):
        """Teste toutes les routes en mode mémoire (Fake repositories)."""
        self._execute_full_suite("fake", use_sql=False)

    def test_all_routes_sql_mode(self):
        """Teste toutes les routes en mode base de données SQL (SQLite)."""
        self._execute_full_suite("sql", use_sql=True)

    def test_story_11_automatic_main_account(self):
        """Vérifie la Story 11 : création automatique d'un compte principal crédité de 100€ à l'inscription."""
        import time
        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"story11_{ts}@test.com"
            res = client.post("/register", json={"email": email, "password": "Password123!"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("account", data)
            self.assertEqual(data["account"]["solde"], 100.0)
            self.assertTrue(data["account"]["is_main"])

            # Vérifie également via /login et /accounts
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            accounts_res = client.get("/accounts", headers=headers)
            self.assertEqual(accounts_res.status_code, 200)
            user_accounts = accounts_res.json()
            self.assertEqual(len(user_accounts), 1)
            self.assertEqual(user_accounts[0]["solde"], 100.0)
            self.assertTrue(user_accounts[0]["is_main"])

if __name__ == "__main__":
    unittest.main()
