import os
from typing import Optional, List
import jwt
from account.account import Account
from user.user import User, UserCreate, hash_password, verify_password
from transaction.transaction import Transaction, debit, credit

class FakeAccountRepository:
    def __init__(self):
        # Base en mémoire initialisée avec Alice et Bob
        self.accounts: dict[int, Account] = {
            1: Account(id=1, name="Alice", solde=100.0),
            2: Account(id=2, name="Bob", solde=100.0),
        }
        self.transactions: list[Transaction] = []

    def get_by_id(self, account_id: int) -> Optional[Account]:
        return self.accounts.get(account_id)

    def get_all(self) -> List[Account]:
        return list(self.accounts.values())

    def get_by_user_id(self, user_id: int) -> List[Account]:
        return [acc for acc in self.accounts.values() if acc.user_id == user_id]


    # --- NOUVELLE MÉTHODE US 4 ---
    def create(self, name: str, user_id: int) -> Account:
        new_id = max(self.accounts.keys(), default=0) + 1
        new_account = Account(
            id=new_id,
            name=name,
            solde=0.0,
            user_id=user_id
        )
        self.accounts[new_id] = new_account
        return new_account

    def transfer(self, source_id: int, destinataire_id: int, montant: float) -> tuple[Account, Account, Transaction]:
        source = self.get_by_id(source_id)
        destinataire = self.get_by_id(destinataire_id)
        if not source or not destinataire:
            raise KeyError("Compte introuvable.")

        debit(source, montant)
        credit(destinataire, montant)

        tx = Transaction(
            id=len(self.transactions) + 1,
            source_id=source_id,
            destinataire_id=destinataire_id,
            montant=montant
        )
        self.transactions.append(tx)
        return source, destinataire, tx

class FakeUserRepository:
    def __init__(self):
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[int, User] = {}

    def get_by_email(self, email: str) -> Optional[User]:
        return self.users_by_email.get(email)

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.users_by_id.get(user_id)

    def create(self, user_in: UserCreate) -> User:
        if user_in.email in self.users_by_email:
            raise ValueError("Cet email est déjà utilisé.")
        new_id = len(self.users_by_id) + 1
        new_user = User(
            id=new_id,
            email=user_in.email,
            password=hash_password(user_in.password)
        )
        self.users_by_email[user_in.email] = new_user
        self.users_by_id[new_id] = new_user
        return new_user

    def authenticate(self, user_in: UserCreate) -> str:
        u = self.get_by_email(user_in.email)
        if not u or not verify_password(user_in.password, u.password):
            raise ValueError("Email ou mot de passe incorrect.")
        secret_key = os.getenv("SECRET_KEY", "cle_secrete_banque_tres_longue_et_securisee_12345")
        return jwt.encode({"user_id": u.id, "email": u.email}, secret_key, algorithm="HS256")

    def get_user_from_token(self, token: str) -> dict:
        secret_key = os.getenv("SECRET_KEY", "cle_secrete_banque_tres_longue_et_securisee_12345")
        t = token.replace("Bearer ", "").strip()
        data = jwt.decode(t, secret_key, algorithms=["HS256"])
        u = self.get_by_email(data.get("email"))
        if not u:
            raise ValueError("Utilisateur introuvable.")
        return {"id": u.id, "email": u.email}
