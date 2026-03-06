from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from src.contracts.state import State
from src.core.block import Block
from src.core.chain import Chain
from src.core.transaction import Transaction
from src.p2p.events import EventBus
from src.p2p.schemas import (
    TransactionResponse,
    BlockResponse,
    PeersRequest, PeersResponse, PeersListResponse,
    MempoolResponse,
    StateResponse,
    ChainResponse,
    MineResponse,
    SyncResponse,
    ClaimResponse,
    NonceResponse,
)


# ---------------------------------------------------------------------------
# Classe Node
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, port: int, difficulty: int = 3):
        self.port = port
        self.peers: list[str] = []
        self.mempool: list[Transaction] = []
        self.chain: Chain = Chain(difficulty=difficulty)
        self.state: State = State()
        self.seen_ids: set[str] = set()
        self.events: EventBus = EventBus()

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def receive_tx(self, tx: Transaction) -> bool:
        """Valide et ajoute une transaction au mempool.

        Retourne True si la transaction est nouvelle et valide.
        Anti-boucle : si le hash est déjà dans seen_ids, on ignore.
        """
        tx_hash = tx.calculate_hash()
        if tx_hash in self.seen_ids:
            return False

        self.events.emit("tx:received", {"hash": tx_hash, "type": tx.type_tx, "sender": tx.sender_address, "receiver": tx.receiver_address, "amount": tx.amount})

        if not tx.is_valid():
            self.events.emit("tx:rejected", {"hash": tx_hash, "reason": "invalid signature or structure"})
            return False

        self.seen_ids.add(tx_hash)
        self.mempool.append(tx)
        self.events.emit("tx:validated", {"hash": tx_hash, "mempool_size": len(self.mempool)})
        self.events.emit("mempool:updated", {"length": len(self.mempool)})
        return True

    async def broadcast_tx(self, tx_dict: dict) -> None:
        """Diffuse une transaction à tous les pairs."""
        self.events.emit("tx:broadcast", {"peers": len(self.peers)})
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer in self.peers:
                try:
                    await client.post(f"{peer}/tx", json=tx_dict)
                except Exception:
                    pass  # pair hors ligne — on continue

    # ------------------------------------------------------------------
    # Blocs
    # ------------------------------------------------------------------

    def receive_block(self, block: Block) -> bool:
        """Ajoute un bloc reçu du réseau et met à jour l'état.

        La merkle_root reçue est vérifiée avant l'ajout.
        Les transactions confirmées sont retirées du mempool.
        """
        block_hash = block.calculate_hash()
        if block_hash in self.seen_ids:
            return False

        self.events.emit("block:received", {"hash": block_hash, "tx_count": len(block.transactions)})

        # Vérification de la merkle_root
        if block.b_header.merkle_root != block.simplified_merkle_root():
            self.events.emit("block:rejected", {"hash": block_hash, "reason": "invalid merkle root"})
            return False

        if not self.chain.add_block(block):
            self.events.emit("block:rejected", {"hash": block_hash, "reason": "chain rejected block"})
            return False

        self.seen_ids.add(block_hash)

        # Mettre à jour l'état avec les transactions confirmées
        confirmed_hashes = []
        for tx in block.transactions:
            self.state.execute_tx(tx)
            confirmed_hashes.append(tx.calculate_hash())

        self.events.emit("state:updated", {"confirmed_tx": len(block.transactions)})

        # Purger le mempool des transactions confirmées
        confirmed = set(confirmed_hashes)
        self.mempool = [tx for tx in self.mempool if tx.calculate_hash() not in confirmed]

        self.events.emit("block:validated", {"hash": block_hash, "height": len(self.chain.blocks), "tx_count": len(block.transactions)})
        self.events.emit("mempool:updated", {"length": len(self.mempool)})

        return True

    async def broadcast_block(self, block_dict: dict) -> None:
        """Diffuse un bloc miné à tous les pairs."""
        self.events.emit("block:broadcast", {"peers": len(self.peers)})
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer in self.peers:
                try:
                    await client.post(f"{peer}/block", json=block_dict)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Synchronisation
    # ------------------------------------------------------------------

    async def sync_chain(self) -> None:
        """Remplace la chaîne locale par la plus longue chaîne valide trouvée chez les pairs."""
        self.events.emit("peer:sync_started", {"peers": len(self.peers)})
        replaced = False
        async with httpx.AsyncClient(timeout=5.0) as client:
            for peer in self.peers:
                try:
                    resp = await client.get(f"{peer}/chain")
                    data = resp.json()
                    candidate_blocks = [Block.from_dict(b) for b in data["blocks"]]

                    if len(candidate_blocks) <= len(self.chain.blocks):
                        continue

                    # Vérifier la validité de la chaîne candidate
                    candidate_chain = Chain(difficulty=self.chain.difficulty)
                    candidate_chain.blocks = candidate_blocks
                    if candidate_chain.is_chain_valid():
                        self.chain = candidate_chain
                        # Reconstruire l'état depuis la nouvelle chaîne
                        self.state = State()
                        for block in self.chain.blocks[1:]:  # skip genesis
                            for tx in block.transactions:
                                self.state.execute_tx(tx)
                        replaced = True
                        self.events.emit("peer:sync_replaced", {"peer": peer, "new_length": len(self.chain.blocks)})
                        self.events.emit("state:updated", {"reason": "chain replaced after sync"})
                except Exception:
                    pass
        self.events.emit("peer:sync_completed", {"replaced": replaced, "length": len(self.chain.blocks)})


