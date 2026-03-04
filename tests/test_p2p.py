import pytest
from fastapi.testclient import TestClient

import src.p2p.node as node_module
from src.core.block import Block
from src.core.transaction import Transaction
from src.crypto.wallet import Wallet
from src.p2p.node import Node, app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_node():
    """Réinitialise le node global avant chaque test."""
    node_module.node = Node(port=9999, difficulty=2)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def wallet():
    return Wallet()


@pytest.fixture
def valid_tx(wallet):
    tx = Transaction(
        type_tx="transfer",
        sender_address=wallet.address,
        receiver_address="ab" * 20,
        amount=5.0,
        nonce=1,
        payload={"public_key": wallet.public_key_bytes.hex()},
    )
    tx.signature = wallet.sign_tx(tx)
    return tx


# ---------------------------------------------------------------------------
# GET /chain
# ---------------------------------------------------------------------------

class TestGetChain:
    def test_initial_chain_has_genesis(self, client):
        resp = client.get("/chain")
        assert resp.status_code == 200
        data = resp.json()
        assert data["length"] == 1
        assert len(data["blocks"]) == 1


# ---------------------------------------------------------------------------
# POST /peers & GET /peers
# ---------------------------------------------------------------------------

class TestPeers:
    def test_add_peers(self, client):
        resp = client.post("/peers", json={"peers": ["http://localhost:5001"]})
        assert resp.status_code == 201
        assert "http://localhost:5001" in resp.json()["added"]

    def test_add_duplicate_peer_not_counted_twice(self, client):
        client.post("/peers", json={"peers": ["http://localhost:5001"]})
        resp = client.post("/peers", json={"peers": ["http://localhost:5001"]})
        assert resp.json()["total"] == 1

    def test_list_peers(self, client):
        client.post("/peers", json={"peers": ["http://localhost:5001"]})
        resp = client.get("/peers")
        assert "http://localhost:5001" in resp.json()["peers"]


# ---------------------------------------------------------------------------
# POST /tx
# ---------------------------------------------------------------------------

class TestPostTransaction:
    def test_valid_tx_accepted(self, client, valid_tx):
        resp = client.post("/tx", json=valid_tx.to_network_dict())
        assert resp.status_code == 201
        assert resp.json()["status"] == "accepted"

    def test_tx_hash_returned(self, client, valid_tx):
        resp = client.post("/tx", json=valid_tx.to_network_dict())
        assert resp.json()["hash"] == valid_tx.calculate_hash()

    def test_duplicate_tx_rejected(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        resp = client.post("/tx", json=valid_tx.to_network_dict())
        assert resp.status_code == 400

    def test_invalid_tx_rejected(self, client, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        tx.signature = ""  # pas de signature
        resp = client.post("/tx", json=tx.to_network_dict())
        assert resp.status_code == 400

    def test_malformed_payload_rejected(self, client):
        resp = client.post("/tx", json={"broken": "data"})
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /mempool
# ---------------------------------------------------------------------------

class TestMempool:
    def test_mempool_empty_initially(self, client):
        resp = client.get("/mempool")
        assert resp.json()["length"] == 0

    def test_mempool_grows_after_tx(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        resp = client.get("/mempool")
        assert resp.json()["length"] == 1


# ---------------------------------------------------------------------------
# GET /mine
# ---------------------------------------------------------------------------

class TestMine:
    def test_mine_empty_mempool_rejected(self, client):
        resp = client.get("/mine")
        assert resp.status_code == 400

    def test_mine_adds_block(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        resp = client.get("/mine")
        assert resp.status_code == 200
        assert resp.json()["status"] == "mined"

    def test_mine_clears_mempool(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        client.get("/mine")
        resp = client.get("/mempool")
        assert resp.json()["length"] == 0

    def test_mine_produces_valid_pow(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        resp = client.get("/mine")
        block_hash = resp.json()["hash"]
        assert block_hash.startswith("00")

    def test_chain_grows_after_mine(self, client, valid_tx):
        client.post("/tx", json=valid_tx.to_network_dict())
        client.get("/mine")
        resp = client.get("/chain")
        assert resp.json()["length"] == 2


# ---------------------------------------------------------------------------
# GET /state
# ---------------------------------------------------------------------------

class TestState:
    def test_state_endpoint_returns_balances(self, client):
        resp = client.get("/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "balances" in data
        assert "escrow" in data


# ---------------------------------------------------------------------------
# POST /block (receive_block)
# ---------------------------------------------------------------------------

class TestPostBlock:
    def test_valid_mined_block_accepted(self, client, valid_tx):
        """Mine un bloc côté node, le sérialise et le renvoie via /block."""
        node = node_module.node
        node.mempool.append(valid_tx)
        block = node.chain.mine_block()
        block_dict = block.to_network_dict()

        # Réinitialiser le nœud pour simuler la réception depuis un pair
        node_module.node = Node(port=9998, difficulty=2)
        client2 = TestClient(app)

        resp = client2.post("/block", json=block_dict)
        assert resp.status_code == 201
        assert resp.json()["status"] == "accepted"

    def test_malformed_block_rejected(self, client):
        resp = client.post("/block", json={"broken": "block"})
        assert resp.status_code in (400, 422)
