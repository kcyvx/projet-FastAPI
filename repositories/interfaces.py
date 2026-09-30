from typing import Protocol, Optional, List
from account.account import Account
from user.user import User, UserCreate
from transaction.transaction import Transaction

class AccountRepository(Protocol):
    def get_by_id(self, account_id: int) -> Optional[Account]:
        """Récupère un compte par son identifiant."""
        ...

    def get_all(self) -> List[Account]:
        """Récupère tous les comptes."""
        ...

    def get_by_user_id(self, user_id: int) -> List[Account]:
        """Récupère tous les comptes d'un utilisateur."""
        ...

    def create(self, name: str, user_id: int, solde: float = 0.0, is_main: bool = False) -> Account:
        """Crée un nouveau compte bancaire."""
        ...

    def deposit(self, account_id: int, montant: float) -> tuple[Account, Transaction]:
        """Crédite un compte et enregistre la transaction de dépôt."""
        ...

    def create_pending_transfer(self, source_id: int, destinataire_id: int, montant: float) -> Transaction:
        """Crée et enregistre en base une transaction avec le statut 'pending'."""
        ...

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """Récupère une transaction par son identifiant en base."""
        ...

    def get_pending_transactions(self) -> List[Transaction]:
        """Récupère toutes les transactions actuellement en attente ('pending') en base."""
        ...

    def get_pending_amount_by_source(self, source_id: int) -> float:
        """Calcule le montant total cumulé des transactions en attente pour un compte source."""
        ...

    def cancel_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """Annule une transaction en attente en passant son statut à 'cancelled'."""
        ...

    def finalize_transfer(self, transaction_id: int) -> tuple[Account, Account, Transaction]:
        """Valide et applique définitivement un virement en attente (débit, crédit, statut 'approved')."""
        ...

class UserRepository(Protocol):
    def get_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son adresse email."""
        ...

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par son identifiant."""
        ...

    def create(self, user_in: UserCreate) -> User:
        """Crée et enregistre un nouvel utilisateur."""
        ...
