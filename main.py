from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from account.account import Account
from user.user import UserCreate
from transaction.transaction import Transaction, InvalidAmountError, InsufficientBalanceError
from repositories.interfaces import AccountRepository, UserRepository
from dependencies import get_account_repo, get_user_repo, is_use_sql
from db.db import seed_initial_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialise les tables et les données par défaut en mode SQL
    if is_use_sql():
        seed_initial_data()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/register")
def inscription(user: UserCreate, user_repo: UserRepository = Depends(get_user_repo)):
    try:
        new_user = user_repo.create(user)
        return {
            "message": "Inscription réussie",
            "user_id": new_user.id,
            "email": new_user.email
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def connexion(user: UserCreate, user_repo: UserRepository = Depends(get_user_repo)):
    try:
        token = user_repo.authenticate(user)
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/me")
def mon_profil(
    authorization: str = Header(None),
    token: str = None,
    user_repo: UserRepository = Depends(get_user_repo)
):
    t = authorization or token
    if not t:
        raise HTTPException(status_code=401, detail="Token manquant.")
    try:
        return user_repo.get_user_from_token(t)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/accounts")
def liste_comptes(account_repo: AccountRepository = Depends(get_account_repo)):
    return account_repo.get_all()

@app.post("/transactions")
def Faire_un_transfert(
    transfert: Transaction,
    account_repo: AccountRepository = Depends(get_account_repo)
):
    if transfert.source_id == transfert.destinataire_id:
        raise HTTPException(status_code=400, detail="Le compte source et le compte destination doivent être différents.")

    source = account_repo.get_by_id(transfert.source_id)
    destinataire = account_repo.get_by_id(transfert.destinataire_id)

    if not source or not destinataire:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    try:
        source, destinataire, tx = account_repo.transfer(
            transfert.source_id,
            transfert.destinataire_id,
            transfert.montant
        )
    except (InvalidAmountError, InsufficientBalanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    summary = f"Transfert de {transfert.montant}€ de {source.name} (ID: {transfert.source_id}) vers {destinataire.name} (ID: {transfert.destinataire_id})"
    return {
        "status": "success",
        "summary": summary,
        "sender_new_solde": source.solde,
        "receiver_new_solde": destinataire.solde
    }
