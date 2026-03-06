from __future__ import annotations

import time
from pydantic import BaseModel, Field, ConfigDict

from src.core.transaction import Transaction
from src.crypto.utils import hash_data


class BlockHeader(BaseModel):
    """Pydantic model for block headers."""
    prev_hash: str = Field(..., description="Hash of the previous block")
    merkle_root: str = Field(..., description="Merkle root of transactions")
    timestamp: float = Field(..., description="Timestamp when block was created")
    nonce: int = Field(default=0, description="Proof of work nonce")

    def to_dict(self) -> dict:
        return {
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }


class Block(BaseModel):
    """Pydantic model for blockchain blocks."""
    b_header: BlockHeader = Field(..., alias="header", description="Block header")
    transactions: list[Transaction] = Field(default_factory=list, description="List of transactions in the block")

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    def simplified_merkle_root(self) -> str:
        """Calcule une racine de Merkle simplifiée.

        Stratégie itérative : on hache les paires de hashs jusqu'à obtenir
        un seul hash. Si le nombre de hashs est impair, le dernier est dupliqué.
        Retourne "0" * 64 si la liste de transactions est vide.
        """
        hashes = [tx.calculate_hash() for tx in self.transactions]

        if not hashes:
            return "0" * 64

        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hash_data(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)
            ]

        return hashes[0]

    def calculate_hash(self) -> str:
        return hash_data(self.b_header.to_dict())

    def to_network_dict(self) -> dict:
        """Sérialise le bloc entier (header + transactions) pour envoi réseau."""
        header_dict = self.b_header.to_dict()
        header_dict["hash"] = self.calculate_hash()
        return {
            "header": header_dict,
            "transactions": [tx.to_network_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        h = data["header"]
        header = BlockHeader(
            prev_hash=h["prev_hash"],
            merkle_root=h["merkle_root"],
            timestamp=h["timestamp"],
            nonce=h["nonce"],
        )
        transactions = [Transaction.from_dict(t) for t in data.get("transactions", [])]
        return cls(b_header=header, transactions=transactions)

    @classmethod
    def create(cls, prev_hash: str, transactions: list[Transaction]) -> "Block":
        """Crée un bloc non miné avec merkle_root calculé et timestamp courant."""
        header = BlockHeader(
            prev_hash=prev_hash,
            merkle_root="",  # sera calculé juste après
            timestamp=time.time(),
            nonce=0,
        )
        block = cls(b_header=header, transactions=transactions)
        block.b_header.merkle_root = block.simplified_merkle_root()
        return block
