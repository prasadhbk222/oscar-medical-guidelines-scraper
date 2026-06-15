"""Phase 3: download every discovered PDF; persist outcome to `downloads`.

- Polite: reuses PoliteClient (bounded concurrency, throttle, retry+backoff).
- Resume-safe: skips files already on disk.
- Idempotent: one `downloads` row per policy (upserted by policy_id), so reruns
  don't accumulate duplicate rows.
- Failures are logged AND persisted (http_status + error), never swallowed.

Run: uv run python -m backend.pipeline.download
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select

from backend.app.config import settings
from backend.app.db import async_session
from backend.app.models import Download, Policy
from backend.pipeline.scraper import PoliteClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("download")


@dataclass
class Outcome:
    policy_id: int
    stored_location: str | None
    http_status: int | None
    error: str | None


def _filename(policy: Policy) -> str:
    slug = policy.source_page_url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^A-Za-z0-9_.-]", "_", slug) or "policy"
    return f"{policy.id}_{slug}.pdf"


async def _download_one(
    client: PoliteClient, policy: Policy
) -> Outcome:
    path = settings.pdf_dir / _filename(policy)
    rel = str(path.relative_to(settings.pdf_dir.parents[1]))

    if path.exists() and path.stat().st_size > 0:
        log.info("skip (cached) policy %s -> %s", policy.id, rel)
        return Outcome(policy.id, rel, 200, None)

    try:
        resp = await client.get(policy.pdf_url)
    except Exception as e:  # noqa: BLE001 - record transport failure, keep going
        log.warning("policy %s download failed: %s", policy.id, e)
        return Outcome(policy.id, None, None, f"{type(e).__name__}: {e}")

    if resp.status_code != 200:
        log.warning("policy %s HTTP %s", policy.id, resp.status_code)
        return Outcome(
            policy.id, None, resp.status_code, f"HTTP {resp.status_code}"
        )

    ctype = resp.headers.get("content-type", "")
    if "pdf" not in ctype.lower():
        log.warning("policy %s unexpected content-type %r", policy.id, ctype)
        return Outcome(
            policy.id, None, resp.status_code, f"unexpected content-type: {ctype}"
        )

    path.write_bytes(resp.content)
    log.info("downloaded policy %s (%d bytes) -> %s", policy.id, len(resp.content), rel)
    return Outcome(policy.id, rel, resp.status_code, None)


async def _persist(outcomes: list[Outcome]) -> None:
    """Upsert one row per policy_id (no DB unique constraint, so do it in Python)."""
    async with async_session() as session:
        existing = {
            d.policy_id: d
            for d in (await session.scalars(select(Download))).all()
        }
        for o in outcomes:
            row = existing.get(o.policy_id)
            if row is None:
                session.add(
                    Download(
                        policy_id=o.policy_id,
                        stored_location=o.stored_location,
                        http_status=o.http_status,
                        error=o.error,
                    )
                )
            else:
                row.stored_location = o.stored_location
                row.http_status = o.http_status
                row.error = o.error
        await session.commit()


async def download_all() -> list[Outcome]:
    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    async with async_session() as session:
        policies = (await session.scalars(select(Policy).order_by(Policy.id))).all()
    log.info("downloading %d PDFs", len(policies))

    async with PoliteClient() as client:
        outcomes = await asyncio.gather(
            *(_download_one(client, p) for p in policies)
        )
    await _persist(list(outcomes))
    return list(outcomes)


async def _main() -> None:
    outcomes = await download_all()
    ok = [o for o in outcomes if o.error is None]
    fail = [o for o in outcomes if o.error is not None]
    print(f"\n{'='*70}\nDOWNLOAD: {len(ok)} ok  |  {len(fail)} failed  (of {len(outcomes)})\n{'='*70}")
    for o in fail:
        print(f"  policy {o.policy_id}: status={o.http_status} error={o.error}")


if __name__ == "__main__":
    asyncio.run(_main())
