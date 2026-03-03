from __future__ import annotations

from src.crypto.utils import hash_data
from src.crypto.wallet import Wallet


class Transaction:
    def __init__(
        self,
        type_tx: str,
        sender_address: str,
        receiver_address: str,
        amount: float,
        nonce: int,
        payload: dict | None = None,
        signature: str = "",
    ):
        self.type_tx = type_tx
        self.sender_address = sender_address
        self.receiver_address = receiver_address
        self.amount = amount
        self.nonce = nonce
        self.payload = payload or {}
        self.signature = signature

    def to_dict(self) -> dict:
        """Sérialise la transaction SANS la signature (utilisé pour le hachage)."""
        return {
            "type_tx": self.type_tx,
            "sender_address": self.sender_address,
            "receiver_address": self.receiver_address,
            "amount": self.amount,
            "nonce": self.nonce,
            "payload": self.payload,
        }

    def calculate_hash(self) -> str:
        return hash_data(self.to_dict())

    def is_valid(self) -> bool:
        """Vérifie la validité de la transaction.

        Règles :
        - Le montant doit être strictement positif.
        - La signature doit être présente et vérifiable via la clé publique
          stockée dans payload["public_key"] (hex de la clé X962).
        """
        if self.amount <= 0:
            return False

        public_key_hex = self.payload.get("public_key")
        if not public_key_hex or not self.signature:
            return False

        try:
            public_key_bytes = bytes.fromhex(public_key_hex)
        except ValueError:
            return False

        return Wallet.verify(self.calculate_hash(), self.signature, public_key_bytes)
