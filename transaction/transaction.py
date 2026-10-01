from datetime import datetime, timezone
from typing import Optional, Any
from enum import Enum
from pydantic import BaseModel, Field as PydanticField, model_validator
from sqlmodel import SQLModel, Field

class TransferStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    CANCEL = "cancel"

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[str] = Field(default=None, nullable=True)
    destinataire_id: str = Field(index=True)
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
    source_id: Optional[str] = None
    destinataire_id: Optional[str] = None
    montant: Optional[float] = PydanticField(default=None, gt=0, description="Le montant doit être strictement supérieur à 0.")
    source_account: Optional[Any] = None
    target_account: Optional[Any] = None
    amount: Optional[float] = PydanticField(default=None, gt=0, description="Montant strictement positif")

    @model_validator(mode="before")
    @classmethod
    def unify_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # Normalisation des alias
            if "source_id" not in values and "source_account" in values:
                values["source_id"] = values["source_account"]
            if "destinataire_id" not in values and "target_account" in values:
                values["destinataire_id"] = values["target_account"]
            if "montant" not in values and "amount" in values:
                values["montant"] = values["amount"]

            # Conversion en str si un entier est envoyé (ex: 999999)
            if "source_id" in values and values["source_id"] is not None:
                values["source_id"] = str(values["source_id"])
            if "destinataire_id" in values and values["destinataire_id"] is not None:
                values["destinataire_id"] = str(values["destinataire_id"])
        return values

    @model_validator(mode="after")
    def validate_required_fields(self):
        if self.source_id is None:
            raise ValueError("Le champ source_id est obligatoire.")
        if self.destinataire_id is None:
            raise ValueError("Le champ destinataire_id est obligatoire.")
        if self.montant is None or self.montant <= 0:
            raise ValueError("Le montant doit être strictement supérieur à 0.")
        return self

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