from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    pdf_url: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    source_page_url: Mapped[str] = mapped_column(String, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    downloads: Mapped[list["Download"]] = relationship(back_populates="policy")
    structured: Mapped[list["StructuredPolicy"]] = relationship(
        back_populates="policy"
    )


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )
    stored_location: Mapped[str | None] = mapped_column(String, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    policy: Mapped["Policy"] = relationship(back_populates="downloads")


class StructuredPolicy(Base):
    __tablename__ = "structured_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), unique=True, index=True
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    policy: Mapped["Policy"] = relationship(back_populates="structured")
