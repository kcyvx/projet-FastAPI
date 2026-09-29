import os
from typing import Optional
import bcrypt
import jwt
from dotenv import load_dotenv
from sqlmodel import SQLModel, Field

load_dotenv()

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password: str

class UserCreate(SQLModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))

def is_logged_in(token: str) -> bool:
    try:
        secret_key = os.getenv("SECRET_KEY", "cle_secrete_banque_tres_longue_et_securisee_12345")
        jwt.decode(token.replace("Bearer ", "").strip(), secret_key, algorithms=["HS256"])
        return True
    except Exception:
        return False

def get_user_from_token(token: str) -> dict:
    secret_key = os.getenv("SECRET_KEY", "cle_secrete_banque_tres_longue_et_securisee_12345")
    t = token.replace("Bearer ", "").strip()
    data = jwt.decode(t, secret_key, algorithms=["HS256"])
    return {"id": data.get("user_id"), "email": data.get("email")}

