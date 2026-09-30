from typing import Optional, List
from sqlmodel import Session, select, or_
from account.account import Account
from user.user import User, UserCreate, hash_password
from transaction.transaction import Transaction, TransferStatus, debit, credit

class SqlAccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, account_id: str ) -> Optional[Account]:
        return self.session.get(Account, account_id)

    def get_all(self) -> List[Account]:
        return list(self.session.exec(select(Account)).all())

    def get_by_user_id(self, user_id: int) -> List[Account]:
        return list(self.session.exec(select(Account).where(Account.user_id == user_id)).all())

    def get_transactions_by_account_id(self, account_id: str) -> List[Transaction]:
        statement = (
            select(Transaction)
            .where(or_(Transaction.source_id == account_id, Transaction.destinataire_id == account_id))
            .order_by(Transaction.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def create(self, name: str, user_id: int, solde: float = 0.0, is_main: bool = False) -> Account:
        new_account = Account(name=name, user_id=user_id, solde=solde, is_main=is_main)
        try:
            self.session.add(new_account)
            self.session.commit()
            self.session.refresh(new_account)
            return new_account
        except Exception:
            self.session.rollback()
            raise

    def deposit(self, account_id: str, montant: float) -> tuple[Account, Transaction]:
        account = self.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        try:
            credit(account, montant)
            tx = Transaction(
                destinataire_id=account_id,
                montant=montant,
                type="DEPOT",
                statut=TransferStatus.APPROVED.value
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

    def create_pending_transfer(self, source_id: str, destinataire_id: str, montant: float) -> Transaction:
        tx = Transaction(
            source_id=source_id,
            destinataire_id=destinataire_id,
            montant=montant,
            type="VIREMENT",
            statut=TransferStatus.PENDING.value
        )
        try:
            self.session.add(tx)
            self.session.commit()
            self.session.refresh(tx)
            return tx
        except Exception:
            self.session.rollback()
            raise

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        self.session.expire_all()
        return self.session.get(Transaction, transaction_id)

    def get_pending_transactions(self) -> List[Transaction]:
        self.session.expire_all()
        return list(self.session.exec(
            select(Transaction).where(Transaction.statut == TransferStatus.PENDING.value)
        ).all())

    def get_pending_amount_by_source(self, source_id: str) -> float:
        self.session.expire_all()
        pending_txs = self.session.exec(
            select(Transaction).where(
                Transaction.source_id == source_id,
                Transaction.statut == TransferStatus.PENDING.value
            )
        ).all()
        return round(sum(t.montant for t in pending_txs), 2)

    def cancel_transaction(self, transaction_id: int) -> Optional[Transaction]:
        self.session.expire_all()
        tx = self.session.get(Transaction, transaction_id)
        if not tx:
            return None
        tx.statut = TransferStatus.CANCELLED.value
        try:
            self.session.add(tx)
            self.session.commit()
            self.session.refresh(tx)
            return tx
        except Exception:
            self.session.rollback()
            raise

    def finalize_transfer(self, transaction_id: int) -> tuple[Account, Account, Transaction]:
        self.session.expire_all()
        tx = self.session.get(Transaction, transaction_id)
        if not tx:
            raise KeyError("Transaction introuvable.")

        source = self.session.get(Account, tx.source_id)
        destinataire = self.session.get(Account, tx.destinataire_id)
        if not source or not destinataire:
            raise KeyError("Compte introuvable.")

        try:
            debit(source, tx.montant)
            credit(destinataire, tx.montant)
            tx.statut = TransferStatus.APPROVED.value
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
            tx.statut = TransferStatus.REJECTED.value
            self.session.add(tx)
            self.session.commit()
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
