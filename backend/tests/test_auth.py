"""认证模块单元测试"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.config import settings
from app.models.user import UserRole


class TestPasswordHashing:
    """密码哈希测试"""

    def test_password_hash_creates_different_hashes(self) -> None:
        """相同密码产生不同哈希（bcrypt 自动加盐）"""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2

    def test_verify_password_correct(self) -> None:
        """正确密码验证通过"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """错误密码验证失败"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert verify_password("wrong_password", hashed) is False

    def test_password_hash_format(self) -> None:
        """密码哈希格式正确（bcrypt 格式）"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        assert hashed.startswith("$2b$")


class TestAccessToken:
    """访问令牌测试"""

    def test_create_access_token_with_string_subject(self) -> None:
        """使用字符串主题创建访问令牌"""
        subject = str(uuid.uuid4())
        token = create_access_token(subject)
        assert token is not None
        assert isinstance(token, str)

    def test_create_access_token_with_dict_subject(self) -> None:
        """使用字典主题创建访问令牌"""
        subject = {"sub": str(uuid.uuid4()), "role": "editor"}
        token = create_access_token(subject)
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("role") == "editor"

    def test_create_access_token_with_custom_expiry(self) -> None:
        """使用自定义过期时间创建访问令牌"""
        subject = str(uuid.uuid4())
        expires_delta = timedelta(hours=1)
        token = create_access_token(subject, expires_delta=expires_delta)
        payload = decode_token(token)
        assert payload is not None
        exp = payload.get("exp")
        assert exp is not None

    def test_create_access_token_with_additional_claims(self) -> None:
        """创建包含额外声明的访问令牌"""
        subject = str(uuid.uuid4())
        additional_claims = {"role": "admin", "tenant_id": "test_tenant"}
        token = create_access_token(
            subject, additional_claims=additional_claims
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("role") == "admin"
        assert payload.get("tenant_id") == "test_tenant"

    def test_decode_valid_token(self) -> None:
        """解码有效令牌"""
        subject = str(uuid.uuid4())
        token = create_access_token(subject)
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("sub") == subject

    def test_decode_invalid_token(self) -> None:
        """解码无效令牌返回 None"""
        invalid_token = "invalid.token.here"
        payload = decode_token(invalid_token)
        assert payload is None

    def test_decode_expired_token(self) -> None:
        """解码过期令牌返回 None"""
        subject = str(uuid.uuid4())
        # 创建一个已经过期的令牌
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        to_encode = {"sub": subject, "exp": expired_time}
        expired_token = jwt.encode(
            to_encode, settings.secret_key, algorithm=settings.algorithm
        )
        payload = decode_token(expired_token)
        assert payload is None


class TestRefreshToken:
    """刷新令牌测试"""

    def test_create_refresh_token(self) -> None:
        """创建刷新令牌"""
        subject = str(uuid.uuid4())
        token = create_refresh_token(subject)
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("sub") == subject
        assert payload.get("type") == "refresh"

    def test_refresh_token_has_longer_expiry(self) -> None:
        """刷新令牌有过期时间"""
        subject = str(uuid.uuid4())
        access_token = create_access_token(subject)
        refresh_token = create_refresh_token(subject)

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload is not None
        assert refresh_payload is not None

        # 刷新令牌的过期时间应该更长
        assert refresh_payload.get("exp") > access_payload.get("exp")

    def test_refresh_token_with_custom_expiry(self) -> None:
        """使用自定义过期时间创建刷新令牌"""
        subject = str(uuid.uuid4())
        expires_delta = timedelta(days=30)
        token = create_refresh_token(subject, expires_delta=expires_delta)
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("type") == "refresh"

    def test_refresh_token_with_additional_claims(self) -> None:
        """创建包含额外声明的刷新令牌"""
        subject = str(uuid.uuid4())
        additional_claims = {"role": "editor"}
        token = create_refresh_token(
            subject, additional_claims=additional_claims
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("role") == "editor"
        assert payload.get("type") == "refresh"


class TestTokenPayload:
    """令牌载荷测试"""

    def test_token_contains_user_id(self) -> None:
        """令牌包含用户ID"""
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id))
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("sub") == str(user_id)

    def test_token_contains_role(self) -> None:
        """令牌包含角色信息"""
        subject = str(uuid.uuid4())
        token = create_access_token(
            subject, additional_claims={"role": UserRole.ADMIN.value}
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload.get("role") == UserRole.ADMIN.value

    def test_token_expiry_in_future(self) -> None:
        """令牌过期时间在未来"""
        subject = str(uuid.uuid4())
        token = create_access_token(subject)
        payload = decode_token(token)
        assert payload is not None
        exp = payload.get("exp")
        assert exp is not None
        now = datetime.now(timezone.utc).timestamp()
        assert exp > now
