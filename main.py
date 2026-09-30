from contextlib import asynccontextmanager 
from fastapi import FastAPI, HTTPException, Depends 
from account.account import Account, AccountCreate, AccountInfo
from user.user import UserCreate, authenticate
from transaction.transaction import Transaction, InvalidAmountError, InsufficientBalanceError, DepositRequest, TransferRequest
from repositories.interfaces import AccountRepository, UserRepository
from dependencies import get_account_repo, get_user_repo, get_current_user, is_use_sql
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
        token = authenticate(user_repo, user)
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/me")
def mon_profil(user: dict = Depends(get_current_user)):
    return user

@app.get("/accounts")
def liste_comptes(
    account_repo: AccountRepository = Depends(get_account_repo),
    user: dict = Depends(get_current_user)
):
    return account_repo.get_by_user_id(user["id"])


@app.post("/transactions")
def Faire_un_transfert(
    transfert: TransferRequest,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    if transfert.source_id == transfert.destinataire_id:
        raise HTTPException(status_code=400, detail="Le compte source et le compte destination doivent être différents.")

    source = account_repo.get_by_id(transfert.source_id)
    destinataire = account_repo.get_by_id(transfert.destinataire_id)

    if not source or not destinataire:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    if source.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez initier un virement que depuis vos propres comptes."
        )

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
        "status": "pending",
        "summary": summary,
        "sender_new_solde": source.solde,
        "receiver_new_solde": destinataire.solde,
        "transaction_id": tx.id
    }



@app.post("/accounts", status_code=201)
def ouvrir_compte(
    payload: AccountCreate,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    nouveau_compte = account_repo.create(
        name=payload.name,
        user_id=current_user["id"]
    )
    return {
        "message": "Compte bancaire ouvert avec succès",
        "account": nouveau_compte
    }


@app.get("/accounts/{account_id}")
def get_account_info(
    account_id: int,
    account_repo: AccountRepository = Depends(get_account_repo),
    user: dict = Depends(get_current_user)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    return AccountInfo(account, user["id"])


@app.post("/accounts/{account_id}/deposit")
def deposer_argent(
    account_id: int,
    payload: DepositRequest,
    user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    if account.user_id != user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez déposer que sur vos propres comptes."
        )

    try:
        updated_account, tx = account_repo.deposit(account_id, payload.montant)
        return {
            "message": f"Dépôt de {payload.montant} € effectué avec succès.",
            "account_id": updated_account.id,
            "nouveau_solde": updated_account.solde,
            "transaction_id": tx.id,
            "date": tx.created_at
        }
    except InvalidAmountError as e:
        raise HTTPException(status_code=400, detail=str(e))