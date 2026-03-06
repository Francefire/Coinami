from __future__ import annotations

import time
from src.core.transaction import Transaction


class State:
    def __init__(self):
        # { address: float }
        self.balances: dict[str, float] = {}
        # { escrow_id: { "sender": str, "receiver": str, "amount": float, "status": str } }
        self.escrow: dict[str, dict] = {}
        # { address: timestamp } - tracks last claim time for daily token rewards
        self.last_claims: dict[str, float] = {}

    def get_balance(self, address: str) -> float:
        return self.balances.get(address, 0.0)

    def execute_tx(self, tx: Transaction) -> bool:
        """Exécute une transaction et met à jour l'état.

        Types supportés :
        - "transfer"       : transfert simple entre deux adresses
        - "create_escrow"  : crée un séquestre (débite sender, fonds en attente)
        - "release_escrow" : libère les fonds vers le receiver
        - "cancel_escrow"  : rembourse les fonds vers le sender

        Retourne True si l'exécution a réussi, False sinon.
        """
        dispatch = {
            "transfer": self._handle_transfer,
            "create_escrow": self._handle_create_escrow,
            "release_escrow": self._handle_release_escrow,
            "cancel_escrow": self._handle_cancel_escrow,
            "claim": self._handle_claim,
        }

        handler = dispatch.get(tx.type_tx)
        if handler is None:
            return False

        return handler(tx)

    # ------------------------------------------------------------------
    # Handlers privés
    # ------------------------------------------------------------------

    def _handle_transfer(self, tx: Transaction) -> bool:
        if self.get_balance(tx.sender_address) < tx.amount:
            return False
        self.balances[tx.sender_address] = self.get_balance(tx.sender_address) - tx.amount
        self.balances[tx.receiver_address] = self.get_balance(tx.receiver_address) + tx.amount
        return True

    def _handle_create_escrow(self, tx: Transaction) -> bool:
        """Débite le sender et crée une entrée escrow en statut 'locked'.

        Le payload doit contenir "escrow_id" (str).
        """
        escrow_id = tx.payload.get("escrow_id")
        if not escrow_id:
            return False
        if escrow_id in self.escrow:
            return False  # ID déjà utilisé
        if self.get_balance(tx.sender_address) < tx.amount:
            return False

        self.balances[tx.sender_address] = self.get_balance(tx.sender_address) - tx.amount
        self.escrow[escrow_id] = {
            "sender": tx.sender_address,
            "receiver": tx.receiver_address,
            "amount": tx.amount,
            "status": "locked",
        }
        return True

    def _handle_release_escrow(self, tx: Transaction) -> bool:
        """Transfère les fonds de l'escrow vers le receiver.

        Le payload doit contenir "escrow_id" (str).
        """
        escrow_id = tx.payload.get("escrow_id")
        entry = self.escrow.get(escrow_id)
        if entry is None:
            return False
        if entry["status"] != "locked":
            return False
        if tx.sender_address != entry["receiver"]:
            return False
        
        self.balances[entry["receiver"]] = (
            self.get_balance(entry["receiver"]) + entry["amount"]
        )
        entry["status"] = "released"
        return True

    def _handle_cancel_escrow(self, tx: Transaction) -> bool:
        """Rembourse les fonds de l'escrow vers le sender.

        Le payload doit contenir "escrow_id" (str).
        """
        escrow_id = tx.payload.get("escrow_id")
        entry = self.escrow.get(escrow_id)
        if entry is None:
            return False
        if entry["status"] != "locked":
            return False
        if tx.sender_address != entry["sender"] or tx.receiver_address != entry["receiver"]:
            return False

        self.balances[entry["sender"]] = (
            self.get_balance(entry["sender"]) + entry["amount"]
        )
        entry["status"] = "refunded"
        return True

    def _handle_claim(self, tx: Transaction) -> bool:
        """Distributes 50 daily tokens to the sender.

        Validates:
        - Amount is exactly 50.0
        - Sender and receiver are the same address
        - At least 24 hours (86400 seconds) have passed since last claim

        Mints new tokens (no balance deduction).
        """
        # Validate amount is 50
        if tx.amount != 50.0:
            return False
        
        # Validate sender == receiver (claim to self)
        if tx.sender_address != tx.receiver_address:
            return False
        
        # Check 24-hour cooldown
        current_time = time.time()
        last_claim = self.last_claims.get(tx.sender_address, 0)
        time_since_last_claim = current_time - last_claim
        
        # 86400 seconds = 24 hours
        if time_since_last_claim < 86400:
            return False
        
        # Mint tokens and update claim timestamp
        self.balances[tx.sender_address] = self.get_balance(tx.sender_address) + 50.0
        self.last_claims[tx.sender_address] = current_time
        return True
