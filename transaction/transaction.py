from datetime import datetime, timezone
from typing import Optional, Any
from enum import Enum
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import SQLModel, Field

class TransferStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(default=None, nullable=True)
    destinataire_id: int = Field(index=True)
    montant: float
    type: str = Field(default="DEPOT")
    statut: str = Field(default=TransferStatus.PENDING.value)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class DepositRequest(BaseModel):
    montant: float = PydanticField(..., gt=0, description="Le montant doit être strictement supérieur à 0.")

class TransferRequest(BaseModel):
    source_id: int
    destinataire_id: int
    montant: float = PydanticField(..., gt=0, description="Le montant doit être strictement supérieur à 0.")

class InsufficientBalanceError(Exception):
    """Exception levée en cas de solde insuffisant."""
    pass

class InvalidAmountError(Exception):
    """Exception levée si le montant est <= 0."""
    pass

def credit(account: Any, amount: float) -> float:
    """Ajoute de l'argent au compte."""
    if amount <= 0:
        raise InvalidAmountError("Le montant doit être strictement positif.")
    account.solde = round(account.solde + amount, 2)
    return account.solde

def debit(account: Any, amount: float) -> float:
    """Retire de l'argent du compte après vérification du solde."""
    if amount <= 0:
        raise InvalidAmountError("Le montant doit être strictement positif.")
    if account.solde < amount:
        raise InsufficientBalanceError(f"Solde insuffisant ({account.solde:.2f} € disponibles, {amount:.2f} € requis).")
    account.solde = round(account.solde - amount, 2)
    return account.solde