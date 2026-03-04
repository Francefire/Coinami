from __future__ import annotations

from pydantic import BaseModel, Field
from src.crypto.utils import hash_data
from src.crypto.wallet import Wallet


class Transaction(BaseModel):
    """Pydantic model for blockchain transactions."""
    type_tx: str = Field(..., description="Transaction type (e.g., 'transfer')")
    sender_address: str = Field(..., description="Address of the transaction sender")
    receiver_address: str = Field(..., description="Address of the transaction receiver")
    amount: float = Field(..., description="Amount to transfer")
    nonce: int = Field(..., description="Transaction sequence number")
    payload: dict = Field(default_factory=dict, description="Additional transaction data (e.g., public_key)")
    signature: str = Field(default="", description="Digital signature of the transaction")

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

    def to_network_dict(self) -> dict:
        """Sérialise la transaction AVEC la signature (pour envoi réseau)."""
        d = self.to_dict()
        d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            type_tx=data["type_tx"],
            sender_address=data["sender_address"],
            receiver_address=data["receiver_address"],
            amount=data["amount"],
            nonce=data["nonce"],
            payload=data.get("payload", {}),
            signature=data.get("signature", ""),
        )

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
