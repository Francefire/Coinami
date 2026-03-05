import httpx
from src.core.transaction import Transaction

class NodeClient:
    def __init__(self, default_node_url: str = "http://localhost:5000"):
        self.default_node_url = default_node_url

    def get_balance(self, address: str, custom_url: str | None = None) -> float:
        """Récupère le solde d'une adresse depuis le nœud."""
        url = (custom_url or self.default_node_url).rstrip("/")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{url}/state")
                response.raise_for_status()
                data = response.json()
                # Le nœud retourne {"balances": {...}, "escrow": {...}}
                return data["balances"].get(address, 0.0)
        except Exception as e:
            raise ConnectionError(f"Impossible de contacter le nœud à {url} : {e}")

    def broadcast_transaction(self, tx: Transaction, custom_url: str | None = None) -> str:
        """Envoie une transaction au nœud pour diffusion."""
        url = (custom_url or self.default_node_url).rstrip("/")
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{url}/tx", json=tx.to_network_dict())
                if response.status_code != 201:
                    raise ValueError(f"Le nœud a rejeté la transaction : {response.text}")
                return response.json()["hash"]
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Erreur HTTP lors de l'envoi : {e.response.text}")
        except Exception as e:
            raise ConnectionError(f"Erreur de communication avec le nœud : {e}")
