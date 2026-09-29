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

def get_user_info(users_db, token):
    t = token.replace("Bearer ", "")
    data = jwt.decode(t, os.getenv("SECRET_KEY"), algorithms=["HS256"])
    user = users_db.get(data["email"])
    if not user:
        raise ValueError("Utilisateur introuvable.")
    return {"id": user["id"], "email": user["email"]}
