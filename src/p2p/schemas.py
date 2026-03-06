"""API request/response models for Coinami endpoints.

These Pydantic models work in conjunction with domain models
from src.core.* which are themselves Pydantic BaseModels.
"""

from pydantic import BaseModel, Field
from typing import Optional
from src.core.transaction import Transaction
from src.core.block import Block, BlockHeader


# ============================================================================
# Transaction Models (re-exported from domain)
# ============================================================================
# TransactionRequest and TransactionResponse use the domain Transaction model

class TransactionResponse(BaseModel):
    """Successful transaction submission response."""
    status: str = Field(description="Status: 'accepted' or error message")
    hash: str = Field(description="Hash of the submitted transaction")


# ============================================================================
# Block Models (re-exported from domain)
# ============================================================================
# BlockRequest and BlockResponse use the domain Block model

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
# Nonce Models
# ============================================================================

class NonceResponse(BaseModel):
    """Current nonce for an address — used by clients before building a transaction."""
    address: str = Field(description="The queried address")
    nonce: int = Field(description="Number of confirmed + pending transactions sent from this address")


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


# ============================================================================
# Claim Models
# ============================================================================

class ClaimResponse(BaseModel):
    """Response for a daily claim request."""
    status: str = Field(description="Status: 'claimed'")
    hash: str = Field(description="Hash of the claim transaction")
    balance: float = Field(description="Updated balance after claiming")
