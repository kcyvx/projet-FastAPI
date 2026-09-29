# from typing_extensions import Optional
# from enum import Enum
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from transaction.transaction import debit, credit, InsufficientBalanceError, InvalidAmountError , Transaction 
from account.account import Account
# from sqlmodel import SQLModel, Field
# from datetime import datetime, timezone
app = FastAPI()

# class TransactionType(str,Enum):
#     DEPOT = "DEPOT"
#     TRANSFER ="TRANSFER"

# class TransactionStatus(str, Enum):
#     PENDING = "pending"
#     COMPLETED = "completed"
#     CANCELLED = "cancelled"


# class Account(SQLModel, table=True):
#     id: int = Field(default=None, primary_key=True)
#     account_number: str = Field(unique=True, index=True)
#     balance: float = Field(default=0.0)
#     is_main: bool = Field(default=False)
#     is_closed: bool = Field(default=False)
#     user_id: int = Field(index=True)

# class Transaction(SQLModel, table=True):
#     id: int = Field(default=None, primary_key=True)
#     source_account_id:int = Field(default=None, foreign_key="account.id", index=True)
#     destination_account_id: int = Field(foreign_key="account.id", index=True)
#     amount: float
#     type: TransactionType
#     status: TransactionStatus = Field(default=TransactionStatus.PENDING)
#     created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    


    

Lf_db={
    1: {"name": "Alice", "solde": 100.0},
    2: {"name": "Bob", "solde": 100.0},
} 
    
@app.post("/transactions")
def Faire_un_transfert(transfert: Transaction):
    
    if transfert.source_id == transfert.destinataire_id:
        raise HTTPException(status_code=400, detail="Le compte source et le compte destination doivent être différents.")

    source = Lf_db.get(transfert.source_id)
    destinataire = Lf_db.get(transfert.destinataire_id)

    if not source or not destinataire:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    try:
        debit(source, transfert.montant)
        credit(destinataire, transfert.montant)
    except (InvalidAmountError, InsufficientBalanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    summary = f"Transfert de {transfert.montant}€ de {source['name']} (ID: {transfert.source_id}) vers {destinataire['name']} (ID: {transfert.destinataire_id})"
    return {
        "status": "success",
        "summary": summary,
        "sender_new_solde": source["solde"],
        "receiver_new_solde": destinataire["solde"]
    }
    
    
