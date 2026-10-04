import reflex as rx

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class ConnectionProfile(Base):
    """Saved SQL Server settings; runtime passwords are never persisted."""

    __tablename__ = "sql_server_connection_profiles"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject", "name", name="uq_connection_profiles_owner_name"
        ),
        UniqueConstraint(
            "owner_subject", "id", name="uq_connection_profiles_owner_id"
        ),
        CheckConstraint(
            "length(trim(owner_subject)) > 0", name="owner_subject_required"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_required"),
        CheckConstraint("length(trim(host)) > 0", name="host_required"),
        CheckConstraint("length(trim(database)) > 0", name="database_required"),
        CheckConstraint("length(trim(username)) > 0", name="username_required"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),
        Index(
            "ix_connection_profiles_owner_updated",
            "owner_subject",
            "updated_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    owner_subject: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    host: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )
    port: Mapped[int] = mapped_column(
        Integer, default=1433, server_default="1433"
    )
    database: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    username: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SavedQuery(Base):
    """Optional profile references are constrained to the same owner."""

    __tablename__ = "saved_sql_queries"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject", "name", name="uq_saved_queries_owner_name"
        ),
        ForeignKeyConstraint(
            ["owner_subject", "connection_profile_id"],
            [
                "sql_server_connection_profiles.owner_subject",
                "sql_server_connection_profiles.id",
            ],
            name="fk_saved_queries_owned_connection_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "length(trim(owner_subject)) > 0", name="owner_subject_required"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_required"),
        CheckConstraint("length(trim(sql_text)) > 0", name="sql_text_required"),
        Index("ix_saved_queries_owner_updated", "owner_subject", "updated_at"),
        Index(
            "ix_saved_queries_owned_profile",
            "owner_subject",
            "connection_profile_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    owner_subject: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    sql_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    connection_profile_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MCPAccessToken(Base):
    """Only a SHA-256 digest and non-secret lifecycle metadata are stored."""

    __tablename__ = "mcp_access_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_mcp_access_tokens_token_hash"),
        CheckConstraint(
            "length(trim(owner_subject)) > 0", name="owner_subject_required"
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_required"),
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name="sha256_hex_digest"
        ),
        CheckConstraint(
            "hash_algorithm = 'sha256'", name="supported_hash_algorithm"
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="valid_expiration",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="valid_revocation",
        ),
        CheckConstraint(
            "last_used_at IS NULL OR last_used_at >= created_at",
            name="valid_last_use",
        ),
        Index(
            "ix_mcp_access_tokens_owner_created", "owner_subject", "created_at"
        ),
        Index(
            "ix_mcp_access_tokens_owner_revoked", "owner_subject", "revoked_at"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    owner_subject: Mapped[str] = mapped_column(
        String(255), default="", server_default=""
    )
    name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default=""
    )
    hash_algorithm: Mapped[str] = mapped_column(
        String(16), default="sha256", server_default="sha256"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
