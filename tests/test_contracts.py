import pytest

from src.contracts.state import State
from src.core.transaction import Transaction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state():
    s = State()
    s.balances["alice"] = 100.0
    s.balances["bob"] = 0.0
    return s


def make_tx(type_tx, sender, receiver, amount, nonce=1, extra_payload=None):
    payload = extra_payload or {}
    payload.setdefault("public_key", "aabbcc")
    return Transaction(type_tx, sender, receiver, amount, nonce, payload)


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------

class TestTransfer:
    def test_valid_transfer(self, state):
        tx = make_tx("transfer", "alice", "bob", 40.0)
        assert state.execute_tx(tx) is True
        assert state.get_balance("alice") == 60.0
        assert state.get_balance("bob") == 40.0

    def test_insufficient_balance(self, state):
        tx = make_tx("transfer", "alice", "bob", 200.0)
        assert state.execute_tx(tx) is False
        assert state.get_balance("alice") == 100.0

    def test_transfer_to_new_address(self, state):
        tx = make_tx("transfer", "alice", "charlie", 10.0)
        assert state.execute_tx(tx) is True
        assert state.get_balance("charlie") == 10.0

    def test_unknown_tx_type(self, state):
        tx = make_tx("unknown_type", "alice", "bob", 10.0)
        assert state.execute_tx(tx) is False


# ---------------------------------------------------------------------------
# Escrow : Create
# ---------------------------------------------------------------------------

class TestCreateEscrow:
    def test_create_escrow_success(self, state):
        tx = make_tx("create_escrow", "alice", "bob", 30.0,
                     extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(tx) is True
        assert state.get_balance("alice") == 70.0
        assert state.escrow["e1"]["status"] == "locked"
        assert state.escrow["e1"]["amount"] == 30.0

    def test_create_escrow_insufficient_balance(self, state):
        tx = make_tx("create_escrow", "alice", "bob", 999.0,
                     extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(tx) is False
        assert "e1" not in state.escrow

    def test_create_escrow_duplicate_id(self, state):
        tx1 = make_tx("create_escrow", "alice", "bob", 10.0,
                      extra_payload={"escrow_id": "e1"})
        tx2 = make_tx("create_escrow", "alice", "bob", 10.0, nonce=2,
                      extra_payload={"escrow_id": "e1"})
        state.execute_tx(tx1)
        assert state.execute_tx(tx2) is False

    def test_create_escrow_missing_id(self, state):
        tx = make_tx("create_escrow", "alice", "bob", 10.0)
        assert state.execute_tx(tx) is False


# ---------------------------------------------------------------------------
# Escrow : Release
# ---------------------------------------------------------------------------

class TestReleaseEscrow:
    def test_release_sends_funds_to_receiver(self, state):
        create = make_tx("create_escrow", "alice", "bob", 20.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)

        # Receiver (bob) releases the escrow.
        release = make_tx("release_escrow", "bob", "alice", 0,
                          extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(release) is True
        assert state.get_balance("bob") == 20.0
        assert state.escrow["e1"]["status"] == "released"

    def test_sender_cannot_release_own_escrow(self, state):
        create = make_tx("create_escrow", "alice", "bob", 20.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)

        # Sender (alice) must not be allowed to release.
        sender_release = make_tx("release_escrow", "alice", "bob", 0,
                                 extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(sender_release) is False
        assert state.get_balance("alice") == 80.0
        assert state.get_balance("bob") == 0.0
        assert state.escrow["e1"]["status"] == "locked"

    def test_release_nonexistent_escrow(self, state):
        tx = make_tx("release_escrow", "alice", "bob", 0,
                     extra_payload={"escrow_id": "no_such_id"})
        assert state.execute_tx(tx) is False

    def test_double_release_is_rejected(self, state):
        create = make_tx("create_escrow", "alice", "bob", 20.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)
        release = make_tx("release_escrow", "bob", "alice", 0,
                          extra_payload={"escrow_id": "e1"})
        state.execute_tx(release)
        assert state.execute_tx(release) is False


# ---------------------------------------------------------------------------
# Escrow : Cancel
# ---------------------------------------------------------------------------

class TestCancelEscrow:
    def test_cancel_refunds_sender(self, state):
        create = make_tx("create_escrow", "alice", "bob", 25.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)

        cancel = make_tx("cancel_escrow", "alice", "bob", 0,
                         extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(cancel) is True
        assert state.get_balance("alice") == 100.0  # remboursée intégralement
        assert state.escrow["e1"]["status"] == "refunded"

    def test_cancel_nonexistent_escrow(self, state):
        tx = make_tx("cancel_escrow", "alice", "bob", 0,
                     extra_payload={"escrow_id": "ghost"})
        assert state.execute_tx(tx) is False

    def test_cannot_cancel_released_escrow(self, state):
        create = make_tx("create_escrow", "alice", "bob", 10.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)
        release = make_tx("release_escrow", "bob", "alice", 0,
                          extra_payload={"escrow_id": "e1"})
        state.execute_tx(release)

        cancel = make_tx("cancel_escrow", "alice", "bob", 0,
                         extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(cancel) is False

    def test_only_sender_or_receiver_can_cancel(self, state):
        # Initialiser charlie avec un solde
        state.balances["charlie"] = 50.0
        
        create = make_tx("create_escrow", "alice", "bob", 15.0,
                         extra_payload={"escrow_id": "e1"})
        state.execute_tx(create)
        
        # charlie essaie d'annuler l'escrow (n'est ni sender ni receiver)
        cancel_by_third_party = make_tx("cancel_escrow", "charlie", "alice", 0,
                                        extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(cancel_by_third_party) is False
        assert state.escrow["e1"]["status"] == "locked"  # Status inchangé
        
        # Seul alice (sender) peut annuler avec bob (receiver) comme receiver
        cancel_by_sender = make_tx("cancel_escrow", "alice", "bob", 0,
                                   extra_payload={"escrow_id": "e1"})
        assert state.execute_tx(cancel_by_sender) is True
        assert state.get_balance("alice") == 100.0  # Remboursée
        assert state.escrow["e1"]["status"] == "refunded"


def test_get_balance_unknown_address_is_zero():
    state = State()
    assert state.get_balance("nobody") == 0.0
