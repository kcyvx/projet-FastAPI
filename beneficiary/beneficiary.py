from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import SQLModel, Field

class Beneficiary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    account_id: str = Field(index=True)
    name: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class BeneficiaryCreate(BaseModel):
    account_id: str
    name: str = PydanticField(..., min_length=1)