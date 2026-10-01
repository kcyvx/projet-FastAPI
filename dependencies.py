import os
from fastapi import Depends, Header, HTTPException
from sqlmodel import Session
from db.db import get_session
from repositories.interfaces import (
    AccountRepository,
    TransactionRepository,
    BeneficiaryRepository,
    UserRepository
)
from repositories.fake_repo import (
    FakeAccountRepository,
    FakeTransactionRepository,
    FakeBeneficiaryRepository,
    FakeUserRepository
)
from repositories.sql_repo import (
    SqlAccountRepository,
    SqlTransactionRepository,
    SqlBeneficiaryRepository,
    SqlUserRepository
)
from services.bank_service import BankService
from user.user import get_user_from_token

def is_use_sql() -> bool:
    val = os.getenv("USE_SQL", "true").lower()
    return val in ("true", "1", "yes", "t", "on")

_fake_account_repo = FakeAccountRepository()
_fake_transaction_repo = FakeTransactionRepository()
_fake_beneficiary_repo = FakeBeneficiaryRepository()
_fake_user_repo = FakeUserRepository()

def get_account_repo(session: Session = Depends(get_session)) -> AccountRepository:
    if is_use_sql():
        return SqlAccountRepository(session)
    return _fake_account_repo

def get_transaction_repo(session: Session = Depends(get_session)) -> TransactionRepository:
    if is_use_sql():
        return SqlTransactionRepository(session)
    return _fake_transaction_repo

def get_beneficiary_repo(session: Session = Depends(get_session)) -> BeneficiaryRepository:
    if is_use_sql():
        return SqlBeneficiaryRepository(session)
    return _fake_beneficiary_repo

def get_user_repo(session: Session = Depends(get_session)) -> UserRepository:
    if is_use_sql():
        return SqlUserRepository(session)
    return _fake_user_repo

def get_bank_service(
    account_repo: AccountRepository = Depends(get_account_repo),
    tx_repo: TransactionRepository = Depends(get_transaction_repo)
) -> BankService:
    return BankService(account_repo=account_repo, tx_repo=tx_repo)

def get_current_user(
    authorization: str = Header(None),
    token: str = None,
    user_repo: UserRepository = Depends(get_user_repo)
) -> dict:
    t = authorization or token
    if not t:
        raise HTTPException(status_code=401, detail="Token manquant.")
    try:
        user_info = get_user_from_token(t)
        u = user_repo.get_by_id(user_info["id"])
        if not u:
            raise ValueError("Utilisateur introuvable.")
        return {"id": u.id, "email": u.email}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token invalide : {str(e)}")
