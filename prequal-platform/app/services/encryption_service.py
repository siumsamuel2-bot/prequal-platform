import os
import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

AWS_KMS_KEY_ID = os.getenv("AWS_KMS_KEY_ID")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
USE_KMS = bool(AWS_KMS_KEY_ID)

_fernet: Optional[Fernet] = None


def _get_fernet_key() -> bytes:
    key_material = os.getenv("ENCRYPTION_KEY", os.getenv("SECRET_KEY", ""))
    if not key_material:
        logger.warning("No ENCRYPTION_KEY or SECRET_KEY set. Using temporary key for development.")
        return Fernet.generate_key()
    raw = key_material.encode()
    if len(raw) == 32 and _is_valid_fernet_key(key_material):
        return raw
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"prequal_salt",
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(raw))


def _is_valid_fernet_key(key_material: str) -> bool:
    try:
        Fernet(key_material)
        return True
    except Exception:
        return False


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_get_fernet_key())
    return _fernet


def encrypt_value(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None or plaintext == "":
        return None
    try:
        if USE_KMS:
            return _encrypt_kms(plaintext)
        return _encrypt_local(plaintext)
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_value(ciphertext: Optional[str]) -> Optional[str]:
    if ciphertext is None or ciphertext == "":
        return None
    try:
        if USE_KMS and ciphertext.startswith("aws:"):
            return _decrypt_kms(ciphertext)
        return _decrypt_local(ciphertext)
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise


def _encrypt_local(plaintext: str) -> str:
    f = _get_fernet()
    encrypted = f.encrypt(plaintext.encode())
    return encrypted.decode()


def _decrypt_local(ciphertext: str) -> str:
    f = _get_fernet()
    decrypted = f.decrypt(ciphertext.encode())
    return decrypted.decode()


def _encrypt_kms(plaintext: str) -> str:
    try:
        import boto3
        kms_client = boto3.client("kms", region_name=AWS_REGION)
        response = kms_client.encrypt(
            KeyId=AWS_KMS_KEY_ID,
            Plaintext=plaintext.encode(),
        )
        encrypted_base64 = base64.b64encode(response["CiphertextBlob"]).decode()
        return f"aws:{encrypted_base64}"
    except ImportError:
        logger.warning("boto3 not installed, falling back to local encryption")
        return _encrypt_local(plaintext)
    except Exception as e:
        logger.error(f"KMS encryption failed: {e}, falling back to local encryption")
        return _encrypt_local(plaintext)


def _decrypt_kms(ciphertext: str) -> str:
    try:
        import boto3
        kms_client = boto3.client("kms", region_name=AWS_REGION)
        ciphertext_bytes = base64.b64decode(ciphertext[4:])
        response = kms_client.decrypt(CiphertextBlob=ciphertext_bytes)
        return response["Plaintext"].decode()
    except ImportError:
        logger.warning("boto3 not installed, cannot decrypt KMS ciphertext")
        raise
    except Exception as e:
        logger.error(f"KMS decryption failed: {e}")
        raise