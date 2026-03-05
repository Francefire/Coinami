import base64
import json
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src.crypto.wallet import Wallet

class Keystore:
    def __init__(self, filepath: str = "wallet.json"):
        self.filepath = filepath

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return key

    def save_wallet(self, wallet: Wallet, passphrase: str, nonce: int = 0):
        """Sauvegarde le wallet de manière chiffrée avec une passphrase."""
        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        
        # On chiffre la clé privée hexadécimale
        encrypted_priv = f.encrypt(wallet.export_private_key().encode()).decode()
        
        data = {
            "address": wallet.address,
            "encrypted_private_key": encrypted_priv,
            "salt": salt.hex(),
            "nonce": nonce
        }
        
        with open(self.filepath, "w") as f_out:
            json.dump(data, f_out, indent=4)

    def load_wallet(self, passphrase: str) -> Wallet:
        """Charge le wallet en déchiffrant la clé avec la passphrase."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError("Keystore file not found.")
            
        with open(self.filepath, "r") as f_in:
            data = json.load(f_in)
            
        salt = bytes.fromhex(data["salt"])
        key = self._derive_key(passphrase, salt)
        f = Fernet(key)
        
        try:
            decrypted_priv = f.decrypt(data["encrypted_private_key"].encode()).decode()
            return Wallet(private_key_hex=decrypted_priv)
        except Exception:
            raise ValueError("Passphrase invalide ou fichier keystore corrompu.")

    def get_last_nonce(self) -> int:
         if not os.path.exists(self.filepath):
            return 0
         with open(self.filepath, "r") as f_in:
            data = json.load(f_in)
            return data.get("nonce", 0)

    def update_nonce(self, nonce: int):
        """Met à jour le nonce stocké dans le fichier sans modifier le reste."""
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "r") as f_in:
            data = json.load(f_in)
        data["nonce"] = nonce
        with open(self.filepath, "w") as f_out:
            json.dump(data, f_out, indent=4)
