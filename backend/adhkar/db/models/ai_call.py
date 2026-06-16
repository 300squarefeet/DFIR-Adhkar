"""AiCall: audit log row for every LLM invocation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from adhkar.db.base import Base
from adhkar.db.models._common import IdMixin


class AiCall(Base, IdMixin):
    __tablename__ = "ai_calls"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    case_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    # purpose: summarize_case | suggest_next_steps | explain_observable | freeform
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(String, nullable=False)
    response_text: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
