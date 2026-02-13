"""Fernet 对称加密工具"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import settings


class EncryptionService:
    """Fernet 对称加密服务"""

    def __init__(self):
        """初始化加密服务，从环境变量读取加密密钥"""
        encryption_key = os.getenv("ENCRYPTION_KEY", "")

        if not encryption_key:
            # 如果没有设置环境变量，使用 secret_key 作为后备
            encryption_key = settings.secret_key

        # 将密钥转换为 32 字节的 Fernet 密钥
        self._fernet = self._derive_fernet_key(encryption_key)

    def _derive_fernet_key(self, password: str) -> Fernet:
        """从密码派生 Fernet 密钥"""
        # 使用固定的 salt（生产环境应该使用随机 salt 并存储）
        # 这里为了简化，使用项目名称作为 salt
        salt = b"ai_write_helper_encryption_salt_v1"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """加密字符串"""
        if not plaintext:
            return ""
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_text: str) -> str:
        """解密字符串"""
        if not encrypted_text:
            return ""
        try:
            decrypted = self._fernet.decrypt(encrypted_text.encode())
            return decrypted.decode()
        except Exception:
            # 解密失败返回空字符串
            return ""


# 全局加密服务实例
encryption_service = EncryptionService()
