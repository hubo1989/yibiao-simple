"""
测试审计日志中间件的敏感字段过滤功能
"""
import pytest

from app.middleware.audit_middleware import sanitize_dict, _is_sensitive_field, _is_sensitive_value


class TestSensitiveFieldDetection:
    """测试敏感字段检测"""

    def test_exact_match_sensitive_fields(self):
        """测试精确匹配敏感字段"""
        assert _is_sensitive_field("password") is True
        assert _is_sensitive_field("api_key") is True
        assert _is_sensitive_field("secret") is True
        assert _is_sensitive_field("token") is True

    def test_pattern_match_sensitive_fields(self):
        """测试模式匹配敏感字段"""
        assert _is_sensitive_field("user_password") is True
        assert _is_sensitive_field("newPassword") is True
        assert _is_sensitive_field("secret_key") is True
        assert _is_sensitive_field("access_token") is True
        assert _is_sensitive_field("api_key") is True
        assert _is_sensitive_field("my_key") is False  # "my_key" 不是已知敏感模式

    def test_non_sensitive_fields(self):
        """测试非敏感字段"""
        assert _is_sensitive_field("username") is False
        assert _is_sensitive_field("title") is False
        assert _is_sensitive_field("content") is False
        assert _is_sensitive_field("monkey_key") is False  # "key" 不是结尾
        assert _is_sensitive_field("keynote") is False  # "key" 不是结尾


class TestSensitiveValueDetection:
    """测试敏感值检测"""

    def test_bearer_token(self):
        """测试 Bearer token 检测"""
        assert _is_sensitive_value("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9") is True

    def test_jwt_token(self):
        """测试 JWT token 检测"""
        assert _is_sensitive_value("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U") is True

    def test_long_random_string(self):
        """测试长随机字符串（可能是 API key）"""
        assert _is_sensitive_value("a" * 32) is True
        assert _is_sensitive_value("abc123def456ghi789jkl012mno345pq") is True

    def test_credit_card_format(self):
        """测试信用卡号格式"""
        assert _is_sensitive_value("4111-1111-1111-1111") is True
        assert _is_sensitive_value("4111 1111 1111 1111") is True
        assert _is_sensitive_value("4111111111111111") is True

    def test_password_mask(self):
        """测试密码掩码"""
        assert _is_sensitive_value("***") is True
        assert _is_sensitive_value("*****") is True

    def test_non_sensitive_values(self):
        """测试非敏感值"""
        assert _is_sensitive_value("hello world") is False
        assert _is_sensitive_value("user@example.com") is False
        assert _is_sensitive_value("123") is False


class TestSanitizeDict:
    """测试字典过滤功能"""

    def test_simple_dict_sanitization(self):
        """测试简单字典过滤"""
        data = {
            "username": "john",
            "password": "secret123",
            "email": "john@example.com",
        }
        result = sanitize_dict(data)

        assert result["username"] == "john"
        assert result["password"] == "***"
        assert result["email"] == "john@example.com"

    def test_nested_dict_sanitization(self):
        """测试嵌套字典过滤"""
        data = {
            "user": {
                "name": "John",
                "credentials": {
                    "api_key": "secret_key_value",
                    "token": "bearer_token_value",
                },
            },
        }
        result = sanitize_dict(data)

        assert result["user"]["name"] == "John"
        assert result["user"]["credentials"]["api_key"] == "***"
        assert result["user"]["credentials"]["token"] == "***"

    def test_list_of_dicts_sanitization(self):
        """测试字典列表过滤"""
        data = {
            "users": [
                {"name": "John", "password": "pass1"},
                {"name": "Jane", "password": "pass2"},
            ]
        }
        result = sanitize_dict(data)

        assert result["users"][0]["name"] == "John"
        assert result["users"][0]["password"] == "***"
        assert result["users"][1]["name"] == "Jane"
        assert result["users"][1]["password"] == "***"

    def test_sensitive_value_detection_in_dict(self):
        """测试字典中敏感值的检测"""
        data = {
            "username": "john",
            "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        }
        result = sanitize_dict(data)

        assert result["username"] == "john"
        assert result["auth_header"] == "***"

    def test_max_depth_protection(self):
        """测试最大递归深度保护"""
        # 创建深度嵌套的字典
        data = {"level": 0}
        current = data
        for i in range(1, 20):
            current["nested"] = {"level": i}
            current = current["nested"]

        result = sanitize_dict(data, max_depth=5)

        # 应该在达到最大深度时停止
        assert "_truncated" in str(result)

    def test_custom_sensitive_field_names(self):
        """测试各种敏感字段名变体"""
        data = {
            "new_password": "pass123",
            "old_password": "oldpass",
            "password_confirm": "confirm",
            "secret_key": "secret",
            "access_token": "token",
            "refresh_token": "refresh",
            "api_key_secret": "key",
            "credit_card": "4111111111111111",
            "cvv": "123",
            "ssn": "123-45-6789",
        }
        result = sanitize_dict(data)

        # 所有敏感字段都应被过滤
        for key in data:
            assert result[key] == "***", f"Field {key} should be sanitized"

    def test_preserve_non_sensitive_data(self):
        """测试保留非敏感数据"""
        data = {
            "title": "Test Project",
            "description": "This is a test",
            "tags": ["test", "sample"],
            "count": 42,
            "is_active": True,
        }
        result = sanitize_dict(data)

        assert result == data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
