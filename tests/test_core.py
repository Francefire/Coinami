import pytest

from src.core.block import Block, BlockHeader
from src.core.chain import Chain
from src.core.transaction import Transaction
from src.crypto.wallet import Wallet


# ---------------------------------------------------------------------------
# Fixtures partagées
# ---------------------------------------------------------------------------

@pytest.fixture
def wallet():
    return Wallet()


@pytest.fixture
def valid_tx(wallet):
    tx = Transaction(
        type_tx="transfer",
        sender_address=wallet.address,
        receiver_address="ab" * 20,
        amount=10.0,
        nonce=1,
        payload={"public_key": wallet.public_key_bytes.hex()},
    )
    tx.signature = wallet.sign_tx(tx)
    return tx


@pytest.fixture
def chain():
    return Chain(difficulty=2)


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TestTransaction:
    def test_valid_transaction(self, valid_tx):
        assert valid_tx.is_valid() is True

    def test_negative_amount_is_invalid(self, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=-1.0,
            nonce=1,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        tx.signature = wallet.sign_tx(tx)
        assert tx.is_valid() is False

    def test_zero_amount_is_invalid(self, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=0.0,
            nonce=1,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        tx.signature = wallet.sign_tx(tx)
        assert tx.is_valid() is False

    def test_missing_signature_is_invalid(self, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        assert tx.is_valid() is False

    def test_missing_public_key_is_invalid(self, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={}
        )
        tx.signature = "fakesig"
        assert tx.is_valid() is False

    def test_wrong_signature_is_invalid(self, wallet):
        tx = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        tx.signature = "00" * 32  # signature invalide
        assert tx.is_valid() is False

    def test_hash_changes_when_amount_changes(self, wallet):
        tx1 = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=5.0,
            nonce=1,
            payload={}
        )
        tx2 = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="ab" * 20,
            amount=6.0,
            nonce=1,
            payload={}
        )
        assert tx1.calculate_hash() != tx2.calculate_hash()

    def test_to_dict_excludes_signature(self, valid_tx):
        d = valid_tx.to_dict()
        assert "signature" not in d
        assert d["amount"] == valid_tx.amount

    def test_to_network_dict_includes_signature(self, valid_tx):
        d = valid_tx.to_network_dict()
        assert "signature" in d
        assert d["signature"] == valid_tx.signature

    def test_from_dict_roundtrip(self, valid_tx):
        d = valid_tx.to_network_dict()
        tx2 = Transaction.from_dict(d)
        assert tx2.calculate_hash() == valid_tx.calculate_hash()
        assert tx2.signature == valid_tx.signature
        assert tx2.is_valid() is True


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

class TestBlock:
    def test_merkle_root_empty_transactions(self):
        block = Block.create("0" * 64, [])
        assert block.b_header.merkle_root == "0" * 64

    def test_merkle_root_single_tx(self, valid_tx):
        block = Block.create("0" * 64, [valid_tx])
        assert block.b_header.merkle_root == valid_tx.calculate_hash()

    def test_merkle_root_two_txs(self, wallet, valid_tx):
        tx2 = Transaction(
            type_tx="transfer",
            sender_address=wallet.address,
            receiver_address="cd" * 20,
            amount=2.0,
            nonce=2,
            payload={"public_key": wallet.public_key_bytes.hex()}
        )
        tx2.signature = wallet.sign_tx(tx2)
        block = Block.create("0" * 64, [valid_tx, tx2])
        assert len(block.b_header.merkle_root) == 64
        assert block.b_header.merkle_root != "0" * 64

    def test_hash_changes_with_nonce(self, valid_tx):
        block = Block.create("0" * 64, [valid_tx])
        h1 = block.calculate_hash()
        block.b_header.nonce += 1
        h2 = block.calculate_hash()
        assert h1 != h2

    def test_from_dict_roundtrip(self, valid_tx):
        block = Block.create("0" * 64, [valid_tx])
        block_dict = block.to_network_dict()
        block2 = Block.from_dict(block_dict)
        assert block2.calculate_hash() == block.calculate_hash()
        assert len(block2.transactions) == 1


# ---------------------------------------------------------------------------
# Chain
# ---------------------------------------------------------------------------

class TestChain:
    def test_genesis_block_exists(self, chain):
        assert len(chain.blocks) == 1

    def test_mine_block_adds_block(self, chain, valid_tx):
        chain.pending_transactions.append(valid_tx)
        chain.mine_block()
        assert len(chain.blocks) == 2

    def test_mined_block_satisfies_pow(self, chain, valid_tx):
        chain.pending_transactions.append(valid_tx)
        block = chain.mine_block()
        assert block.calculate_hash().startswith("0" * chain.difficulty)

    def test_mine_clears_pending_transactions(self, chain, valid_tx):
        chain.pending_transactions.append(valid_tx)
        chain.mine_block()
        assert len(chain.pending_transactions) == 0

    def test_is_chain_valid_on_fresh_chain(self, chain):
        assert chain.is_chain_valid() is True

    def test_is_chain_valid_after_mining(self, chain, valid_tx):
        chain.pending_transactions.append(valid_tx)
        chain.mine_block()
        assert chain.is_chain_valid() is True

    def test_tampered_block_fails_validation(self, chain, valid_tx):
        chain.pending_transactions.append(valid_tx)
        chain.mine_block()
        # Modifier directement un champ du bloc miné
        chain.blocks[1].b_header.nonce = 9999999
        assert chain.is_chain_valid() is False

    def test_add_block_rejects_wrong_prev_hash(self, chain, valid_tx):
        block = Block.create("wronghash" * 7, [valid_tx])
        # Forcer un hash valide PoW
        target = "0" * chain.difficulty
        while not block.calculate_hash().startswith(target):
            block.b_header.nonce += 1
        assert chain.add_block(block) is False

    def test_add_block_rejects_insufficient_pow(self, chain, valid_tx):
        prev_hash = chain.last_block.calculate_hash()
        block = Block.create(prev_hash, [valid_tx])
        block.b_header.nonce = 0  # nonce non miné
        assert chain.add_block(block) is False

    def test_multiple_blocks_chain(self, wallet, chain):
        for i in range(3):
            tx = Transaction(
                type_tx="transfer",
                sender_address=wallet.address,
                receiver_address="ff" * 20,
                amount=float(i + 1),
                nonce=i,
                payload={"public_key": wallet.public_key_bytes.hex()}
            )
            tx.signature = wallet.sign_tx(tx)
            chain.pending_transactions.append(tx)
            chain.mine_block()
        assert len(chain.blocks) == 4
        assert chain.is_chain_valid() is True
