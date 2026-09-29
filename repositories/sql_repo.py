import os
from typing import Optional, List
import jwt
from sqlmodel import Session, select
from account.account import Account
from user.user import User, UserCreate, hash_password, verify_password
from transaction.transaction import Transaction, debit, credit

class SqlAccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, account_id: int) -> Optional[Account]:
        return self.session.get(Account, account_id)

    def get_all(self) -> List[Account]:
        return self.session.exec(select(Account)).all()

    # --- NOUVELLE MÉTHODE US 4 ---
    def create(self, name: str, user_id: int) -> Account:
        new_account = Account(
            name=name,
            user_id=user_id,
            solde=0.0          # Règle Story 4 : solde à 0€ obligatoire
        )
        try:
            self.session.add(new_account)
            self.session.commit()
            self.session.refresh(new_account)
            return new_account
        except Exception:
            self.session.rollback()
            raise

    def transfer(self, source_id: int, destinataire_id: int, montant: float) -> tuple[Account, Account, Transaction]:
        """Effectue un virement atomique avec commit et rollback automatique en cas d'erreur."""
        source = self.session.get(Account, source_id)
        destinataire = self.session.get(Account, destinataire_id)
        if not source or not destinataire:
            raise KeyError("Compte introuvable.")

        try:
            debit(source, montant)
            credit(destinataire, montant)

            tx = Transaction(
                source_id=source_id,
                destinataire_id=destinataire_id,
                montant=montant
            )
            self.session.add(source)
            self.session.add(destinataire)
            self.session.add(tx)
            self.session.commit()
            self.session.refresh(source)
            self.session.refresh(destinataire)
            self.session.refresh(tx)
            return source, destinataire, tx
        except Exception:
            self.session.rollback()
            raise

class SqlUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.exec(select(User).where(User.email == email)).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def create(self, user_in: UserCreate) -> User:
        existing = self.get_by_email(user_in.email)
        if existing:
            raise ValueError("Cet email est déjà utilisé.")
        new_user = User(
            email=user_in.email,
            password=hash_password(user_in.password)
        )
        try:
            self.session.add(new_user)
            self.session.commit()
            self.session.refresh(new_user)
            return new_user
        except Exception:
            self.session.rollback()
            raise

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
