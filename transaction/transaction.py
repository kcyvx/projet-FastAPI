from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import SQLModel, Field

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(default=None, nullable=True)
    destinataire_id: int = Field(index=True)
    montant: float
    type: str = Field(default="DEPOT")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class DepositRequest(BaseModel):
    montant: float = PydanticField(..., gt=0, description="Le montant doit être strictement supérieur à 0.")

class InsufficientBalanceError(Exception):
    """Exception levée en cas de solde insuffisant."""
    pass

class InvalidAmountError(Exception):
    """Exception levée si le montant est <= 0."""
    pass

def credit(account: Any, amount: float) -> float:
    """Ajoute de l'argent au compte (compatible objet SQLModel et dict)."""
    if amount <= 0:
        raise InvalidAmountError("Le montant doit être strictement positif.")
    val = getattr(account, "solde", None) if not isinstance(account, dict) else account.get("solde")
    new_val = round(val + amount, 2)
    if isinstance(account, dict):
        account["solde"] = new_val
    else:
        account.solde = new_val
    return new_val

def debit(account: Any, amount: float) -> float:
    """Retire de l'argent du compte après vérification du solde (compatible objet SQLModel et dict)."""
    if amount <= 0:
        raise InvalidAmountError("Le montant doit être strictement positif.")
    val = getattr(account, "solde", None) if not isinstance(account, dict) else account.get("solde")
    if val < amount:
        raise InsufficientBalanceError(f"Solde insuffisant ({val:.2f} € disponibles, {amount:.2f} € requis).")
    new_val = round(val - amount, 2)
    if isinstance(account, dict):
        account["solde"] = new_val
    else:
        account.solde = new_val
    return new_val