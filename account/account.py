import uuid
from typing import Optional, Union
from sqlmodel import SQLModel, Field
from pydantic import BaseModel
from fastapi import HTTPException
from user.user import is_logged_in, get_user_from_token

class Account(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    solde: float = Field(default=0.0)
    user_id: int = Field(foreign_key="user.id", index=True)
    is_main: bool = Field(default=False)
    is_closed: bool = Field(default=False)


class AccountCreate(BaseModel):     
    name: str = "Compte Courant"

def AccountInfo(account: Account, user_or_token: Union[int, str, dict]) -> dict:
    """Vérifie que l'utilisateur est le propriétaire du compte et retourne ses informations."""
    if isinstance(user_or_token, int):
        user_id = user_or_token
    elif isinstance(user_or_token, dict):
        user_id = user_or_token.get("id")
    elif isinstance(user_or_token, str):
        user = get_user_from_token(user_or_token)
        user_id = user.get("id") if user else None
    else:
        user_id = None

    if user_id is None or account.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas accès à ce compte."
        )

    return {
        "id": account.id,
        "user_id": account.user_id,
        "name": account.name,
        "solde": account.solde,
        "is_main": account.is_main,
        "is_closed": account.is_closed
    }
