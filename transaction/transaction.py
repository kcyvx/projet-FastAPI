from pydantic import BaseModel
class Transaction(BaseModel):
    source_id: int
    destinataire_id: int
    montant:float



class InsufficientBalanceError(Exception):
    """Exception levée en cas de solde insuffisant."""
    pass

class InvalidAmountError(Exception):
    """Exception levée si le montant est <= 0."""
    pass

def credit(account: dict, amount: float) -> float:
    """Ajoute de l'argent au compte."""
    if amount <= 0:
        raise InvalidAmountError("Le montant à créditer doit être strictement positif.")
    key = "solde" if "solde" in account else "balance"
    account[key] += amount
    return account[key]

def debit(account: dict, amount: float) -> float:
    """Retire de l'argent du compte après vérification du solde."""
    if amount <= 0:
        raise InvalidAmountError("Le montant à débiter doit être strictement positif.")
    key = "solde" if "solde" in account else "balance"
    if account[key] < amount:
        raise InsufficientBalanceError(
            f"Solde insuffisant ({account[key]:.2f}€ disponibles, {amount:.2f}€ requis)."
        )
    account[key] -= amount
    return account[key]