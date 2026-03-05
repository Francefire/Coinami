import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.cli.controller import CLI_Controller
from src.crypto.wallet import Wallet

@pytest.fixture
def mock_keystore(tmp_path):
    filepath = tmp_path / "wallet.json"
    return filepath

def test_controller_balance_no_wallet(mock_keystore, capsys):
    controller = CLI_Controller(keystore_path=str(mock_keystore))
    controller.balance_cmd()
    captured = capsys.readouterr()
    assert "Aucun wallet trouvé" in captured.out

def test_controller_balance_with_wallet(mock_keystore, capsys):
    controller = CLI_Controller(keystore_path=str(mock_keystore))
    wallet = Wallet()
    # Manual save for test
    with open(mock_keystore, "w") as f:
        json.dump({"address": wallet.address, "encrypted_private_key": "...", "salt": "...", "nonce": 0}, f)
    
    with patch("src.cli.node_client.NodeClient.get_balance", return_value=50.0):
        controller.balance_cmd()
        captured = capsys.readouterr()
        assert f"Solde pour {wallet.address} : 50.0 COIN" in captured.out
