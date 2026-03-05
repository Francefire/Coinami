import os
import pytest
from src.crypto.wallet import Wallet
from src.cli.keystore import Keystore

def test_keystore_save_load(tmp_path):
    keystore_path = tmp_path / "wallet.json"
    keystore = Keystore(filepath=str(keystore_path))
    
    passphrase = "super_secret_pass"
    wallet = Wallet()
    original_address = wallet.address
    
    # 1. Save
    keystore.save_wallet(wallet, passphrase, nonce=5)
    
    assert keystore_path.exists()
    
    # Check if file is encrypted (content is not the private key directly)
    with open(keystore_path, "r") as f:
        content = f.read()
        assert wallet.export_private_key() not in content
        assert "encrypted_private_key" in content

    # 2. Load
    loaded_wallet = keystore.load_wallet(passphrase)
    assert loaded_wallet.address == original_address
    assert keystore.get_last_nonce() == 5

    # 3. Wrong passphrase
    with pytest.raises(ValueError):
        keystore.load_wallet("wrong_pass")

    # 4. Update nonce
    keystore.update_nonce(6)
    assert keystore.get_last_nonce() == 6
