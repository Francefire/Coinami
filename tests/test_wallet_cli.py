from src.crypto.wallet import Wallet

def test_wallet_export_import():
    # 1. Generate new wallet
    w1 = Wallet()
    addr1 = w1.address
    priv1 = w1.export_private_key()

    # 2. Import into a new instance
    w2 = Wallet(private_key_hex=priv1)
    addr2 = w2.address
    priv2 = w2.export_private_key()

    assert addr1 == addr2
    assert priv1 == priv2
    assert len(priv1) == 64
