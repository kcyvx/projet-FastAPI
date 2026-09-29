from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from transaction.transaction import debit, credit, InsufficientBalanceError, InvalidAmountError , Transaction 
from account.account import Account
from user.user import UserCreate, inscription_user, connexion_user
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

users_db = {}

@app.post("/register")
def inscription(user: UserCreate):
    try:
        new_user = inscription_user(users_db, user)
        return {
            "message": "Inscription réussie",
            "user_id": new_user["id"],
            "email": new_user["email"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def connexion(user: UserCreate):
    try:
        token = connexion_user(users_db, user)
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    
@app.post("/transactions")
def Faire_un_transfert(transfert: Transaction):
    
    source = Lf_db[transfert.source_id]
    destinataire = Lf_db[transfert.destinataire_id]

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

    
    
