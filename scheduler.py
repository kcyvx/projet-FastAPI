import os
import asyncio
from datetime import datetime, timezone
from typing import List
from sqlmodel import Session

from db.db import engine
from dependencies import is_use_sql
import dependencies
from repositories.sql_repo import SqlAccountRepository, SqlTransactionRepository
from services.bank_service import BankService
from transaction.transaction import Transaction

def get_transaction_age_seconds(tx: Transaction) -> float:
    """Calcule l'âge d'une transaction en secondes (gère timezone utc et naive)."""
    now = datetime.now(timezone.utc)
    tx_time = tx.created_at
    if tx_time.tzinfo is None:
        tx_time = tx_time.replace(tzinfo=timezone.utc)
    return (now - tx_time).total_seconds()

def apply_pending_transactions(cancellation_timeout: float = 5.0) -> List[int]:
    """
    Parcourt toutes les transactions ayant le statut 'pending'.
    Pour chacune, si le délai d'annulation (5 secondes) est écoulé :
    - Applique définitivement la transaction via BankService (débit source, crédit destinataire).
    - Met à jour le statut en 'approved'.
    Retourne la liste des IDs des transactions traitées avec succès.
    """
    applied_ids: List[int] = []

    if is_use_sql():
        with Session(engine) as session:
            account_repo = SqlAccountRepository(session)
            tx_repo = SqlTransactionRepository(session)
            bank_service = BankService(account_repo=account_repo, tx_repo=tx_repo)

            pending_txs = tx_repo.get_pending()
            for tx in pending_txs:
                if get_transaction_age_seconds(tx) >= cancellation_timeout:
                    try:
                        bank_service.finalize_transfer(tx.id)
                        applied_ids.append(tx.id)
                    except Exception as e:
                        print(f"[TaskScheduler] Erreur finalisation transaction {tx.id}: {e}")
    else:
        account_repo = dependencies._fake_account_repo
        tx_repo = dependencies._fake_transaction_repo
        bank_service = BankService(account_repo=account_repo, tx_repo=tx_repo)

        pending_txs = tx_repo.get_pending()
        for tx in pending_txs:
            if get_transaction_age_seconds(tx) >= cancellation_timeout:
                try:
                    bank_service.finalize_transfer(tx.id)
                    applied_ids.append(tx.id)
                except Exception as e:
                    print(f"[TaskScheduler] Erreur finalisation transaction {tx.id}: {e}")

    return applied_ids

async def run_task_scheduler(interval_seconds: float = 10.0, cancellation_timeout: float = 5.0):
    """
    Tâche de fond TaskScheduler (cronjob) exécutée toutes les interval_seconds (10s par défaut).
    Vérifie et applique les transactions pending dont le délai d'annulation est écoulé via BankService.
    """
    while True:
        try:
            timeout = float(os.getenv("CANCELLATION_TIMEOUT_SECONDS", str(cancellation_timeout)))
            apply_pending_transactions(cancellation_timeout=timeout)
        except Exception as e:
            print(f"[TaskScheduler] Erreur inattendue dans la boucle: {e}")

        interval = float(os.getenv("TASK_SCHEDULER_INTERVAL_SECONDS", str(interval_seconds)))
        await asyncio.sleep(interval)
