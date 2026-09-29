from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    solde: float = Field(default=0.0)
    user_id: int = Field(foreign_key="user.id", index=True)  # Lien avec l'utilisateur


# Données reçues du client (Bruno)
class AccountCreate(BaseModel):
    name: str = "Nouveau Compte Courant"