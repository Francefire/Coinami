"""API request/response models for Coinami endpoints.

These Pydantic models:
- Auto-generate OpenAPI documentation
- Validate incoming requests
- Are easy to update when the project evolves
"""

from pydantic import BaseModel, Field
from typing import Optional


# ============================================================================
# Transaction Models
# ============================================================================

class TransactionRequest(BaseModel):
    """Request body for submitting a transaction."""
    type_tx: str = Field(..., description="Transaction type (e.g., 'transfer')")
    sender_address: str = Field(..., description="Address of the transaction sender")
    receiver_address: str = Field(..., description="Address of the transaction receiver")
    amount: float = Field(..., description="Amount to transfer", gt=0)
    nonce: int = Field(..., description="Transaction sequence number")
    payload: dict = Field(default_factory=dict, description="Additional transaction data (e.g., public_key)")
    signature: str = Field(default="", description="Digital signature of the transaction")

    model_config = {
        "json_schema_extra": {
            "example": {
                "type_tx": "transfer",
                "sender_address": "alice",
                "receiver_address": "bob",
                "amount": 10.5,
                "nonce": 1,
                "payload": {"public_key": "a1b2c3d4..."},
                "signature": "sig_hash_here"
            }
        }
    }


class TransactionResponse(BaseModel):
    """Successful transaction submission response."""
    status: str = Field(description="Status: 'accepted' or error message")
    hash: str = Field(description="Hash of the submitted transaction")


class BlockRequest(BaseModel):
    """Request body for submitting a block (simplified)."""
    # You can extend this based on your Block structure
    data: dict = Field(..., description="Block data")


class BlockResponse(BaseModel):
    """Successful block submission response."""
    status: str = Field(description="Status of block submission")
    hash: str = Field(description="Hash of the submitted block")


# ============================================================================
# Peers Models
# ============================================================================

class PeersRequest(BaseModel):
    """Request body for registering peers."""
    peers: list[str] = Field(..., description="List of peer URLs (e.g., 'http://localhost:5001')")

    model_config = {
        "json_schema_extra": {
            "example": {
                "peers": ["http://localhost:5001", "http://localhost:5002"]
            }
        }
    }


class PeersResponse(BaseModel):
    """Response for peer registration."""
    added: list[str] = Field(description="Newly added peer URLs")
    total: int = Field(description="Total number of connected peers")


class PeersListResponse(BaseModel):
    """Response for listing peers."""
    peers: list[str] = Field(description="List of all connected peer URLs")


# ============================================================================
# Mempool Models
# ============================================================================

class MempoolResponse(BaseModel):
    """Response for mempool query."""
    length: int = Field(description="Number of pending transactions")
    transactions: list[dict] = Field(description="List of pending transactions")


# ============================================================================
# State Models
# ============================================================================

class StateResponse(BaseModel):
    """Response for state query."""
    balances: dict = Field(description="Account balances")
    escrow: dict = Field(description="Escrow accounts")


# ============================================================================
# Chain Models
# ============================================================================

class ChainResponse(BaseModel):
    """Response for chain query."""
    length: int = Field(description="Number of blocks in the chain")
    blocks: list[dict] = Field(description="List of all blocks")


# ============================================================================
# Mine Models
# ============================================================================

class MineResponse(BaseModel):
    """Response for mining a block."""
    status: str = Field(description="Status: 'mined'")
    hash: str = Field(description="Hash of the newly mined block")
    block: dict = Field(description="The complete mined block")


# ============================================================================
# Sync Models
# ============================================================================

class SyncResponse(BaseModel):
    """Response for chain synchronization."""
    status: str = Field(description="Status: 'synced'")
    length: int = Field(description="Current chain length after sync")
