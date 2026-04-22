import base64
from typing import Final

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Fixed key and IV used by Sigen Cloud
_ENCRYPT_KEY: Final[bytes] = (b"s" + b"i" + b"g" + b"e" + b"n") * 3 + b"p"
_ENCRYPT_IV: Final[bytes] = (b"s" + b"i" + b"g" + b"e" + b"n") * 3 + b"p"
_CIPHER: Final[Cipher] = Cipher(
    algorithms.AES(_ENCRYPT_KEY),
    modes.CBC(_ENCRYPT_IV),
)


def encrypt_password(password: str) -> str:
    """Encrypt a plaintext password using Sigen's AES-128-CBC logic."""
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(password.encode()) + padder.finalize()

    encryptor = _CIPHER.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()

    return base64.b64encode(ct).decode()
