from typing import Optional, List
from account.account import Account
from user.user import User, UserCreate, hash_password
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

    def deposit(self, account_id: int, montant: float) -> tuple[Account, Transaction]:
        account = self.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        credit(account, montant)

        tx = Transaction(
            id=len(self.transactions) + 1,
            source_id=None,
            destinataire_id=account_id,
            montant=montant,
            type="DEPOT"
        )
        self.transactions.append(tx)
        return account, tx

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
            montant=montant,
            type="VIREMENT"
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
