import uuid
from typing import Optional, List
from account.account import Account
from user.user import User, UserCreate, hash_password
from transaction.transaction import Transaction, TransferStatus, debit, credit

class FakeAccountRepository:
    def __init__(self):
        id_alice = str(uuid.uuid4())
        id_bob = str(uuid.uuid4())
        self.accounts: dict[str, Account] = {
            id_alice: Account(id=id_alice, name="Alice", solde=100.0, user_id=1, is_main=True),
            id_bob: Account(id=id_bob, name="Bob", solde=100.0, user_id=2, is_main=True),
        }
        self.transactions: list[Transaction] = []

    def get_by_id(self, account_id: str ) -> Optional[Account]:
        return self.accounts.get(account_id)

    def get_all(self) -> List[Account]:
        return list(self.accounts.values())

    def get_by_user_id(self, user_id: int) -> List[Account]:
        return [acc for acc in self.accounts.values() if acc.user_id == user_id and not getattr(acc, "is_closed", False)]

    def get_main_account(self, user_id: int) -> Optional[Account]:
        return next((acc for acc in self.accounts.values() if acc.user_id == user_id and acc.is_main and not getattr(acc, "is_closed", False)), None)

    def close_account(self, account_id: str) -> tuple[Account, Account, Optional[Transaction]]:
        account = self.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        main_account = self.get_main_account(account.user_id)
        if not main_account:
            raise ValueError("Compte principal introuvable pour cet utilisateur.")

        solde_to_transfer = account.solde
        tx = None
        if solde_to_transfer > 0:
            credit(main_account, solde_to_transfer)
            account.solde = 0.0
            tx = Transaction(
                id=len(self.transactions) + 1,
                source_id=account.id,
                destinataire_id=main_account.id,
                montant=solde_to_transfer,
                type="CLOTURE",
                statut=TransferStatus.APPROVED.value
            )
            self.transactions.append(tx)

        account.is_closed = True
        return account, main_account, tx

    def get_transactions_by_account_id(self, account_id: str) -> List[Transaction]:
        txs = [
            tx for tx in self.transactions
            if tx.source_id == account_id or tx.destinataire_id == account_id
        ]
        return sorted(txs, key=lambda t: t.created_at, reverse=True)

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

    def deposit(self, account_id: str, montant: float) -> tuple[Account, Transaction]:
        account = self.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        credit(account, montant)
        tx = Transaction(
            id=len(self.transactions) + 1,
            destinataire_id=account_id,
            montant=montant,
            type="DEPOT",
            statut=TransferStatus.APPROVED.value
        )
        self.transactions.append(tx)
        return account, tx

    def create_pending_transfer(self, source_id: str, destinataire_id: str, montant: float) -> Transaction:
        new_id = max((t.id for t in self.transactions if t.id is not None), default=0) + 1
        tx = Transaction(
            id=new_id,
            source_id=source_id,
            destinataire_id=destinataire_id,
            montant=montant,
            type="VIREMENT",
            statut=TransferStatus.PENDING.value
        )
        self.transactions.append(tx)
        return tx

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        return next((t for t in self.transactions if t.id == transaction_id), None)

    def get_pending_transactions(self) -> List[Transaction]:
        return [t for t in self.transactions if t.statut == TransferStatus.PENDING.value]

    def get_pending_amount_by_source(self, source_id: str) -> float:
        return round(
            sum(
                t.montant for t in self.transactions
                if t.source_id == source_id and t.statut == TransferStatus.PENDING.value
            ),
            2
        )

    def cancel_transaction(self, transaction_id: int) -> Optional[Transaction]:
        tx = self.get_transaction_by_id(transaction_id)
        if tx:
            tx.statut = TransferStatus.CANCELLED.value
        return tx

    def finalize_transfer(self, transaction_id: int) -> tuple[Account, Account, Transaction]:
        tx = self.get_transaction_by_id(transaction_id)
        if not tx:
            raise KeyError("Transaction introuvable.")

        source = self.get_by_id(tx.source_id)
        destinataire = self.get_by_id(tx.destinataire_id)
        if not source or not destinataire:
            raise KeyError("Compte introuvable.")

        try:
            debit(source, tx.montant)
            credit(destinataire, tx.montant)
            tx.statut = TransferStatus.APPROVED.value
            return source, destinataire, tx
        except Exception:
            tx.statut = TransferStatus.REJECTED.value
            raise

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
