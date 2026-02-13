"""User 模型和 schema 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserInDB


# ── ORM 模型测试 ──────────────────────────────────────────────


class TestUserRole:
    def test_role_values(self):
        assert UserRole.ADMIN == "admin"
        assert UserRole.EDITOR == "editor"
        assert UserRole.REVIEWER == "reviewer"

    def test_role_is_str_enum(self):
        assert isinstance(UserRole.ADMIN, str)


class TestUserModel:
    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_columns_exist(self):
        cols = {c.name for c in User.__table__.columns}
        expected = {
            "id", "username", "email", "hashed_password",
            "role", "is_active", "created_at", "updated_at",
        }
        assert expected == cols

    def test_username_unique(self):
        col = User.__table__.c.username
        assert col.unique is True

    def test_email_unique(self):
        col = User.__table__.c.email
        assert col.unique is True

    def test_id_is_uuid(self):
        col = User.__table__.c.id
        assert col.primary_key

    def test_repr(self):
        user = User(username="testuser", email="t@t.com", hashed_password="x")
        assert repr(user) == "<User testuser>"


# ── Pydantic schema 测试 ──────────────────────────────────────


class TestUserCreate:
    def test_valid_creation(self):
        data = UserCreate(
            username="alice",
            email="alice@example.com",
            password="securepass123",
        )
        assert data.username == "alice"
        assert data.role == UserRole.EDITOR  # 默认值

    def test_custom_role(self):
        data = UserCreate(
            username="bob",
            email="bob@example.com",
            password="securepass123",
            role=UserRole.ADMIN,
        )
        assert data.role == UserRole.ADMIN

    def test_short_username_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(username="a", email="a@b.com", password="12345678")

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(username="alice", email="alice@b.com", password="short")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(username="alice", email="not-an-email", password="12345678")


class TestUserUpdate:
    def test_all_fields_optional(self):
        data = UserUpdate()
        assert data.username is None
        assert data.email is None
        assert data.role is None
        assert data.is_active is None

    def test_partial_update(self):
        data = UserUpdate(username="newname")
        assert data.username == "newname"
        assert data.email is None


class TestUserResponse:
    def test_from_attributes(self):
        now = datetime.now()
        uid = uuid.uuid4()
        data = UserResponse(
            id=uid,
            username="alice",
            email="alice@example.com",
            role=UserRole.EDITOR,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert data.id == uid
        assert "hashed_password" not in data.model_dump()

    def test_model_config_from_attributes(self):
        assert UserResponse.model_config.get("from_attributes") is True


class TestUserInDB:
    def test_includes_hashed_password(self):
        now = datetime.now()
        data = UserInDB(
            id=uuid.uuid4(),
            username="alice",
            email="alice@example.com",
            role=UserRole.EDITOR,
            is_active=True,
            created_at=now,
            updated_at=now,
            hashed_password="hashed_abc123",
        )
        assert data.hashed_password == "hashed_abc123"
