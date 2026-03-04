import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec



class Wallet:
    def __init__(self, private_key: ec.EllipticCurvePrivateKey | None = None):
        if private_key is not None:
            self._private_key = private_key
        else:
            self._private_key = ec.generate_private_key(ec.SECP256K1())
        self._public_key = self._private_key.public_key()

        # Clé publique sérialisée au format X962 non compressé (65 octets : 04 + x + y)
        self.public_key_bytes: bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

        # Adresse dérivée : 20 derniers octets du SHA-256 de la clé publique (style Bitcoin simplifié)
        self.address: str = self._derive_address(self.public_key_bytes)

    @staticmethod
    def _derive_address(public_key_bytes: bytes) -> str:
        digest = hashlib.sha256(public_key_bytes).digest()
        return digest[-20:].hex()

    def sign_tx(self, tx) -> str:
        """Signe le hash d'une transaction et retourne la signature en hexadécimal."""
        message = tx.calculate_hash().encode("utf-8")
        signature = self._private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        return signature.hex()

    @staticmethod
    def verify(message: str, signature_hex: str, public_key_bytes: bytes) -> bool:
        """Vérifie une signature ECDSA.

        Args:
            message: Le message original (hash de la transaction).
            signature_hex: La signature en hexadécimal.
            public_key_bytes: La clé publique au format X962 non compressé.

        Returns:
            True si la signature est valide, False sinon.
        """
        try:
            public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256K1(), public_key_bytes
            )
            public_key.verify(
                bytes.fromhex(signature_hex),
                message.encode("utf-8"),
                ec.ECDSA(hashes.SHA256()),
            )
            return True
        except (InvalidSignature, ValueError):
            return False
