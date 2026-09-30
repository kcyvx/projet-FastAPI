from typing import Optional, List
from sqlmodel import Session, select
from account.account import Account
from user.user import User, UserCreate, hash_password
from transaction.transaction import Transaction, debit, credit

class SqlAccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, account_id: int) -> Optional[Account]:
        return self.session.get(Account, account_id)

    def get_all(self) -> List[Account]:
        return self.session.exec(select(Account)).all()

    def get_by_user_id(self, user_id: int) -> List[Account]:
        return self.session.exec(select(Account).where(Account.user_id == user_id)).all()


    def create(self, name: str, user_id: int, solde: float = 0.0, is_main: bool = False) -> Account:
        new_account = Account(
            name=name,
            user_id=user_id,
            solde=solde,
            is_main=is_main
        )
        try:
            self.session.add(new_account)
            self.session.commit()
            self.session.refresh(new_account)
            return new_account
        except Exception:
            self.session.rollback()
            raise

    def deposit(self, account_id: int, montant: float) -> tuple[Account, Transaction]:
        account = self.session.get(Account, account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        try:
            credit(account, montant)
            tx = Transaction(
                source_id=None,
                destinataire_id=account_id,
                montant=montant,
                type="DEPOT",
                statut="approved"
            )
            self.session.add(account)
            self.session.add(tx)
            self.session.commit()
            self.session.refresh(account)
            self.session.refresh(tx)
            return account, tx
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
                montant=montant,
                type="VIREMENT",
                statut="approved"
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
