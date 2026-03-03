from __future__ import annotations

import argparse

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

from src.contracts.state import State
from src.core.block import Block
from src.core.chain import Chain
from src.core.transaction import Transaction


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
        if not tx.is_valid():
            return False
        self.seen_ids.add(tx_hash)
        self.mempool.append(tx)
        return True

    async def broadcast_tx(self, tx_dict: dict) -> None:
        """Diffuse une transaction à tous les pairs."""
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

        # Vérification de la merkle_root
        if block.b_header.merkle_root != block.simplified_merkle_root():
            return False

        if not self.chain.add_block(block):
            return False

        self.seen_ids.add(block_hash)

        # Mettre à jour l'état avec les transactions confirmées
        for tx in block.transactions:
            self.state.execute_tx(tx)

        # Purger le mempool des transactions confirmées
        confirmed = {tx.calculate_hash() for tx in block.transactions}
        self.mempool = [tx for tx in self.mempool if tx.calculate_hash() not in confirmed]

        return True

    async def broadcast_block(self, block_dict: dict) -> None:
        """Diffuse un bloc miné à tous les pairs."""
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
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Application FastAPI (singleton par processus)
# ---------------------------------------------------------------------------

app = FastAPI(title="Coinami Node")
node: Node | None = None


@app.post("/tx", status_code=201)
async def post_transaction(data: dict):
    """Reçoit une transaction, la valide, l'ajoute au mempool et la diffuse."""
    try:
        tx = Transaction.from_dict(data)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    accepted = node.receive_tx(tx)
    if not accepted:
        raise HTTPException(status_code=400, detail="Transaction invalide ou déjà reçue.")

    # Broadcast asynchrone aux pairs
    await node.broadcast_tx(tx.to_network_dict())
    return {"status": "accepted", "hash": tx.calculate_hash()}


@app.post("/block", status_code=201)
async def post_block(data: dict):
    """Reçoit un bloc, le valide et l'ajoute à la chaîne."""
    try:
        block = Block.from_dict(data)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    accepted = node.receive_block(block)
    if not accepted:
        raise HTTPException(status_code=400, detail="Bloc invalide ou déjà reçu.")

    await node.broadcast_block(block.to_network_dict())
    return {"status": "accepted", "hash": block.calculate_hash()}


@app.get("/chain")
def get_chain():
    """Retourne la chaîne complète sérialisée."""
    return {
        "length": len(node.chain.blocks),
        "blocks": [b.to_network_dict() for b in node.chain.blocks],
    }


@app.post("/peers", status_code=201)
def add_peers(data: dict):
    """Enregistre de nouveaux pairs. Attend { "peers": ["http://host:port", ...] }."""
    new_peers: list[str] = data.get("peers", [])
    added = []
    for peer in new_peers:
        if isinstance(peer, str) and peer not in node.peers:
            node.peers.append(peer)
            added.append(peer)
    return {"added": added, "total": len(node.peers)}


@app.get("/peers")
def list_peers():
    return {"peers": node.peers}


@app.get("/mine")
async def mine():
    """Mine un nouveau bloc avec les transactions en attente et le diffuse."""
    if not node.mempool:
        raise HTTPException(status_code=400, detail="Mempool vide — rien à miner.")

    block = node.chain.mine_block()

    # Mettre à jour l'état avec le nouveau bloc
    for tx in block.transactions:
        node.state.execute_tx(tx)

    block_dict = block.to_network_dict()
    node.seen_ids.add(block.calculate_hash())
    await node.broadcast_block(block_dict)

    return {"status": "mined", "hash": block.calculate_hash(), "block": block_dict}


@app.get("/mempool")
def get_mempool():
    return {"length": len(node.mempool), "transactions": [tx.to_network_dict() for tx in node.mempool]}


@app.get("/state")
def get_state():
    return {"balances": node.state.balances, "escrow": node.state.escrow}


@app.post("/sync")
async def sync():
    """Déclenche la synchronisation de la chaîne avec les pairs."""
    await node.sync_chain()
    return {"status": "synced", "length": len(node.chain.blocks)}


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
