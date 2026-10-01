from typing import Protocol, Optional, List
from account.account import Account
from user.user import User, UserCreate
from transaction.transaction import Transaction
from beneficiary.beneficiary import Beneficiary

class AccountRepository(Protocol):
    def get_by_id(self, account_id: str) -> Optional[Account]:
        """Récupère un compte par son identifiant."""
        ...

    def get_all(self) -> List[Account]:
        """Récupère tous les comptes."""
        ...

    def get_by_user_id(self, user_id: int) -> List[Account]:
        """Récupère tous les comptes d'un utilisateur triés par date décroissante."""
        ...

    def get_main_account(self, user_id: int) -> Optional[Account]:
        """Récupère le compte principal d'un utilisateur."""
        ...

    def create(self, name: str, user_id: int, solde: float = 0.0, is_main: bool = False) -> Account:
        """Crée un nouveau compte bancaire."""
        ...

    def save(self, account: Account) -> Account:
        """Sauvegarde ou met à jour un compte existant."""
        ...


class TransactionRepository(Protocol):
    def get_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """Récupère une transaction par son identifiant."""
        ...

    def get_by_account_id(self, account_id: str) -> List[Transaction]:
        """Récupère toutes les transactions associées à un compte (émetteur ou destinataire)."""
        ...

    def get_pending(self) -> List[Transaction]:
        """Récupère toutes les transactions actuellement en attente ('pending')."""
        ...

    def get_pending_amount_by_source(self, source_id: str) -> float:
        """Calcule le montant cumulé des transactions en attente pour un compte source."""
        ...

    def save(self, transaction: Transaction) -> Transaction:
        """Sauvegarde ou met à jour une transaction."""
        ...


class BeneficiaryRepository(Protocol):
    def get_by_user(self, user_id: int) -> List[Beneficiary]:
        """Récupère tous les bénéficiaires enregistrés par un utilisateur."""
        ...

    def get_by_account(self, user_id: int, account_id: str) -> Optional[Beneficiary]:
        """Vérifie si un compte cible est déjà enregistré comme bénéficiaire pour l'utilisateur."""
        ...

    def create(self, user_id: int, account_id: str, name: str) -> Beneficiary:
        """Ajoute et enregistre un compte bénéficiaire pour un utilisateur."""
        ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Récupère un utilisateur par son identifiant."""
        ...

    def get_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son adresse email."""
        ...

    def create(self, user_in: UserCreate) -> User:
        """Crée et enregistre un nouvel utilisateur."""
        ...
