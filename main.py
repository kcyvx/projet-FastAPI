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
from repositories.interfaces import (
    AccountRepository,
    TransactionRepository,
    BeneficiaryRepository,
    UserRepository
)
from services.bank_service import BankService
from dependencies import (
    get_account_repo,
    get_transaction_repo,
    get_beneficiary_repo,
    get_user_repo,
    get_bank_service,
    get_current_user,
    is_use_sql
)
from db.db import seed_initial_data
from beneficiary.beneficiary import BeneficiaryCreate
from scheduler import run_task_scheduler, apply_pending_transactions

@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_use_sql():
        seed_initial_data()
    # Tâche de fond TaskScheduler (cronjob) exécutée toutes les 10 secondes
    scheduler_task = asyncio.create_task(run_task_scheduler(interval_seconds=10.0, cancellation_timeout=5.0))
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

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
                "is_main": main_account.is_main,
                "created_at": main_account.created_at
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
    tx_repo: TransactionRepository = Depends(get_transaction_repo)
):
    """Consulte les transactions actuellement en cours de traitement / flottement enregistrées en base."""
    return tx_repo.get_pending()


@app.post("/transactions/{transaction_id}/cancel")
def annuler_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
    tx_repo: TransactionRepository = Depends(get_transaction_repo),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    """Annule une transaction en cours si le délai maximum de 5 secondes n'est pas dépassé."""
    tx = tx_repo.get_by_id(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")

    source = account_repo.get_by_id(tx.source_id) if tx.source_id else None
    if not source or source.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Vous ne pouvez annuler que vos propres transactions.")

    if tx.statut != TransferStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Une transaction confirmée ou déjà traitée ne peut pas être annulée.")

    # Vérification du délai d'annulation de 5 secondes maximum
    now = datetime.now(timezone.utc)
    tx_time = tx.created_at
    if tx_time.tzinfo is None:
        tx_time = tx_time.replace(tzinfo=timezone.utc)
    age = (now - tx_time).total_seconds()
    cancellation_timeout = float(os.getenv("CANCELLATION_TIMEOUT_SECONDS", "5.0"))
    if age > cancellation_timeout:
        raise HTTPException(
            status_code=400,
            detail=f"Délai d'annulation dépassé : la transaction a été initiée il y a {age:.1f}s (maximum autorisé : {cancellation_timeout:.1f}s)."
        )

    tx.statut = TransferStatus.CANCELLED.value
    tx_repo.save(tx)
    return {
        "status": "cancelled",
        "statut": "cancelled",
        "message": "La transaction a été annulée avec succès.",
        "transaction_id": transaction_id
    }


@app.get("/transactions/{transaction_id}")
def detail_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
    tx_repo: TransactionRepository = Depends(get_transaction_repo),
    account_repo: AccountRepository = Depends(get_account_repo)
):
    """Consulte le détail d'une transaction (Story 13)."""
    tx = tx_repo.get_by_id(transaction_id)
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
def Faire_un_transfert(
    transfert: TransferRequest,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo),
    tx_repo: TransactionRepository = Depends(get_transaction_repo)
):
    if transfert.source_id == transfert.destinataire_id:
        raise HTTPException(status_code=400, detail="Le compte source et le compte destination doivent être différents.")

    source = account_repo.get_by_id(transfert.source_id)
    destinataire = account_repo.get_by_id(transfert.destinataire_id)

    if not source or not destinataire:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    if getattr(source, "is_closed", False):
        raise HTTPException(status_code=400, detail="Le compte source est clôturé et ne peut plus être utilisé.")

    if getattr(destinataire, "is_closed", False):
        raise HTTPException(status_code=400, detail="Le compte destinataire est clôturé et ne peut plus être utilisé.")

    if source.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez initier un virement que depuis vos propres comptes."
        )

    pending_amount = tx_repo.get_pending_amount_by_source(transfert.source_id)
    solde_disponible = source.solde - pending_amount
    if solde_disponible < transfert.montant:
        raise HTTPException(
            status_code=400,
            detail=f"Solde insuffisant ({solde_disponible:.2f} € disponibles, {transfert.montant:.2f} € requis)."
        )

    pending_tx = Transaction(
        source_id=transfert.source_id,
        destinataire_id=transfert.destinataire_id,
        montant=transfert.montant,
        type="VIREMENT",
        statut=TransferStatus.PENDING.value
    )
    saved_tx = tx_repo.save(pending_tx)

    summary = f"Transfert de {transfert.montant}€ de {source.name} (ID: {transfert.source_id}) vers {destinataire.name} (ID: {transfert.destinataire_id})"
    return {
        "status": "pending",
        "statut": "pending",
        "message": "Transaction enregistrée avec succès et en attente de traitement.",
        "summary": summary,
        "transaction_id": saved_tx.id,
        "source_id": saved_tx.source_id,
        "destinataire_id": saved_tx.destinataire_id,
        "montant": saved_tx.montant,
        "created_at": saved_tx.created_at
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
    if getattr(account, "is_closed", False):
        raise HTTPException(status_code=404, detail="Ce compte est clôturé et ne peut plus être consulté.")
    return AccountInfo(account, user["id"])


@app.post("/accounts/{account_id}/deposit")
def deposer_argent(
    account_id: str,
    payload: DepositRequest,
    user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo),
    bank_service: BankService = Depends(get_bank_service)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    if getattr(account, "is_closed", False):
        raise HTTPException(status_code=400, detail="Impossible de déposer de l'argent sur un compte clôturé.")

    if account.user_id != user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez déposer que sur vos propres comptes."
        )

    try:
        updated_account, tx = bank_service.deposit(account_id, payload.montant)
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
    account_repo: AccountRepository = Depends(get_account_repo),
    tx_repo: TransactionRepository = Depends(get_transaction_repo)
):
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    if getattr(account, "is_closed", False):
        raise HTTPException(status_code=404, detail="Ce compte est clôturé et ne peut plus être consulté.")
    if account.user_id != user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez consulter que l'historique de vos propres comptes."
        )

    return tx_repo.get_by_account_id(account_id)


