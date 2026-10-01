import uuid
from datetime import datetime
from typing import Optional, List
from account.account import Account
from user.user import User, UserCreate, hash_password
from transaction.transaction import Transaction, TransferStatus
from beneficiary.beneficiary import Beneficiary

class FakeAccountRepository:
    def __init__(self):
        self.accounts: dict[str, Account] = {}

    def get_by_id(self, account_id: str) -> Optional[Account]:
        return self.accounts.get(account_id)

    def get_all(self) -> List[Account]:
        return sorted(list(self.accounts.values()), key=lambda a: getattr(a, "created_at", None) or datetime.min, reverse=True)

    def get_by_user_id(self, user_id: int) -> List[Account]:
        accounts = [acc for acc in self.accounts.values() if acc.user_id == user_id and not getattr(acc, "is_closed", False)]
        return sorted(accounts, key=lambda a: getattr(a, "created_at", None) or datetime.min, reverse=True)

    def get_main_account(self, user_id: int) -> Optional[Account]:
        return next((acc for acc in self.accounts.values() if acc.user_id == user_id and acc.is_main and not getattr(acc, "is_closed", False)), None)

    def create(self, name: str, user_id: int, solde: float = 0.0, is_main: bool = False) -> Account:
        new_id = str(uuid.uuid4())
        new_account = Account(
            id=new_id,
            name=name,
            solde=solde,
            user_id=user_id,
            is_main=is_main
        )
        self.accounts[new_id] = new_account
        return new_account

    def save(self, account: Account) -> Account:
        self.accounts[account.id] = account
        return account


class FakeTransactionRepository:
    def __init__(self):
        self.transactions: list[Transaction] = []

    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        return next((t for t in self.transactions if t.id == transaction_id), None)

    def get_by_account_id(self, account_id: str) -> List[Transaction]:
        txs = [
            tx for tx in self.transactions
            if tx.source_id == account_id or tx.destinataire_id == account_id
        ]
        return sorted(txs, key=lambda t: t.created_at, reverse=True)

    def get_pending(self) -> List[Transaction]:
        return [t for t in self.transactions if t.statut == TransferStatus.PENDING.value]

    def get_pending_amount_by_source(self, source_id: str) -> float:
        return round(
            sum(
                t.montant for t in self.transactions
                if t.source_id == source_id and t.statut == TransferStatus.PENDING.value
            ),
            2
        )

    def save(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            new_id = max((t.id for t in self.transactions if t.id is not None), default=0) + 1
            transaction.id = new_id
            self.transactions.append(transaction)
        else:
            for idx, existing in enumerate(self.transactions):
                if existing.id == transaction.id:
                    self.transactions[idx] = transaction
                    break
            else:
                self.transactions.append(transaction)
        return transaction


class FakeBeneficiaryRepository:
    def __init__(self):
        self.beneficiaries: list[Beneficiary] = []

    def get_by_user(self, user_id: int) -> List[Beneficiary]:
        return [b for b in self.beneficiaries if b.user_id == user_id]

    def get_by_account(self, user_id: int, account_id: str) -> Optional[Beneficiary]:
        for b in self.beneficiaries:
            if b.user_id == user_id and b.account_id == account_id:
                return b
        return None

    def create(self, user_id: int, account_id: str, name: str) -> Beneficiary:
        new_id = len(self.beneficiaries) + 1
        b = Beneficiary(
            id=new_id,
            user_id=user_id,
            account_id=account_id,
            name=name
        )
        self.beneficiaries.append(b)
        return b


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
        user = User(id=new_id, email=user_in.email, password=hash_password(user_in.password))
        self.users_by_id[new_id] = user
        self.users_by_email[user_in.email] = user
        return user
