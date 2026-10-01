from typing import Optional
from account.account import Account
from transaction.transaction import (
    Transaction,
    TransferStatus,
    debit,
    credit,
    InvalidAmountError,
    InsufficientBalanceError
)
from repositories.interfaces import AccountRepository, TransactionRepository

class BankService:
    def __init__(self, account_repo: AccountRepository, tx_repo: TransactionRepository):
        self.account_repo = account_repo
        self.tx_repo = tx_repo

    def close_account(self, account_id: str) -> tuple[Account, Account, Optional[Transaction]]:
        account = self.account_repo.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")
        
        main_account = self.account_repo.get_main_account(account.user_id)
        if not main_account:
            raise ValueError("Compte principal introuvable pour cet utilisateur.")

        solde_to_transfer = account.solde
        tx = None

        if solde_to_transfer > 0:
            credit(main_account, solde_to_transfer)
            account.solde = 0.0
            
            tx = Transaction(
                source_id=account.id,
                destinataire_id=main_account.id,
                montant=solde_to_transfer,
                type="CLOTURE",
                statut=TransferStatus.APPROVED.value
            )
            self.tx_repo.save(tx)

        account.is_closed = True
        
        self.account_repo.save(account)
        self.account_repo.save(main_account)
        
        return account, main_account, tx

    def deposit(self, account_id: str, montant: float) -> tuple[Account, Transaction]:
        account = self.account_repo.get_by_id(account_id)
        if not account:
            raise KeyError("Compte introuvable.")

        credit(account, montant)
        
        tx = Transaction(
            destinataire_id=account_id,
            montant=montant,
            type="DEPOT",
            statut=TransferStatus.APPROVED.value
        )
        
        self.account_repo.save(account)
        self.tx_repo.save(tx)
        
        return account, tx

    def finalize_transfer(self, transaction_id: int) -> tuple[Account, Account, Transaction]:
        tx = self.tx_repo.get_by_id(transaction_id)
        if not tx:
            raise KeyError("Transaction introuvable.")
            
        source = self.account_repo.get_by_id(tx.source_id)
        destinataire = self.account_repo.get_by_id(tx.destinataire_id)
        
        if not source or not destinataire:
            raise KeyError("Compte introuvable.")

        try:
            debit(source, tx.montant)
            credit(destinataire, tx.montant)
            tx.statut = TransferStatus.APPROVED.value
            
            self.account_repo.save(source)
            self.account_repo.save(destinataire)
            self.tx_repo.save(tx)
            
            return source, destinataire, tx
        except Exception:
            tx.statut = TransferStatus.REJECTED.value
            self.tx_repo.save(tx)
            raise
