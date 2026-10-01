from typing import Optional, List
from sqlmodel import Session, select, or_
from account.account import Account
from user.user import User, UserCreate, hash_password
from transaction.transaction import Transaction, TransferStatus
from beneficiary.beneficiary import Beneficiary

class SqlAccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, account_id: str) -> Optional[Account]:
        return self.session.get(Account, account_id)

    def get_all(self) -> List[Account]:
        return list(self.session.exec(select(Account).order_by(Account.created_at.desc())).all())

    def get_by_user_id(self, user_id: int) -> List[Account]:
        statement = (
            select(Account)
            .where(Account.user_id == user_id, Account.is_closed == False)
            .order_by(Account.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def get_main_account(self, user_id: int) -> Optional[Account]:
        statement = select(Account).where(
            Account.user_id == user_id,
            Account.is_main == True,
            Account.is_closed == False
        )
        return self.session.exec(statement).first()

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

    def save(self, account: Account) -> Account:
        try:
            self.session.add(account)
            self.session.commit()
            self.session.refresh(account)
            return account
        except Exception:
            self.session.rollback()
            raise


class SqlTransactionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        self.session.expire_all()
        return self.session.get(Transaction, transaction_id)

    def get_by_account_id(self, account_id: str) -> List[Transaction]:
        statement = (
            select(Transaction)
            .where(or_(Transaction.source_id == account_id, Transaction.destinataire_id == account_id))
            .order_by(Transaction.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def get_pending(self) -> List[Transaction]:
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

    def save(self, transaction: Transaction) -> Transaction:
        try:
            self.session.add(transaction)
            self.session.commit()
            self.session.refresh(transaction)
            return transaction
        except Exception:
            self.session.rollback()
            raise


class SqlBeneficiaryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_user(self, user_id: int) -> List[Beneficiary]:
        statement = select(Beneficiary).where(Beneficiary.user_id == user_id)
        return list(self.session.exec(statement).all())

    def get_by_account(self, user_id: int, account_id: str) -> Optional[Beneficiary]:
        statement = select(Beneficiary).where(
            Beneficiary.user_id == user_id,
            Beneficiary.account_id == account_id
        )
        return self.session.exec(statement).first()

    def create(self, user_id: int, account_id: str, name: str) -> Beneficiary:
        b = Beneficiary(user_id=user_id, account_id=account_id, name=name)
        try:
            self.session.add(b)
            self.session.commit()
            self.session.refresh(b)
            return b
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
