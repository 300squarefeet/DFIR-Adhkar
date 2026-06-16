"""CaseEmbedding: pgvector row per closed case for similarity search."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class CaseEmbedding(Base, IdMixin):
    """One embedding row per case. Embedding stored as opaque text so this
    module stays portable across pgvector drivers; the dedicated similarity
    query uses raw SQL (`embedding::vector <=> $1::vector`)."""

    __tablename__ = "case_embeddings"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    case_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, unique=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    # serialized as '[0.1,0.2,...]' to match pgvector text repr
    embedding_text: Mapped[str] = mapped_column(String, nullable=False)
    source_excerpt: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
