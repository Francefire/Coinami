"""Tests for the EventBus and the /events SSE endpoint."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import src.p2p.node as node_module
from src.p2p.events import EventBus
from src.p2p.node import Node, app


# ---------------------------------------------------------------------------
# EventBus unit tests
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_subscribe_returns_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        assert isinstance(q, asyncio.Queue)
        assert bus.subscriber_count == 1

    def test_unsubscribe_removes_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0

    def test_unsubscribe_missing_queue_is_noop(self):
        bus = EventBus()
        bus.unsubscribe(asyncio.Queue())  # should not raise

    def test_emit_delivers_to_all_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.emit("tx:received", {"hash": "abc123"})
        msg1 = q1.get_nowait()
        msg2 = q2.get_nowait()
        assert msg1["event"] == "tx:received"
        assert msg1["data"]["hash"] == "abc123"
        assert "timestamp" in msg1
        assert msg2["event"] == "tx:received"

    def test_emit_with_no_subscribers_is_noop(self):
        bus = EventBus()
        bus.emit("test:event")  # should not raise

    def test_emit_default_data_is_empty_dict(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.emit("state:updated")
        msg = q.get_nowait()
        assert msg["data"] == {}

    def test_stream_yields_sse_formatted_lines(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.emit("block:mined", {"hash": "def456"})

        # Run the async generator synchronously for one iteration
        gen = bus.stream(q)
        line = asyncio.run(gen.__anext__())

        assert line.startswith("event: block:mined\n")
        assert "data:" in line
        payload = json.loads(line.split("data: ")[1].strip())
        assert payload["event"] == "block:mined"


# ---------------------------------------------------------------------------
# /events SSE endpoint integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_node():
    """Reset the global node before each test."""
    node_module.node = Node(port=9999, difficulty=2)
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestSSEEndpoint:
    def test_events_endpoint_is_registered(self):
        """The /events route should exist in the app."""
        routes = [r.path for r in app.routes]
        assert "/events" in routes

    def test_node_has_event_bus(self):
        """Every Node instance should have an EventBus."""
        n = Node(port=1234)
        assert isinstance(n.events, EventBus)

    def test_receive_tx_emits_events(self, client):
        """Submitting a transaction should populate the event bus."""
        from src.crypto.wallet import Wallet
        from src.core.transaction import Transaction

        w = Wallet()
        tx = Transaction(
            type_tx="transfer",
            sender_address=w.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": w.public_key_bytes.hex()},
        )
        tx.signature = w.sign_tx(tx)

        # Subscribe before posting
        q = node_module.node.events.subscribe()
        client.post("/tx", json=tx.to_network_dict())

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_names = [e["event"] for e in events]
        assert "tx:received" in event_names
        assert "tx:validated" in event_names
        assert "mempool:updated" in event_names

    def test_rejected_tx_emits_rejected_event(self, client):
        """An invalid transaction should emit tx:received then tx:rejected."""
        from src.crypto.wallet import Wallet
        from src.core.transaction import Transaction

        w = Wallet()
        tx = Transaction(
            type_tx="transfer",
            sender_address=w.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": w.public_key_bytes.hex()},
        )
        tx.signature = ""  # invalid

        q = node_module.node.events.subscribe()
        client.post("/tx", json=tx.to_network_dict())

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_names = [e["event"] for e in events]
        assert "tx:received" in event_names
        assert "tx:rejected" in event_names

    def test_mine_emits_mining_events(self, client):
        """Mining should emit mining_started, mining_completed, state and mempool events."""
        from src.crypto.wallet import Wallet
        from src.core.transaction import Transaction

        w = Wallet()
        # Fund the sender so the transfer passes contract validation at mining time
        node_module.node.state.balances[w.address] = 100.0
        tx = Transaction(
            type_tx="transfer",
            sender_address=w.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": w.public_key_bytes.hex()},
        )
        tx.signature = w.sign_tx(tx)
        client.post("/tx", json=tx.to_network_dict())

        q = node_module.node.events.subscribe()
        client.get("/mine")

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_names = [e["event"] for e in events]
        assert "block:mining_started" in event_names
        assert "block:mining_completed" in event_names
        assert "state:updated" in event_names
        assert "mempool:updated" in event_names

    def test_peer_added_emits_event(self, client):
        q = node_module.node.events.subscribe()
        client.post("/peers", json={"peers": ["http://localhost:6000"]})

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        event_names = [e["event"] for e in events]
        assert "peer:added" in event_names
