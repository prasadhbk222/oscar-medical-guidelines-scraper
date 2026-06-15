"""Idempotency of the structuring upsert (one row per policy_id).

DB-backed: skipped automatically if Postgres isn't reachable, so `pytest` still runs
in a fresh clone without Docker.
"""

import asyncio

import pytest
from sqlalchemy import func, select

from backend.app.db import async_session, engine
from backend.app.models import Download, Policy, StructuredPolicy
from backend.pipeline.structure import _upsert


def _db_available() -> bool:
    async def ping():
        try:
            async with engine.connect():
                return True
        finally:
            await engine.dispose()  # don't leak pooled conns across event loops
    try:
        return asyncio.run(ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(), reason="Postgres not reachable (docker compose up)"
)


async def _seed_policy() -> int:
    async with async_session() as s:
        p = Policy(
            title="TEST idempotency",
            pdf_url="https://example.test/idempotency-probe.pdf",
            source_page_url="https://example.test/medical/probe",
        )
        s.add(p)
        await s.flush()
        pid = p.id
        await s.commit()
    return pid


async def _count_for(pid: int) -> int:
    async with async_session() as s:
        return await s.scalar(
            select(func.count()).select_from(StructuredPolicy).where(
                StructuredPolicy.policy_id == pid
            )
        )


async def _cleanup(pid: int) -> None:
    async with async_session() as s:
        for model in (StructuredPolicy, Download, Policy):
            for row in (await s.scalars(
                select(model).where(model.policy_id == pid)
                if model is not Policy
                else select(model).where(model.id == pid)
            )).all():
                await s.delete(row)
        await s.commit()


async def _run():
    await engine.dispose()  # fresh pool bound to this event loop
    pid = await _seed_policy()
    try:
        row = lambda err=None: StructuredPolicy(  # noqa: E731
            policy_id=pid,
            extracted_text="t",
            structured_json={"title": "t", "insurance_name": "Oscar Health",
                             "rules": {"rule_id": "1", "rule_text": "x"}},
            llm_metadata={"model": "test"},
            validation_error=err,
        )
        await _upsert([row()])
        await _upsert([row("changed")])  # second upsert must update, not duplicate
        assert await _count_for(pid) == 1
    finally:
        await _cleanup(pid)


def test_structuring_upsert_is_idempotent():
    asyncio.run(_run())
