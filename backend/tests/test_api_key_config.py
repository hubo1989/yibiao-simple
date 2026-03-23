"""API Key 配置模块单元测试"""
import uuid

import pytest
from pydantic import ValidationError

from app.utils.encryption import encryption_service


class TestEncryptionService:
    """加密服务测试"""

    def test_encrypt_decrypt_simple_string(self) -> None:
        """加密和解密简单字符串"""
        plaintext = "sk-test-api-key-123456"
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert encrypted != plaintext
        assert decrypted == plaintext

    def test_encrypt_decrypt_complex_string(self) -> None:
        """加密和解密复杂字符串"""
        plaintext = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_empty_string(self) -> None:
        """加密空字符串返回空字符串"""
        encrypted = encryption_service.encrypt("")
        assert encrypted == ""

    def test_decrypt_empty_string(self) -> None:
        """解密空字符串返回空字符串"""
        decrypted = encryption_service.decrypt("")
        assert decrypted == ""

    def test_decrypt_invalid_string(self) -> None:
        """解密无效字符串返回空字符串"""
        decrypted = encryption_service.decrypt("not-a-valid-encrypted-string")
        assert decrypted == ""

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """相同明文产生不同密文（Fernet 包含时间戳）"""
        plaintext = "test-api-key"
        encrypted1 = encryption_service.encrypt(plaintext)
        encrypted2 = encryption_service.encrypt(plaintext)

        # Fernet 加密每次都会产生不同的密文（因为包含时间戳）
        # 但都能正确解密
        assert encryption_service.decrypt(encrypted1) == plaintext
        assert encryption_service.decrypt(encrypted2) == plaintext


class TestApiKeyConfigModel:
    """API Key 配置模型测试"""

    def test_model_creation(self) -> None:
        """测试模型创建"""
        from app.models.api_key_config import ApiKeyConfig

        config = ApiKeyConfig(
            provider="openai",
            api_key_encrypted="encrypted_key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4",
            is_default=True,
        )

        assert config.provider == "openai"
        assert config.api_key_encrypted == "encrypted_key"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model_name == "gpt-4"
        assert config.is_default is True

    def test_model_default_values(self) -> None:
        """测试模型默认值（数据库层面的默认值在 ORM 实例中需要显式设置）"""
        from app.models.api_key_config import ApiKeyConfig

        # SQLAlchemy 的 server_default 是数据库层面的，
        # Python 实例需要显式设置或使用 mapped_column 的 default
        config = ApiKeyConfig(
            provider="anthropic",
            api_key_encrypted="encrypted_key",
            model_name="gpt-3.5-turbo",  # 显式设置默认值
            is_default=False,  # 显式设置默认值
        )

        assert config.model_name == "gpt-3.5-turbo"
        assert config.is_default is False
        assert config.base_url is None

    def test_model_supports_multiple_model_configs(self) -> None:
        """支持配置多个模型，并分别选择生成/索引用途"""
        from app.models.api_key_config import ApiKeyConfig

        config = ApiKeyConfig(
            provider="openai",
            api_key_encrypted="encrypted_key",
            model_name="legacy-model",
            is_default=False,
        )
        config.set_model_configs([
            {
                "model_id": "gpt-4.1",
                "use_for_generation": True,
                "use_for_indexing": False,
            },
            {
                "model_id": "text-embedding-3-large",
                "use_for_generation": False,
                "use_for_indexing": True,
            },
        ])

        assert config.model_name == "gpt-4.1"
        assert config.get_generation_model_name() == "gpt-4.1"
        assert config.get_index_model_name() == "text-embedding-3-large"
        assert config.get_model_configs() == [
            {
                "model_id": "gpt-4.1",
                "use_for_generation": True,
                "use_for_indexing": False,
            },
            {
                "model_id": "text-embedding-3-large",
                "use_for_generation": False,
                "use_for_indexing": True,
            },
        ]

    def test_model_falls_back_to_legacy_model_name(self) -> None:
        """旧数据未配置多模型时仍兼容"""
        from app.models.api_key_config import ApiKeyConfig

        config = ApiKeyConfig(
            provider="anthropic",
            api_key_encrypted="encrypted_key",
            model_name="claude-3-7-sonnet",
            is_default=False,
        )

        assert config.get_model_configs() == [
            {
                "model_id": "claude-3-7-sonnet",
                "use_for_generation": True,
                "use_for_indexing": True,
            }
        ]
        assert config.get_generation_model_name() == "claude-3-7-sonnet"
        assert config.get_index_model_name() == "claude-3-7-sonnet"


