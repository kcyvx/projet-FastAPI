from typing import Optional
from sqlmodel import SQLModel, Field

class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    solde: float = Field(default=0.0)
    