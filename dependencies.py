import os
import jwt
from fastapi import Depends
from fastapi import Header, HTTPException
from sqlmodel import Session
from db.db import get_session
from repositories.interfaces import AccountRepository, UserRepository
from repositories.fake_repo import FakeAccountRepository, FakeUserRepository
from repositories.sql_repo import SqlAccountRepository, SqlUserRepository

def is_use_sql() -> bool:
    """Vérifie la variable d'environnement USE_SQL (vrai par défaut si 'true', '1', 'yes')."""
    val = os.getenv("USE_SQL", "true").lower()
    return val in ("true", "1", "yes", "t", "on")

# Instances partagées en mémoire pour le mode fake
_fake_account_repo = FakeAccountRepository()
_fake_user_repo = FakeUserRepository()

def get_account_repo(session: Session = Depends(get_session)) -> AccountRepository:
    """Fournit dynamiquement le repository selon USE_SQL."""
    if is_use_sql():
        return SqlAccountRepository(session)
    return _fake_account_repo

def get_user_repo(session: Session = Depends(get_session)) -> UserRepository:
    """Fournit dynamiquement le repository utilisateur selon USE_SQL."""
    if is_use_sql():
        return SqlUserRepository(session)
    return _fake_user_repo

def get_current_user(
    authorization: str = Header(None),
    token: str = None,
    user_repo: UserRepository = Depends(get_user_repo)
) -> dict:
    """Dépendance FastAPI réutilisable pour authentifier l'utilisateur via son JWT."""
    t = authorization or token
    if not t:
        raise HTTPException(status_code=401, detail="Token manquant.")
    try:
        return user_repo.get_user_from_token(t)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token invalide : {str(e)}")

def is_logged_in(token: str) -> bool:
    try:
        secret_key = os.getenv("SECRET_KEY", "cle_secrete_banque_tres_longue_et_securisee_12345")
        jwt.decode(token.replace("Bearer ", "").strip(), secret_key, algorithms=["HS256"])
        return True
    except Exception:
        return False

# --- DÉPENDANCE D'AUTHENTIFICATION AJOUTÉE ---
def get_current_user(
    authorization: str = Header(None),
    token: str = None,
    user_repo: UserRepository = Depends(get_user_repo)
) -> dict:
    """Récupère l'utilisateur connecté à partir du token JWT."""
    t = authorization or token
    if not t:
        raise HTTPException(status_code=401, detail="Token manquant.")
    try:
        return user_repo.get_user_from_token(t)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))