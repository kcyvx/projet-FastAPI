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
        """Récupère tous les comptes appartenant à un utilisateur spécifique."""
        ...


    def create(self, name: str, user_id: int) -> Account:
        """Crée un nouveau compte bancaire avec un solde initial de 0.0."""
        ...

    def transfer(self, source_id: int, destinataire_id: int, montant: float) -> tuple[Account, Account, Transaction]:
        """Effectue un virement atomique entre deux comptes et enregistre la transaction."""
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

    def authenticate(self, user_in: UserCreate) -> str:
        """Vérifie les identifiants et génère un token JWT."""
        ...

    def get_user_from_token(self, token: str) -> dict:
        """Décode le token JWT et retourne les informations de l'utilisateur."""
        ...
