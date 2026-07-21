"""
SQLAlchemy ORM models for production-grade persistent storage.
Replaces in-memory pickle files with PostgreSQL + pgvector.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey,
    JSON, Index, Float, UniqueConstraint, event,
)
from sqlalchemy import Uuid as UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from database import Base, engine


# ────────────────────────────────────────────────────────────────────
#  Users & Auth
# ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default='user', nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sessions = relationship("QASession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index('ix_users_role_active', 'role', 'is_active'),
    )


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ────────────────────────────────────────────────────────────────────
#  Knowledge Graph Entities & Relations
# ────────────────────────────────────────────────────────────────────

class Entity(Base):
    __tablename__ = 'entities'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    open_time = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    outgoing_relations = relationship(
        "Relation", foreign_keys="Relation.head_entity_id",
        back_populates="head_entity", cascade="all, delete-orphan"
    )
    incoming_relations = relationship(
        "Relation", foreign_keys="Relation.tail_entity_id",
        back_populates="tail_entity"
    )
    text_segments = relationship("TextSegment", back_populates="entity")

    __table_args__ = (
        UniqueConstraint('name', 'entity_type', name='uq_entity_name_type'),
        Index('ix_entities_name_type', 'name', 'entity_type'),
    )


class Relation(Base):
    __tablename__ = 'relations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    head_entity_id = Column(Integer, ForeignKey('entities.id', ondelete='CASCADE'), nullable=False, index=True)
    tail_entity_id = Column(Integer, ForeignKey('entities.id', ondelete='CASCADE'), nullable=False, index=True)
    relation_type = Column(String(128), nullable=False, index=True)
    extra_attrs = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    head_entity = relationship("Entity", foreign_keys=[head_entity_id], back_populates="outgoing_relations")
    tail_entity = relationship("Entity", foreign_keys=[tail_entity_id], back_populates="incoming_relations")

    __table_args__ = (
        UniqueConstraint(
            'head_entity_id', 'tail_entity_id', 'relation_type',
            name='uq_relation_head_tail_type'
        ),
    )


# ────────────────────────────────────────────────────────────────────
#  Text Segments & Vector Embeddings
# ────────────────────────────────────────────────────────────────────

class TextSegment(Base):
    __tablename__ = 'text_segments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey('entities.id', ondelete='SET NULL'), nullable=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entity = relationship("Entity", back_populates="text_segments")
    vectors = relationship("VectorEmbedding", back_populates="segment", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_text_segments_category_name', 'category', 'name'),
    )


class VectorEmbedding(Base):
    __tablename__ = 'vector_embeddings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    segment_id = Column(Integer, ForeignKey('text_segments.id', ondelete='CASCADE'), nullable=False, index=True)
    # pgvector vector type; dimension aligned with model output
    embedding = Column(Text, nullable=False)
    dimension = Column(Integer, nullable=False, default=256)
    backend = Column(String(64), nullable=False, default='tfidf')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    segment = relationship("TextSegment", back_populates="vectors")

    __table_args__ = (
        Index('ix_vector_embeddings_backend_dim', 'backend', 'dimension'),
    )


# ────────────────────────────────────────────────────────────────────
#  QA Sessions & History
# ────────────────────────────────────────────────────────────────────

class QASession(Base):
    __tablename__ = 'qa_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    context_summary = Column(Text, nullable=True)
    device_fingerprint = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")
    histories = relationship("QAHistory", back_populates="session", cascade="all, delete-orphan")


class QAHistory(Base):
    __tablename__ = 'qa_histories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('qa_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    agent_used = Column(String(64), nullable=True)
    sources = Column(JSON, default=list)
    latency_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model_name = Column(String(64), nullable=True)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("QASession", back_populates="histories")

    __table_args__ = (
        Index('ix_qa_histories_created_at', 'created_at'),
    )


# ────────────────────────────────────────────────────────────────────
#  Audit Logs
# ────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index('ix_audit_logs_created_at', 'created_at'),
        Index('ix_audit_logs_action_resource', 'action', 'resource_type'),
    )


# ────────────────────────────────────────────────────────────────────
#  System Settings / Feature Flags
# ────────────────────────────────────────────────────────────────────

class SystemSetting(Base):
    __tablename__ = 'system_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ────────────────────────────────────────────────────────────────────
#  Auto-update timestamps hook
# ────────────────────────────────────────────────────────────────────

@event.listens_for(Base, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
