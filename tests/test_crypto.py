import pytest

from src.crypto.utils import hash_data
from src.crypto.wallet import Wallet


class TestHashData:
    def test_dict_is_deterministic(self):
        """Le même dict produit toujours le même hash."""
        h1 = hash_data({"b": 2, "a": 1})
        h2 = hash_data({"a": 1, "b": 2})
        assert h1 == h2

    def test_string_input(self):
        h = hash_data("hello")
        assert len(h) == 64  # SHA-256 hex = 64 chars

    def test_different_data_gives_different_hash(self):
        assert hash_data({"a": 1}) != hash_data({"a": 2})


class TestWallet:

    def test_construct_with_given_private_key(self):
        newWallet1 = Wallet()
        newWallet2 = Wallet()
        w1 = Wallet(private_key=newWallet1._private_key)
        w2 = Wallet(private_key=newWallet2._private_key)
        assert w1.address == newWallet1.address
        assert w2.address == newWallet2.address
        assert w1.public_key_bytes == newWallet1.public_key_bytes
        assert w2.public_key_bytes == newWallet2.public_key_bytes
        assert w1.public_key_bytes != w2.public_key_bytes

    def test_address_is_40_hex_chars_new_wallet(self):
        w = Wallet()
        assert len(w.address) == 40
        int(w.address, 16)  # doit être du hex valide

    def test_public_key_is_65_bytes(self):
        """Clé publique X962 non compressée : 1 octet de préfixe + 32 + 32."""
        w = Wallet()
        assert len(w.public_key_bytes) == 65
        assert w.public_key_bytes[0] == 0x04

    def test_two_wallets_have_different_addresses(self):
        w1, w2 = Wallet(), Wallet()
        assert w1.address != w2.address

    def test_sign_and_verify_valid(self):
        w = Wallet()

        class FakeTx:
            def calculate_hash(self):
                return "deadbeefcafe0123"

        sig = w.sign_tx(FakeTx())
        assert Wallet.verify("deadbeefcafe0123", sig, w.public_key_bytes) is True

    def test_verify_wrong_message(self):
        w = Wallet()

        class FakeTx:
            def calculate_hash(self):
                return "correct_message"

        sig = w.sign_tx(FakeTx())
        assert Wallet.verify("wrong_message", sig, w.public_key_bytes) is False

    def test_verify_wrong_key(self):
        w1, w2 = Wallet(), Wallet()

        class FakeTx:
            def calculate_hash(self):
                return "some_message"

        sig = w1.sign_tx(FakeTx())
        assert Wallet.verify("some_message", sig, w2.public_key_bytes) is False

    def test_verify_tampered_signature(self):
        w = Wallet()

        class FakeTx:
            def calculate_hash(self):
                return "message"

        sig = w.sign_tx(FakeTx())
        tampered = sig[:-4] + "0000"
        assert Wallet.verify("message", tampered, w.public_key_bytes) is False

    def test_verify_invalid_hex_signature(self):
        w = Wallet()
        assert Wallet.verify("message", "not-hex!!", w.public_key_bytes) is False
