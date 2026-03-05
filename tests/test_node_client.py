import httpx
import pytest
from unittest.mock import MagicMock, patch
from src.cli.node_client import NodeClient
from src.core.transaction import Transaction

def test_node_client_get_balance():
    client = NodeClient(default_node_url="http://fake-node")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"balances": {"0xabc": 100.0}, "escrow": {}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client.get", return_value=mock_response):
        balance = client.get_balance("0xabc")
        assert balance == 100.0
        
        balance_unknown = client.get_balance("0xdef")
        assert balance_unknown == 0.0

def test_node_client_broadcast():
    client = NodeClient(default_node_url="http://fake-node")
    tx = Transaction(
        type_tx="transfer",
        sender_address="0x123",
        receiver_address="0x456",
        amount=10.0,
        nonce=1,
        signature="fake-sig"
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"status": "accepted", "hash": "0xhash"}

    with patch("httpx.Client.post", return_value=mock_response):
        tx_hash = client.broadcast_transaction(tx)
        assert tx_hash == "0xhash"
