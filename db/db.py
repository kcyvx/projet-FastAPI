import uuid
from sqlmodel import SQLModel, create_engine, Session, select
from account.account import Account
from user.user import User
from transaction.transaction import Transaction
from beneficiary.beneficiary import Beneficiary

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def seed_initial_data():
    create_db_and_tables()