import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

class TokenVault:
    def __init__(self):
        # Hash the master key to ensure it's exactly 32 bytes for AES-256
        self.key = hashlib.sha256(settings.MASTER_ENCRYPTION_KEY.encode()).digest()

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes, bytes]:
        iv = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
        
        # We return a dummy empty byte string for the data_key to keep 
        # database schema compatibility with the old KMS envelope encryption.
        dummy_data_key = b""
        
        return (iv + ciphertext, dummy_data_key, iv)

    def decrypt(self, ciphertext: bytes, encrypted_data_key: bytes, iv: bytes) -> str:
        aesgcm = AESGCM(self.key)
        # Strip the IV if it was prepended to the ciphertext
        token_ct = ciphertext[len(iv):] if ciphertext.startswith(iv) else ciphertext
        plaintext = aesgcm.decrypt(iv, token_ct, None).decode()
        
        return plaintext

vault = TokenVault()