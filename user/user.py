import os, jwt
from dotenv import load_dotenv
from pydantic import BaseModel
from passlib.context import CryptContext

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: str
    password: str

def inscription_user(users_db, user):
    if user.email in users_db:
        raise ValueError("Cet email est déjà utilisé.")
    
    new_user = {
        "id": len(users_db) + 1,
        "email": user.email,
        "password": pwd_context.hash(user.password)
    }
    users_db[user.email] = new_user
    return new_user

def connexion_user(users_db, user):
    u = users_db.get(user.email)
    if not u or not pwd_context.verify(user.password, u["password"]):
        raise ValueError("Email ou mot de passe incorrect.")
    
    return jwt.encode({"user_id": u["id"], "email": u["email"]}, os.getenv("SECRET_KEY"), algorithm="HS256")
