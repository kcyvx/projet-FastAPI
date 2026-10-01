import os
import unittest
from fastapi.testclient import TestClient
from main import app
from repositories.fake_repo import (
    FakeAccountRepository,
    FakeTransactionRepository,
    FakeBeneficiaryRepository,
    FakeUserRepository
)
import dependencies

class TestFastAPIBankingAPI(unittest.TestCase):
    def setUp(self):
        # Réinitialise les repositories Fake pour garantir l'indépendance de chaque test
        dependencies._fake_account_repo = FakeAccountRepository()
        dependencies._fake_transaction_repo = FakeTransactionRepository()
        dependencies._fake_beneficiary_repo = FakeBeneficiaryRepository()
        dependencies._fake_user_repo = FakeUserRepository()
        os.environ["TRANSFER_DELAY_SECONDS"] = "0"
        os.environ["USE_SQL"] = "false"
        os.environ["TASK_SCHEDULER_INTERVAL_SECONDS"] = "10.0"
        os.environ["CANCELLATION_TIMEOUT_SECONDS"] = "5.0"

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
            self.assertEqual(res_tx.json().get("status"), "pending")
            self.assertIsNotNone(res_tx.json().get("transaction_id"))

            # Application de la transaction via le TaskScheduler (apply_pending_transactions)
            from scheduler import apply_pending_transactions
            apply_pending_transactions(cancellation_timeout=0.0)

            # Vérification des soldes après exécution du scheduler
            info1 = client.get(f"/accounts/{acc1_id}", headers=headers1).json()
            info2 = client.get(f"/accounts/{acc2_id}", headers=headers2).json()
            self.assertEqual(info1.get("solde"), 150.0)
            self.assertEqual(info2.get("solde"), 50.0)

            # 8.2 Virement réussi vers son propre autre compte (User 1 vers User 1 bis)
            tx_payload_propre = {"source_id": acc1_id, "destinataire_id": acc1_bis_id, "montant": 25.0}
            res_tx_propre = client.post("/transactions", json=tx_payload_propre, headers=headers1)
            self.assertEqual(res_tx_propre.status_code, 200)
            self.assertEqual(res_tx_propre.json().get("status"), "pending")

            apply_pending_transactions(cancellation_timeout=0.0)
            info1_after = client.get(f"/accounts/{acc1_id}", headers=headers1).json()
            info1_bis = client.get(f"/accounts/{acc1_bis_id}", headers=headers1).json()
            self.assertEqual(info1_after.get("solde"), 125.0)
            self.assertEqual(info1_bis.get("solde"), 25.0)

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
        """Vérifie le stockage immédiat en pending et l'application après 5 secondes par le TaskScheduler."""
        from transaction.transaction import TransferStatus
        from scheduler import apply_pending_transactions
        import time

        os.environ["USE_SQL"] = "false"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"delay_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte A"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte B"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            # 1. Enregistrement immédiat avec statut pending
            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 40.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "pending")
            tx_id = res.json()["transaction_id"]

            tx_in_db = dependencies._fake_transaction_repo.get_by_id(tx_id)
            self.assertIsNotNone(tx_in_db)
            self.assertEqual(tx_in_db.statut, TransferStatus.PENDING.value)

            # 2. Avant expiration du délai (timeout=5.0s), le scheduler ne l'applique pas
            applied = apply_pending_transactions(cancellation_timeout=5.0)
            self.assertNotIn(tx_id, applied)
            self.assertEqual(tx_in_db.statut, TransferStatus.PENDING.value)

            # 3. Une fois le délai écoulé (timeout=0.0s pour le test), le scheduler l'applique
            applied_now = apply_pending_transactions(cancellation_timeout=0.0)
            self.assertIn(tx_id, applied_now)
            self.assertEqual(tx_in_db.statut, TransferStatus.APPROVED.value)

            info1 = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
            info2 = client.get(f"/accounts/{acc2['id']}", headers=headers).json()
            self.assertEqual(info1["solde"], 60.0)
            self.assertEqual(info2["solde"], 40.0)

    def test_transaction_cancel_during_floating_window(self):
        """Vérifie l'annulation d'une transaction pendant le délai de 5s et le refus après expiration."""
        from transaction.transaction import TransferStatus
        from scheduler import apply_pending_transactions
        from datetime import datetime, timezone, timedelta
        import time

        os.environ["USE_SQL"] = "false"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"cancel_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte Source"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte Dest"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 50.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            tx_id = res.json()["transaction_id"]

            # Annulation dans le délai de 5s : succès
            res_cancel = client.post(f"/transactions/{tx_id}/cancel", headers=headers)
            self.assertEqual(res_cancel.status_code, 200)
            self.assertEqual(res_cancel.json()["status"], "cancelled")

            # Le scheduler n'applique pas une transaction annulée
            apply_pending_transactions(cancellation_timeout=0.0)
            info = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
            self.assertEqual(info["solde"], 100.0)

            # Test du rejet si le délai de 5s est dépassé :
            res2 = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 20.0}, headers=headers)
            tx2_id = res2.json()["transaction_id"]
            tx2 = dependencies._fake_transaction_repo.get_by_id(tx2_id)
            # Simule une création datant de plus de 5s
            tx2.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)

            res_cancel_late = client.post(f"/transactions/{tx2_id}/cancel", headers=headers)
            self.assertEqual(res_cancel_late.status_code, 400)
            self.assertIn("dépassé", res_cancel_late.json()["detail"].lower())

    def test_transaction_floating_window_sql_mode(self):
        """Vérifie le stockage de la transaction pending directement en base SQLite et sa validation par le scheduler."""
        from transaction.transaction import TransferStatus, Transaction
        from sqlmodel import Session
        from db.db import engine
        from scheduler import apply_pending_transactions
        import time

        os.environ["USE_SQL"] = "true"

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
            self.assertEqual(res.json()["status"], "pending")
            tx_id = res.json()["transaction_id"]

            with Session(engine) as session:
                session.expire_all()
                tx_in_db = session.get(Transaction, tx_id)
                self.assertIsNotNone(tx_in_db)
                self.assertEqual(tx_in_db.statut, TransferStatus.PENDING.value)

            # Application par le TaskScheduler
            applied = apply_pending_transactions(cancellation_timeout=0.0)
            self.assertIn(tx_id, applied)

            with Session(engine) as session:
                session.expire_all()
                tx_in_db = session.get(Transaction, tx_id)
                self.assertEqual(tx_in_db.statut, TransferStatus.APPROVED.value)

            info1 = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
            self.assertEqual(info1["solde"], 60.0)

    def test_transaction_cancel_during_floating_window_sql_mode(self):
        """Vérifie l'annulation d'une transaction pendant le délai en mode SQL SQLite et rejet après 5s."""
        import time
        from datetime import datetime, timezone, timedelta
        from sqlmodel import Session
        from db.db import engine
        from transaction.transaction import Transaction, TransferStatus
        from scheduler import apply_pending_transactions

        os.environ["USE_SQL"] = "true"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"cancel_sql_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Compte SQL Source"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Compte SQL Dest"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 50.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            tx_id = res.json()["transaction_id"]

            res_cancel = client.post(f"/transactions/{tx_id}/cancel", headers=headers)
            self.assertEqual(res_cancel.status_code, 200)

            # Vérifie dans SQLite que la transaction est bien marquée CANCELLED
            with Session(engine) as session:
                session.expire_all()
                tx_in_db = session.get(Transaction, tx_id)
                self.assertEqual(tx_in_db.statut, TransferStatus.CANCELLED.value)

            apply_pending_transactions(cancellation_timeout=0.0)
            info = client.get(f"/accounts/{acc1['id']}", headers=headers)
            self.assertEqual(info.json()["solde"], 100.0)

            # Test délai dépassé (> 5s)
            res2 = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 20.0}, headers=headers)
            tx2_id = res2.json()["transaction_id"]
            with Session(engine) as session:
                tx2 = session.get(Transaction, tx2_id)
                tx2.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)
                session.add(tx2)
                session.commit()

            res_late = client.post(f"/transactions/{tx2_id}/cancel", headers=headers)
            self.assertEqual(res_late.status_code, 400)
            self.assertIn("dépassé", res_late.json()["detail"].lower())

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

    def test_story_13_transaction_detail(self):
        """Vérifie la Story 13 : consultation des détails d'une transaction."""
        import time
        os.environ["USE_SQL"] = "false"
        os.environ["TRANSFER_DELAY_SECONDS"] = "0"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            # Utilisateur 1 (émetteur)
            u1_email = f"u1_s13_{ts}@test.com"
            client.post("/register", json={"email": u1_email, "password": "Password123!"})
            t1 = client.post("/login", json={"email": u1_email, "password": "Password123!"}).json()["access_token"]
            h1 = {"Authorization": f"Bearer {t1}"}
            acc1_id = client.get("/accounts", headers=h1).json()[0]["id"]

            # Utilisateur 2 (destinataire)
            u2_email = f"u2_s13_{ts}@test.com"
            client.post("/register", json={"email": u2_email, "password": "Password123!"})
            t2 = client.post("/login", json={"email": u2_email, "password": "Password123!"}).json()["access_token"]
            h2 = {"Authorization": f"Bearer {t2}"}
            acc2_id = client.get("/accounts", headers=h2).json()[0]["id"]

            # Utilisateur 3 (tiers)
            u3_email = f"u3_s13_{ts}@test.com"
            client.post("/register", json={"email": u3_email, "password": "Password123!"})
            t3 = client.post("/login", json={"email": u3_email, "password": "Password123!"}).json()["access_token"]
            h3 = {"Authorization": f"Bearer {t3}"}

            # Effectuer un virement de U1 vers U2
            res_transfer = client.post("/transactions", json={"source_id": acc1_id, "destinataire_id": acc2_id, "montant": 25.0}, headers=h1)
            self.assertEqual(res_transfer.status_code, 200)
            tx_id = res_transfer.json()["transaction_id"]

            # 1. Émetteur (U1) peut consulter le détail
            res_detail_u1 = client.get(f"/transactions/{tx_id}", headers=h1)
            self.assertEqual(res_detail_u1.status_code, 200)
            self.assertEqual(res_detail_u1.json()["id"], tx_id)
            self.assertEqual(res_detail_u1.json()["montant"], 25.0)

            # 2. Destinataire (U2) peut aussi consulter le détail
            res_detail_u2 = client.get(f"/transactions/{tx_id}", headers=h2)
            self.assertEqual(res_detail_u2.status_code, 200)
            self.assertEqual(res_detail_u2.json()["id"], tx_id)

            # 3. Tiers non autorisé (U3) reçoit 403
            res_detail_u3 = client.get(f"/transactions/{tx_id}", headers=h3)
            self.assertEqual(res_detail_u3.status_code, 403)

            # 4. Transaction inexistante reçoit 404
            res_not_found = client.get("/transactions/999999", headers=h1)
            self.assertEqual(res_not_found.status_code, 404)

            # 5. Non authentifié reçoit 401
            res_no_auth = client.get(f"/transactions/{tx_id}")
            self.assertEqual(res_no_auth.status_code, 401)

    def test_story_12_close_account(self):
        """Vérifie la Story 12 : clôture d'un compte avec transfert du solde sur le compte principal."""
        import time
        os.environ["USE_SQL"] = "false"
        os.environ["TRANSFER_DELAY_SECONDS"] = "0"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            u_email = f"close_{ts}@test.com"
            client.post("/register", json={"email": u_email, "password": "Password123!"})
            token = client.post("/login", json={"email": u_email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Récupération du compte principal (solde initial 100€)
            accounts = client.get("/accounts", headers=headers).json()
            main_acc = next(a for a in accounts if a["is_main"])
            self.assertEqual(main_acc["solde"], 100.0)

            # Ouverture d'un compte secondaire (solde initial 0€)
            sec_acc = client.post("/accounts", json={"name": "Compte Épargne"}, headers=headers).json()["account"]
            self.assertEqual(sec_acc["solde"], 0.0)
            self.assertFalse(sec_acc["is_main"])

            # Dépôt de 50€ sur le compte secondaire
            client.post(f"/accounts/{sec_acc['id']}/deposit", json={"montant": 50.0}, headers=headers)
            sec_info = client.get(f"/accounts/{sec_acc['id']}", headers=headers).json()
            self.assertEqual(sec_info["solde"], 50.0)

            # Règle : Le compte principal ne peut pas être clôturé (400)
            res_close_main = client.post(f"/accounts/{main_acc['id']}/close", headers=headers)
            self.assertEqual(res_close_main.status_code, 400)
            self.assertIn("principal", res_close_main.json()["detail"])

            # Clôture du compte secondaire
            res_close = client.post(f"/accounts/{sec_acc['id']}/close", headers=headers)
            self.assertEqual(res_close.status_code, 200)
            self.assertEqual(res_close.json()["transferred_amount"], 50.0)
            self.assertEqual(res_close.json()["main_account_new_solde"], 150.0)
            self.assertTrue(res_close.json()["is_closed"])

            # Règle : Un compte clôturé ne peut plus être consulté via /accounts (il disparaît de la liste)
            accounts_after = client.get("/accounts", headers=headers).json()
            account_ids_after = [a["id"] for a in accounts_after]
            self.assertNotIn(sec_acc["id"], account_ids_after)
            self.assertIn(main_acc["id"], account_ids_after)

            # Règle : Un compte clôturé ne peut plus être consulté individuellement (404)
            res_get_closed = client.get(f"/accounts/{sec_acc['id']}", headers=headers)
            self.assertEqual(res_get_closed.status_code, 404)

            # Règle : Impossible de déposer sur un compte clôturé (400)
            res_dep_closed = client.post(f"/accounts/{sec_acc['id']}/deposit", json={"montant": 10.0}, headers=headers)
            self.assertEqual(res_dep_closed.status_code, 400)

            # Règle : Impossible de faire un virement depuis un compte clôturé (400)
            res_tx_closed = client.post("/transactions", json={"source_id": sec_acc["id"], "destinataire_id": main_acc["id"], "montant": 10.0}, headers=headers)
            self.assertEqual(res_tx_closed.status_code, 400)

    def test_story_14_add_beneficiary(self):
        import time 
        os.environ["USE_SQL"] = "false"
        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            u1_email = f"alice_b_{ts}@test.com"
            client.post("/register", json={"email": u1_email, "password": "Password123!"})
            t1 = client.post("/login", json={"email": u1_email, "password": "Password123!"}).json()["access_token"]
            h1 = {"Authorization": f"Bearer {t1}"}
            acc1_id = client.get("/accounts", headers=h1).json()[0]["id"]

            u2_email = f"bob_b_{ts}@test.com"
            client.post("/register", json={"email": u2_email, "password": "Password123!"})
            t2 = client.post("/login", json={"email": u2_email, "password": "Password123!"}).json()["access_token"]
            h2 = {"Authorization": f"Bearer {t2}"}
            acc2_id = client.get("/accounts", headers=h2).json()[0]["id"]

            # 1. Ajout valide
            res_add = client.post("/beneficiaries", json={"account_id": acc2_id, "name": "Bob Ami"}, headers=h1)
            self.assertEqual(res_add.status_code, 201)
            self.assertEqual(res_add.json()["beneficiary"]["name"], "Bob Ami")

            # 2. Interdiction d'ajouter son propre compte (400)
            res_self = client.post("/beneficiaries", json={"account_id": acc1_id, "name": "Moi-meme"}, headers=h1)
            self.assertEqual(res_self.status_code, 400)

            # 3. Compte inexistant (404)
            res_not_found = client.post("/beneficiaries", json={"account_id": "00000000-0000-0000-0000-000000000000", "name": "Fantome"}, headers=h1)
            self.assertEqual(res_not_found.status_code, 404)

            # 4. Doublon interdit (400)
            res_dup = client.post("/beneficiaries", json={"account_id": acc2_id, "name": "Bob Bis"}, headers=h1)
            self.assertEqual(res_dup.status_code, 400)

            # 5. Nom invalide (400 ou 422)
            res_empty_space = client.post("/beneficiaries", json={"account_id": acc2_id, "name": "   "}, headers=h1)
            self.assertEqual(res_empty_space.status_code, 400)
            res_empty_str = client.post("/beneficiaries", json={"account_id": acc2_id, "name": ""}, headers=h1)
            self.assertEqual(res_empty_str.status_code, 422)

            # 6. Non authentifié (401)
            res_no_auth = client.post("/beneficiaries", json={"account_id": acc2_id, "name": "Inconnu"})
            self.assertEqual(res_no_auth.status_code, 401)

    def test_story_15_get_beneficiaries(self):
        import time
        os.environ["USE_SQL"] = "false"
        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            u1_email = f"u1_s15_{ts}@test.com"
            client.post("/register", json={"email": u1_email, "password": "Password123!"})
            t1 = client.post("/login", json={"email": u1_email, "password": "Password123!"}).json()["access_token"]
            h1 = {"Authorization": f"Bearer {t1}"}

            u2_email = f"u2_s15_{ts}@test.com"
            client.post("/register", json={"email": u2_email, "password": "Password123!"})
            t2 = client.post("/login", json={"email": u2_email, "password": "Password123!"}).json()["access_token"]
            h2 = {"Authorization": f"Bearer {t2}"}
            acc2_id = client.get("/accounts", headers=h2).json()[0]["id"]

            res_empty = client.get("/beneficiaries", headers=h1)
            self.assertEqual(res_empty.status_code, 200)
            self.assertEqual(res_empty.json(), [])

            client.post("/beneficiaries", json={"account_id": acc2_id, "name": "Bénéficiaire 1"}, headers=h1)

            res_list = client.get("/beneficiaries", headers=h1)
            self.assertEqual(res_list.status_code, 200)
            beneficiaries = res_list.json()
            self.assertEqual(len(beneficiaries), 1)

            item = beneficiaries[0]
            self.assertIn("id", item)
            self.assertEqual(item["name"], "Bénéficiaire 1")
            self.assertEqual(item["account_id"], acc2_id)
            self.assertIn("created_at", item)

            res_other_user = client.get("/beneficiaries", headers=h2)
            self.assertEqual(res_other_user.status_code, 200)
            self.assertEqual(res_other_user.json(), [])

            res_no_auth = client.get("/beneficiaries")
            self.assertEqual(res_no_auth.status_code, 401)

    def test_accounts_ordered_by_created_at_desc(self):
        """Vérifie que les comptes retournés par GET /accounts sont triés par created_at décroissant (Fake et SQL)."""
        import time

        for use_sql in (False, True):
            os.environ["USE_SQL"] = "true" if use_sql else "false"
            dependencies._fake_account_repo = FakeAccountRepository()
            dependencies._fake_transaction_repo = FakeTransactionRepository()
            dependencies._fake_beneficiary_repo = FakeBeneficiaryRepository()
            dependencies._fake_user_repo = FakeUserRepository()

            with TestClient(app) as client:
                ts = int(time.time() * 1000)
                email = f"order_{use_sql}_{ts}@test.com"
                client.post("/register", json={"email": email, "password": "Password123!"})
                token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                # Création de 2 comptes supplémentaires
                time.sleep(0.01)
                res_c1 = client.post("/accounts", json={"name": "Compte 1"}, headers=headers)
                self.assertEqual(res_c1.status_code, 201)
                c1_id = res_c1.json()["account"]["id"]

                time.sleep(0.01)
                res_c2 = client.post("/accounts", json={"name": "Compte 2"}, headers=headers)
                self.assertEqual(res_c2.status_code, 201)
                c2_id = res_c2.json()["account"]["id"]

                # Récupération des comptes
                res_list = client.get("/accounts", headers=headers)
                self.assertEqual(res_list.status_code, 200)
                accounts = res_list.json()

                self.assertGreaterEqual(len(accounts), 3)
                # Le plus récent (Compte 2) doit être en premier
                self.assertEqual(accounts[0]["id"], c2_id)
                self.assertEqual(accounts[1]["id"], c1_id)

                # Vérification de la présence du champ created_at
                for acc in accounts:
                    self.assertIn("created_at", acc)

                # Vérification que chaque date est >= à la suivante
                for i in range(len(accounts) - 1):
                    self.assertGreaterEqual(accounts[i]["created_at"], accounts[i + 1]["created_at"])

    def test_story_10_task_scheduler_auto_apply(self):
        """Vérifie l'exécution automatique en tâche de fond du TaskScheduler (cronjob) sans appel manuel."""
        import time
        from transaction.transaction import TransferStatus

        os.environ["USE_SQL"] = "false"
        os.environ["TASK_SCHEDULER_INTERVAL_SECONDS"] = "0.05"
        os.environ["CANCELLATION_TIMEOUT_SECONDS"] = "0.05"

        with TestClient(app) as client:
            ts = int(time.time() * 1000)
            email = f"scheduler_{ts}@test.com"
            client.post("/register", json={"email": email, "password": "Password123!"})
            token = client.post("/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            acc1 = client.post("/accounts", json={"name": "Source Auto"}, headers=headers).json()["account"]
            acc2 = client.post("/accounts", json={"name": "Dest Auto"}, headers=headers).json()["account"]
            client.post(f"/accounts/{acc1['id']}/deposit", json={"montant": 100.0}, headers=headers)

            res = client.post("/transactions", json={"source_id": acc1["id"], "destinataire_id": acc2["id"], "montant": 30.0}, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "pending")
            tx_id = res.json()["transaction_id"]

            # Laisser le temps à la tâche d'arrière-plan TaskScheduler de tourner
            time.sleep(0.15)

            tx_in_db = dependencies._fake_transaction_repo.get_by_id(tx_id)
            self.assertEqual(tx_in_db.statut, TransferStatus.APPROVED.value)

            info1 = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
            self.assertEqual(info1["solde"], 70.0)

if __name__ == "__main__":
    unittest.main()