@app.post("/accounts/{account_id}/close")
@app.delete("/accounts/{account_id}")
def cloturer_compte(
    account_id: str,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo),
    tx_repo: TransactionRepository = Depends(get_transaction_repo),
    bank_service: BankService = Depends(get_bank_service)
):
    """Clôture un compte bancaire et transfère son solde vers le compte principal via BankService (Story 12)."""
    account = account_repo.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    if account.user_id != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="Action non autorisée : vous ne pouvez clôturer que vos propres comptes."
        )

    if getattr(account, "is_closed", False):
        raise HTTPException(status_code=400, detail="Ce compte est déjà clôturé.")

    if getattr(account, "is_main", False):
        raise HTTPException(status_code=400, detail="Le compte principal ne peut pas être clôturé.")

    pending_txs = [
        t for t in tx_repo.get_pending()
        if (t.source_id == account_id or t.destinataire_id == account_id)
        and getattr(t, "statut", None) == TransferStatus.PENDING.value
    ]
    if pending_txs:
        raise HTTPException(
            status_code=400,
            detail="Le compte ne peut pas être clôturé s'il y a des transactions en cours."
        )

    closed_account, main_account, tx = bank_service.close_account(account_id)
    return {
        "message": "Le compte a été clôturé avec succès.",
        "account_id": closed_account.id,
        "is_closed": closed_account.is_closed,
        "transferred_amount": tx.montant if tx else 0.0,
        "main_account_new_solde": main_account.solde
    }


@app.post("/beneficiaries", status_code=201)
def ajouter_beneficiaire(
    payload: BeneficiaryCreate,
    current_user: dict = Depends(get_current_user),
    account_repo: AccountRepository = Depends(get_account_repo),
    beneficiary_repo: BeneficiaryRepository = Depends(get_beneficiary_repo)
):
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="Le nom du bénéficiaire doit être renseigné."
        )

    target_account = account_repo.get_by_id(payload.account_id)
    if not target_account:
        raise HTTPException(
            status_code=404,
            detail="Compte bénéficiaire introuvable."
        )

    if target_account.user_id == current_user["id"]:
        raise HTTPException(
            status_code=400,
            detail="Le bénéficiaire ne peut pas être un de vos propres comptes."
        )

    existing = beneficiary_repo.get_by_account(current_user["id"], payload.account_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ce bénéficiaire a déjà été ajouté."
        )

    beneficiary = beneficiary_repo.create(
        user_id=current_user["id"],
        account_id=payload.account_id,
        name=clean_name
    )
    return {
        "message": "Bénéficiaire ajouté avec succès.",
        "beneficiary": beneficiary
    }

@app.get("/beneficiaries")
def liste_beneficiaires(
    current_user: dict = Depends(get_current_user),
    beneficiary_repo: BeneficiaryRepository = Depends(get_beneficiary_repo)
):
    return beneficiary_repo.get_by_user(current_user["id"])