# ---------------------------------------------------------------------------
# Application FastAPI (singleton par processus)
# ---------------------------------------------------------------------------

node: Node | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the node on app startup/shutdown."""
    global node
    # Startup
    node = Node(port=5000, difficulty=3)
    print(f"✓ Node initialized on port {node.port}")
    yield
    # Shutdown
    print("✓ Node shutdown")


app = FastAPI(title="Coinami Node", lifespan=lifespan)

# Add CORS middleware to handle preflight requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (can be restricted in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.post("/tx", status_code=201, response_model=TransactionResponse, tags=["Transactions"])
async def post_transaction(
    tx: Transaction
) -> TransactionResponse:
    """
    Submit a new transaction to the mempool.

    This endpoint:
    - Validates the transaction structure and signature
    - Adds it to the mempool
    - Broadcasts it to all connected peers
    - Returns the transaction hash

    **Validation Rules:**
    - Amount must be positive
    - Signature must be valid
    - Transaction must not have been received before
    """
    print(f"Received transaction from {tx.sender_address} to {tx.receiver_address} for amount {tx.amount}")
    accepted = node.receive_tx(tx)
    if not accepted:
        raise HTTPException(status_code=400, detail="Transaction invalid or already received")

    # Broadcast asynchrone aux pairs
    await node.broadcast_tx(tx.to_network_dict())
    return TransactionResponse(status="accepted", hash=tx.calculate_hash())


@app.post("/block", status_code=201, response_model=BlockResponse, tags=["Blocks"])
async def post_block(block: Block) -> BlockResponse:
    """Submit a newly mined block to the chain with validation and broadcast."""
    accepted = node.receive_block(block)
    if not accepted:
        raise HTTPException(status_code=400, detail="Block invalid or already received")

    await node.broadcast_block(block.to_network_dict())
    return BlockResponse(status="accepted", hash=block.calculate_hash())


@app.get("/chain", response_model=ChainResponse, tags=["Chain"])
def get_chain() -> ChainResponse:
    """Retrieve the complete blockchain with all blocks."""
    return ChainResponse(
        length=len(node.chain.blocks),
        blocks=[b.to_network_dict() for b in node.chain.blocks],
    )


@app.post("/peers", status_code=201, response_model=PeersResponse, tags=["Peers"])
def add_peers(peers_data: PeersRequest) -> PeersResponse:
    """Register new peer nodes to the network."""
    added = []
    for peer in peers_data.peers:
        if isinstance(peer, str) and peer not in node.peers:
            node.peers.append(peer)
            added.append(peer)
    if added:
        node.events.emit("peer:added", {"added": added, "total": len(node.peers)})
    return PeersResponse(added=added, total=len(node.peers))


@app.get("/peers", response_model=PeersListResponse, tags=["Peers"])
def list_peers() -> PeersListResponse:
    """List all connected peer nodes."""
    return PeersListResponse(peers=node.peers)


@app.get("/mine", response_model=MineResponse, tags=["Mining"])
async def mine() -> MineResponse:
    """Mine a new block with pending transactions and broadcast it."""
    if not node.mempool:
        raise HTTPException(status_code=400, detail="Mempool empty — nothing to mine")

    node.events.emit("block:mining_started", {"mempool_size": len(node.mempool)})

    node.chain.pending_transactions = list(node.mempool)
    block = node.chain.mine_block()
    node.mempool = []

    for tx in block.transactions:
        node.state.execute_tx(tx)

    block_dict = block.to_network_dict()
    block_hash = block.calculate_hash()
    node.seen_ids.add(block_hash)

    node.events.emit("block:mining_completed", {"hash": block_hash, "height": len(node.chain.blocks), "tx_count": len(block.transactions)})
    node.events.emit("state:updated", {"confirmed_tx": len(block.transactions)})
    node.events.emit("mempool:updated", {"length": 0})

    await node.broadcast_block(block_dict)

    return MineResponse(
        status="mined",
        hash=block_hash,
        block=block_dict
    )


@app.get("/mempool", response_model=MempoolResponse, tags=["Mempool"])
def get_mempool() -> MempoolResponse:
    """View all pending transactions in the mempool."""
    return MempoolResponse(
        length=len(node.mempool),
        transactions=[tx.to_network_dict() for tx in node.mempool]
    )


@app.get("/state", response_model=StateResponse, tags=["State"])
def get_state() -> StateResponse:
    """Get the current state with account balances and escrow."""
    return StateResponse(
        balances=node.state.balances,
        escrow=node.state.escrow
    )


@app.post("/claim", status_code=200, response_model=ClaimResponse, tags=["Transactions"])
async def post_claim(tx: Transaction) -> ClaimResponse:
    """
    Submit a daily claim for 50 COIN tokens.

    This endpoint immediately validates and executes the claim:
    - Transaction must have type_tx='claim', amount=50.0, sender==receiver
    - Signature must be valid
    - 24-hour cooldown must have passed since the last claim
    """
    tx_hash = tx.calculate_hash()
    node.events.emit("claim:received", {"hash": tx_hash, "address": tx.sender_address})

    if tx.type_tx != "claim" or tx.amount != 50.0 or tx.sender_address != tx.receiver_address:
        node.events.emit("claim:rejected", {"hash": tx_hash, "reason": "invalid claim parameters"})
        raise HTTPException(status_code=400, detail="Invalid claim transaction")
    if not tx.is_valid():
        node.events.emit("claim:rejected", {"hash": tx_hash, "reason": "invalid signature"})
        raise HTTPException(status_code=400, detail="Invalid signature")
    if not node.state.execute_tx(tx):
        node.events.emit("claim:rejected", {"hash": tx_hash, "reason": "24h cooldown not passed"})
        raise HTTPException(status_code=400, detail="Claim rejected: 24-hour cooldown has not passed")

    balance = node.state.get_balance(tx.sender_address)
    node.events.emit("claim:validated", {"hash": tx_hash, "address": tx.sender_address, "new_balance": balance})
    node.events.emit("state:updated", {"reason": "claim executed"})

    return ClaimResponse(
        status="claimed",
        hash=tx_hash,
        balance=balance,
    )


@app.get("/nonce/{address}", response_model=NonceResponse, tags=["Transactions"])
def get_nonce(address: str) -> NonceResponse:
    """
    Return the next nonce to use for a transaction from this address.

    Counts confirmed transactions across the whole chain plus any
    pending transactions already in the mempool, so the client can
    build and sign a transaction without risk of nonce collision.
    """
    confirmed = sum(
        1
        for block in node.chain.blocks
        for tx in block.transactions
        if tx.sender_address == address
    )
    pending = sum(1 for tx in node.mempool if tx.sender_address == address)
    return NonceResponse(address=address, nonce=confirmed + pending)


@app.post("/sync", response_model=SyncResponse, tags=["Sync"])
async def sync() -> SyncResponse:
    """Synchronize the blockchain with connected peers."""
    await node.sync_chain()
    return SyncResponse(
        status="synced",
        length=len(node.chain.blocks)
    )


@app.get("/events", tags=["Events"])
async def sse_events():
    """Server-Sent Events stream for real-time data-flow visualization.

    Clients receive JSON events for every lifecycle action:
    tx:received, tx:validated, tx:rejected, tx:broadcast,
    block:received, block:validated, block:rejected, block:broadcast,
    block:mining_started, block:mining_completed,
    claim:received, claim:validated, claim:rejected,
    peer:added, peer:sync_started, peer:sync_completed, peer:sync_replaced,
    mempool:updated, state:updated.
    """
    queue = node.events.subscribe()
    return StreamingResponse(
        node.events.stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Point d'entrée CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lance un nœud Coinami.")
    parser.add_argument("--port", type=int, default=5000, help="Port d'écoute (défaut: 5000)")
    parser.add_argument("--difficulty", type=int, default=3, help="Difficulté PoW (défaut: 3)")
    args = parser.parse_args()

    node = Node(port=args.port, difficulty=args.difficulty)
    uvicorn.run(app, host="0.0.0.0", port=args.port)
