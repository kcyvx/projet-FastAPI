
from pydantic import BaseModel



class Account(BaseModel):
    name:str 
    id:int 
    solde:float