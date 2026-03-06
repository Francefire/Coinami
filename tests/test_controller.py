import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.cli.controller import CLI_Controller
from src.crypto.wallet import Wallet
from src.core.transaction import Transaction

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


def test_controller_claim_success(mock_keystore, capsys):
    controller = CLI_Controller(keystore_path=str(mock_keystore))
    wallet = Wallet()

    with patch("src.cli.controller.getpass.getpass", return_value="secret"), \
         patch.object(controller.keystore, "load_wallet", return_value=wallet), \
         patch.object(controller.keystore, "get_last_nonce", return_value=7), \
         patch.object(controller.keystore, "update_nonce") as mock_update_nonce, \
         patch.object(controller.node_client, "broadcast_transaction", return_value="0xclaimhash") as mock_broadcast:
        controller.claim_cmd()

    tx_sent = mock_broadcast.call_args.args[0]
    assert isinstance(tx_sent, Transaction)
    assert tx_sent.type_tx == "claim"
    assert tx_sent.sender_address == wallet.address
    assert tx_sent.receiver_address == wallet.address
    assert tx_sent.amount == 50.0
    assert tx_sent.nonce == 7
    assert tx_sent.signature != ""
    mock_update_nonce.assert_called_once_with(8)

    captured = capsys.readouterr()
    assert "50 tokens réclamés" in captured.out
    assert "0xclaimhash" in captured.out


def test_controller_claim_no_wallet_file(mock_keystore, capsys):
    controller = CLI_Controller(keystore_path=str(mock_keystore))

    with patch("src.cli.controller.getpass.getpass", return_value="secret"), \
         patch.object(controller.keystore, "load_wallet", side_effect=FileNotFoundError):
        controller.claim_cmd()

    captured = capsys.readouterr()
    assert "Aucun wallet trouvé" in captured.out
