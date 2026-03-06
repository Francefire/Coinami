import getpass
from src.cli.keystore import Keystore
from src.cli.node_client import NodeClient
from src.crypto.wallet import Wallet
from src.core.transaction import Transaction

class CLI_Controller:
    def __init__(self, keystore_path: str = "wallet.json", node_url: str = "http://localhost:5000"):
        self.keystore = Keystore(keystore_path)
        self.node_client = NodeClient(node_url)

    def init_cmd(self):
        """Initialise un nouveau wallet."""
        passphrase = getpass.getpass("Choisissez une passphrase pour chiffrer votre clé : ")
        wallet = Wallet()
        self.keystore.save_wallet(wallet, passphrase)
        print(f"✓ Wallet généré avec succès !")
        print(f"Adresse publique : {wallet.address}")
        print(f"Sauvegardé dans : {self.keystore.filepath}")

    def balance_cmd(self, node_url: str | None = None):
        """Affiche le solde du wallet."""
        try:
            # On n'a pas besoin de passphrase pour lire l'adresse publique (en clair dans le JSON)
            import json
            with open(self.keystore.filepath, "r") as f:
                data = json.load(f)
            address = data["address"]
            
            balance = self.node_client.get_balance(address, custom_url=node_url)
            print(f"Solde pour {address} : {balance} COIN")
        except FileNotFoundError:
            print("Erreur : Aucun wallet trouvé. Utilisez 'init' d'abord.")
        except Exception as e:
            print(f"Erreur : {e}")

    def send_cmd(self, to: str, amount: float, node_url: str | None = None):
        """Envoie une transaction."""
        try:
            passphrase = getpass.getpass("Entrez votre passphrase pour déverrouiller la clé : ")
            wallet = self.keystore.load_wallet(passphrase)
            nonce = self.keystore.get_last_nonce()
            
            # Construction de la transaction
            tx = Transaction(
                type_tx="transfer",
                sender_address=wallet.address,
                receiver_address=to,
                amount=amount,
                nonce=nonce,
                payload={"public_key": wallet.public_key_bytes.hex()}
            )
            
            # Signature
            tx.signature = wallet.sign_tx(tx)
            
            # Envoi
            tx_hash = self.node_client.broadcast_transaction(tx, custom_url=node_url)
            
            # Mise à jour du nonce locale si succès
            self.keystore.update_nonce(nonce + 1)
            
            print(f"✓ Succès ! Transaction envoyée.")
            print(f"Hash : {tx_hash}")
            
        except FileNotFoundError:
            print("Erreur : Aucun wallet trouvé. Utilisez 'init' d'abord.")
        except ValueError as e:
            print(f"Erreur : {e}")
        except Exception as e:
            print(f"Erreur inattendue : {e}")

    def claim_cmd(self, node_url: str | None = None):
        """Réclame 50 tokens quotidiens (une fois par 24h)."""
        try:
            passphrase = getpass.getpass("Entrez votre passphrase pour déverrouiller la clé : ")
            wallet = self.keystore.load_wallet(passphrase)
            nonce = self.keystore.get_last_nonce()
            
            # Construction de la transaction claim
            tx = Transaction(
                type_tx="claim",
                sender_address=wallet.address,
                receiver_address=wallet.address,  # Claim to self
                amount=50.0,
                nonce=nonce,
                payload={"public_key": wallet.public_key_bytes.hex()}
            )
            
            # Signature
            tx.signature = wallet.sign_tx(tx)
            
            # Envoi
            tx_hash = self.node_client.broadcast_transaction(tx, custom_url=node_url)
            
            # Mise à jour du nonce locale si succès
            self.keystore.update_nonce(nonce + 1)
            
            print(f"✓ Succès ! 50 tokens réclamés.")
            print(f"Hash : {tx_hash}")
            
        except FileNotFoundError:
            print("Erreur : Aucun wallet trouvé. Utilisez 'init' d'abord.")
        except ValueError as e:
            print(f"Erreur : {e}")
        except Exception as e:
            print(f"Erreur inattendue : {e}")