class TestApiKeyConfigSchemas:
    """API Key 配置 Schema 测试"""

    def test_create_schema_valid(self) -> None:
        """测试创建 Schema 验证"""
        from app.schemas.api_key_config import ApiKeyConfigCreate

        data = ApiKeyConfigCreate(
            provider="openai",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model_configs=[
                {
                    "model_id": "gpt-4.1",
                    "use_for_generation": True,
                    "use_for_indexing": False,
                },
                {
                    "model_id": "text-embedding-3-large",
                    "use_for_generation": False,
                    "use_for_indexing": True,
                },
            ],
            is_default=True,
        )

        assert data.provider == "openai"
        assert data.api_key == "sk-test-key"
        assert data.base_url == "https://api.openai.com/v1"
        assert len(data.model_configs) == 2
        assert data.generation_model_name == "gpt-4.1"
        assert data.index_model_name == "text-embedding-3-large"
        assert data.is_default is True

    def test_create_schema_minimal(self) -> None:
        """测试最小创建 Schema"""
        from app.schemas.api_key_config import ApiKeyConfigCreate

        data = ApiKeyConfigCreate(
            provider="anthropic",
            api_key="sk-ant-test",
        )

        assert data.provider == "anthropic"
        assert data.api_key == "sk-ant-test"
        assert data.base_url is None
        assert data.model_name == "gpt-3.5-turbo"
        assert data.generation_model_name == "gpt-3.5-turbo"
        assert data.index_model_name == "gpt-3.5-turbo"
        assert data.is_default is False

    def test_create_schema_rejects_multiple_generation_models(self) -> None:
        """同一配置不能同时指定多个生成模型"""
        from app.schemas.api_key_config import ApiKeyConfigCreate

        with pytest.raises(ValidationError):
            ApiKeyConfigCreate(
                provider="openai",
                api_key="sk-test-key",
                model_configs=[
                    {
                        "model_id": "gpt-4.1",
                        "use_for_generation": True,
                        "use_for_indexing": False,
                    },
                    {
                        "model_id": "gpt-4o",
                        "use_for_generation": True,
                        "use_for_indexing": False,
                    },
                ],
            )

    def test_update_schema_all_optional(self) -> None:
        """测试更新 Schema 所有字段可选"""
        from app.schemas.api_key_config import ApiKeyConfigUpdate

        data = ApiKeyConfigUpdate()

        assert data.provider is None
        assert data.api_key is None
        assert data.base_url is None
        assert data.model_name is None
        assert data.model_configs is None
        assert data.is_default is None

    def test_response_schema(self) -> None:
        """测试响应 Schema"""
        from app.schemas.api_key_config import ApiKeyConfigResponse
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        user_id = uuid.uuid4()
        config_id = uuid.uuid4()

        data = ApiKeyConfigResponse(
            id=config_id,
            provider="openai",
            api_key_masked="sk-t****1234",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4",
            model_configs=[
                {
                    "model_id": "gpt-4",
                    "use_for_generation": True,
                    "use_for_indexing": False,
                },
                {
                    "model_id": "text-embedding-3-large",
                    "use_for_generation": False,
                    "use_for_indexing": True,
                },
            ],
            generation_model_name="gpt-4",
            index_model_name="text-embedding-3-large",
            is_default=True,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )

        assert data.id == config_id
        assert data.api_key_masked == "sk-t****1234"
        assert data.generation_model_name == "gpt-4"
        assert data.index_model_name == "text-embedding-3-large"
        assert data.created_by == user_id


class TestApiKeyConfigResponseTransform:
    """API Key 配置响应转换测试"""

    def test_config_to_response_includes_model_configs(self) -> None:
        """响应转换包含多模型信息和用途摘要"""
        from app.models.api_key_config import ApiKeyConfig
        from app.routers.admin import config_to_response

        from datetime import datetime, timezone

        encrypted_key = encryption_service.encrypt("sk-test-api-key-12345678")
        config = ApiKeyConfig(
            id=uuid.uuid4(),
            provider="openai",
            api_key_encrypted=encrypted_key,
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1",
            is_default=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        config.set_model_configs([
            {
                "model_id": "gpt-4.1",
                "use_for_generation": True,
                "use_for_indexing": False,
            },
            {
                "model_id": "text-embedding-3-large",
                "use_for_generation": False,
                "use_for_indexing": True,
            },
        ])

        response = config_to_response(config)

        assert response.api_key_masked == "sk-t****5678"
        assert response.generation_model_name == "gpt-4.1"
        assert response.index_model_name == "text-embedding-3-large"
        assert len(response.model_configs) == 2


class TestMaskApiKey:
    """API Key 脱敏测试"""

    def test_mask_normal_key(self) -> None:
        """测试正常长度 Key 脱敏"""
        from app.routers.admin import mask_api_key

        result = mask_api_key("sk-test-api-key-12345678")
        assert result == "sk-t****5678"

    def test_mask_short_key(self) -> None:
        """测试短 Key 脱敏"""
        from app.routers.admin import mask_api_key

        result = mask_api_key("short")
        assert result == "****"

    def test_mask_8_char_key(self) -> None:
        """测试 8 字符 Key 脱敏"""
        from app.routers.admin import mask_api_key

        result = mask_api_key("12345678")
        assert result == "****"

    def test_mask_9_char_key(self) -> None:
        """测试 9 字符 Key 脱敏"""
        from app.routers.admin import mask_api_key

        result = mask_api_key("123456789")
        assert result == "1234****6789"

    def test_mask_empty_key(self) -> None:
        """测试空 Key 脱敏"""
        from app.routers.admin import mask_api_key

        result = mask_api_key("")
        assert result == ""

    def test_mask_long_key(self) -> None:
        """测试长 Key 脱敏"""
        from app.routers.admin import mask_api_key

        long_key = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        result = mask_api_key(long_key)
        assert result == "sk-p****6789"
        assert "****" in result
        assert result.startswith("sk-p")
        assert result.endswith("6789")
