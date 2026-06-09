"""AES 对称加密工具"""
import base64
from typing import Union

from Cryptodome.Cipher import AES


class AESCipher:
    def __init__(self, key: str, iv: str) -> None:
        self.key = key[0:16].encode("utf-8")
        self.iv = iv.encode("utf-8")

    @staticmethod
    def _pad(text: str) -> str:
        text_length = len(text)
        amount_to_pad = AES.block_size - (text_length % AES.block_size)
        if amount_to_pad == 0:
            amount_to_pad = AES.block_size
        pad = chr(amount_to_pad)
        return text + pad * amount_to_pad

    @staticmethod
    def _unpad(text: str) -> str:
        pad = ord(text[-1])
        return text[:-pad]

    def encrypt(self, raw: str) -> bytes:
        raw = self._pad(raw).encode("utf-8")
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return base64.b64encode(cipher.encrypt(raw))

    def decrypt(self, enc: Union[str, bytes]) -> str:
        enc = base64.b64decode(enc)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return self._unpad(cipher.decrypt(enc).decode("utf-8"))
