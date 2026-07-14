import os
import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

class TokenVault:
    def __init__(self):
        self.kms = boto3.client('kms')
        self.key_id = settings.KMS_KEY_ID

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes, bytes]:
        response = self.kms.generate_data_key(KeyId=self.key_id, KeySpec='AES_256')
        plaintext_data_key = response['Plaintext']
        encrypted_data_key = response['CiphertextBlob']
        
        iv = os.urandom(12)
        aesgcm = AESGCM(plaintext_data_key)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
        
        del plaintext_data_key
        return (iv + ciphertext, encrypted_data_key, iv)

    def decrypt(self, ciphertext: bytes, encrypted_data_key: bytes, iv: bytes) -> str:
        response = self.kms.decrypt(CiphertextBlob=encrypted_data_key)
        plaintext_data_key = response['Plaintext']
        
        aesgcm = AESGCM(plaintext_data_key)
        token_ct = ciphertext[len(iv):] if iv in ciphertext else ciphertext
        plaintext = aesgcm.decrypt(iv, token_ct, None).decode()
        
        del plaintext_data_key
        return plaintext

vault = TokenVault()