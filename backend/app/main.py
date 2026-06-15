"""FastAPI backend for the policy explorer UI.

Run: uv run uvicorn backend.app.main:app --reload
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import async_session
from backend.app.models import Download, Policy, StructuredPolicy

app = FastAPI(title="Oscar Guidelines Explorer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


@app.get("/api/policies")
async def list_policies(session: AsyncSession = Depends(get_session)):
    """List all policies with download + structured indicators."""
    rows = (
        await session.execute(
            select(
                Policy.id,
                Policy.title,
                Policy.pdf_url,
                Policy.source_page_url,
                Download.stored_location,
                Download.http_status,
                StructuredPolicy.id.label("structured_id"),
                StructuredPolicy.validation_error,
            )
            .outerjoin(Download, Download.policy_id == Policy.id)
            .outerjoin(StructuredPolicy, StructuredPolicy.policy_id == Policy.id)
            .order_by(Policy.id)
        )
    ).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "pdf_url": r.pdf_url,
            "source_page_url": r.source_page_url,
            "downloaded": r.stored_location is not None,
            "http_status": r.http_status,
            "has_structured": r.structured_id is not None
            and r.validation_error is None,
        }
        for r in rows
    ]


@app.get("/api/policies/{policy_id}")
async def get_policy(policy_id: int, session: AsyncSession = Depends(get_session)):
    policy = await session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(404, "policy not found")

    structured = (
        await session.scalars(
            select(StructuredPolicy).where(StructuredPolicy.policy_id == policy_id)
        )
    ).first()
    download = (
        await session.scalars(
            select(Download).where(Download.policy_id == policy_id)
        )
    ).first()

    return {
        "id": policy.id,
        "title": policy.title,
        "pdf_url": policy.pdf_url,
        "source_page_url": policy.source_page_url,
        "download": (
            {
                "stored_location": download.stored_location,
                "http_status": download.http_status,
                "error": download.error,
            }
            if download
            else None
        ),
        "structured": (
            {
                "structured_json": structured.structured_json,
                "validation_error": structured.validation_error,
                "llm_metadata": structured.llm_metadata,
            }
            if structured
            else None
        ),
    }
