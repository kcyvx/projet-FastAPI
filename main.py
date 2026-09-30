import os
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager 
from fastapi import FastAPI, HTTPException, Depends 
from account.account import Account, AccountCreate, AccountInfo
from user.user import UserCreate, authenticate
from transaction.transaction import (
    Transaction,
    InvalidAmountError,
    InsufficientBalanceError,
    DepositRequest,
    TransferRequest,
    TransferStatus
)
from repositories.interfaces import AccountRepository, UserRepository
from dependencies import get_account_repo, get_user_repo, get_current_user, is_use_sql
from db.db import seed_initial_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_use_sql():
        seed_initial_data()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/register")
def inscription(
    user: UserCreate,
    user_repo: UserRepository = Depends(get_user_repo),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    try:
        new_user = user_repo.create(user)
        main_account = account_repo.create(
            name="Compte Principal",
            user_id=new_user.id,
            solde=100.0,
            is_main=True
        )
        return {
            "message": "Inscription réussie",
            "user_id": new_user.id,
            "email": new_user.email,
            "account": {
                "id": main_account.id,
                "name": main_account.name,
                "solde": main_account.solde,
                "is_main": main_account.is_main
            }
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


@app.get("/transactions/pending")
def transactions_en_cours(
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    """Consulte les transactions actuellement en cours de traitement / flottement enregistrées en base."""
    return account_repo.get_pending_transactions()


@app.post("/transactions/{transaction_id}/cancel")
def annuler_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    """Annule une transaction en cours pendant son délai de flottement directement en base de données."""
    tx = account_repo.get_transaction_by_id(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    source = account_repo.get_by_id(tx.source_id)
    if not source or source.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Vous ne pouvez annuler que vos propres transactions.")

    if tx.statut != TransferStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Une transaction confirmée ou déjà traitée ne peut pas être annulée.")

    account_repo.cancel_transaction(transaction_id)
    return {
        "status": "cancelled",
        "message": "La transaction a été annulée avec succès.",
        "transaction_id": transaction_id
    }


@app.get("/transactions/{transaction_id}")
def detail_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    """Consulte le détail d'une transaction (Story 13)."""
    tx = account_repo.get_transaction_by_id(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    source = account_repo.get_by_id(tx.source_id) if tx.source_id else None
    destinataire = account_repo.get_by_id(tx.destinataire_id) if tx.destinataire_id else None

    is_sender = source and source.user_id == current_user["id"]
    is_receiver = destinataire and destinataire.user_id == current_user["id"]

    if not (is_sender or is_receiver):
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous devez être l'expéditeur ou le destinataire de cette transaction."
        )

    return tx


@app.post("/transactions")
async def Faire_un_transfert(
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

    pending_amount = account_repo.get_pending_amount_by_source(transfert.source_id)
    solde_disponible = source.solde - pending_amount
    if solde_disponible < transfert.montant:
        raise HTTPException(
            status_code=400,
            detail=f"Solde insuffisant ({solde_disponible:.2f} € disponibles, {transfert.montant:.2f} € requis)."
        )

    pending_tx = account_repo.create_pending_transfer(
        source_id=transfert.source_id,
        destinataire_id=transfert.destinataire_id,
        montant=transfert.montant
    )
    pending_id = pending_tx.id

    delay = float(os.getenv("TRANSFER_DELAY_SECONDS", "5.0"))
    if delay > 0:
        await asyncio.sleep(delay)

    current_tx = account_repo.get_transaction_by_id(pending_id)
    if not current_tx or current_tx.statut in (TransferStatus.REJECTED.value, TransferStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail="La transaction a été annulée durant le délai de rétractation.")

    try:
        source, destinataire, tx = account_repo.finalize_transfer(pending_id)
    except (InvalidAmountError, InsufficientBalanceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    summary = f"Transfert de {transfert.montant}€ de {source.name} (ID: {transfert.source_id}) vers {destinataire.name} (ID: {transfert.destinataire_id})"
    return {
        "status": "pending",
        "statut": "approved",
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
    account_id: str,
    account_repo: AccountRepository = Depends(get_account_repo),
    user: dict = Depends(get_current_user)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    return AccountInfo(account, user["id"])


@app.post("/accounts/{account_id}/deposit")
def deposer_argent(
    account_id: str,
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


@app.get("/accounts/{account_id}/transactions")
def voir_transactions_compte(
    account_id: str,
    user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    if account.user_id != user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez consulter que l'historique de vos propres comptes."
        )

    return account_repo.get_transactions_by_account_id(account_id)