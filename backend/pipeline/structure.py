"""Phase 4: extract text -> OpenAI -> validated initial-criteria tree -> store.

For each selected policy:
  1. Extract text from the downloaded PDF.
  2. Locate the initial-criteria region (hint for the LLM; fallback signal).
  3. Ask OpenAI (JSON mode) for the initial criteria as the recursive tree.
  4. Validate against the Pydantic schema. On failure, one repair retry; if still
     invalid, store the raw output + validation_error (never crash the pipeline).
  5. Upsert into structured_policies (idempotent on policy_id).

Run: uv run python -m backend.pipeline.structure [--limit 12] [--slugs cg013v11,cg008v12]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.config import settings
from backend.app.db import async_session
from backend.app.models import Policy, StructuredPolicy
from backend.app.schemas import StructuredPolicySchema
from backend.pipeline.extract import extract_text
from backend.pipeline.select_initial import locate_initial

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
log = logging.getLogger("structure")

MAX_TEXT_CHARS = 50_000
DEFAULT_LIMIT = 12

SYSTEM_PROMPT = """You convert health-insurance medical policy text into a strict JSON \
decision tree of the INITIAL medical-necessity criteria.

Output ONLY a JSON object with this exact shape:
{
  "title": string,
  "insurance_name": "Oscar Health",
  "rules": <node>
}
A <node> is:
  { "rule_id": string, "rule_text": string }                          # leaf
  { "rule_id": string, "rule_text": string,
    "operator": "AND" | "OR", "rules": [ <node>, ... ] }              # branch
Rules:
- rule_id is a hierarchical outline number ("1", "1.1", "1.2.1", ...).
- A node WITH child rules MUST have an "operator"; a leaf MUST NOT have "operator" or "rules".
- Use AND when all children are required, OR when any one suffices.
- Extract ONLY the INITIAL / initial-clinical-review / first-time authorization criteria.
- EXCLUDE continuation, subsequent, reauthorization, renewal, maintenance, and \
continued-care criteria, and exclude billing codes, references, and definitions.
- If multiple distinct initial indications/pathways exist, nest them under a single root \
node with operator "OR".
- If no section is explicitly labeled "initial", use the first complete medical-necessity \
criteria tree in the document.
- Preserve the document's wording in rule_text; do not invent criteria.
Return only the JSON object."""


@dataclass
class Result:
    policy_id: int
    slug: str
    ok: bool
    detail: str


def _slug(policy: Policy) -> str:
    return policy.source_page_url.rstrip("/").split("/")[-1]


def _build_user_prompt(title: str, text: str) -> str:
    sel = locate_initial(text)
    hint = (
        f'The initial criteria appear to begin near: "{sel.marker}". '
        if sel.found
        else "No explicit 'initial' heading was found; use the first complete criteria tree. "
    )
    body = text[:MAX_TEXT_CHARS]
    return (
        f"Policy title: {title}\n{hint}\n"
        f"Produce the initial-criteria JSON tree for the following policy document:\n\n"
        f"{body}"
    )


async def _call_llm(client: AsyncOpenAI, messages: list[dict]) -> str:
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    return resp.choices[0].message.content or ""


async def structure_one(
    client: AsyncOpenAI, sem: asyncio.Semaphore, policy: Policy, stored_location: str
) -> tuple[StructuredPolicy, Result]:
    slug = _slug(policy)
    text = extract_text(settings.pdf_dir.parents[1] / stored_location)
    user_prompt = _build_user_prompt(policy.title, text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = ""
    validated: dict | None = None
    validation_error: str | None = None
    attempts = 0
    async with sem:
        for attempt in range(2):  # initial + one repair retry
            attempts = attempt + 1
            try:
                raw = await _call_llm(client, messages)
                parsed = json.loads(raw)
                model = StructuredPolicySchema.model_validate(parsed)
                validated = model.model_dump(exclude_none=True)
                validation_error = None
                break
            except (json.JSONDecodeError, ValidationError) as e:
                validation_error = f"{type(e).__name__}: {e}"
                log.warning("policy %s attempt %d invalid: %s", policy.id, attempts, e)
                # Feed the error back for a repair attempt.
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            "That output was invalid: "
                            f"{validation_error}. Return corrected JSON only, "
                            "matching the required schema exactly."
                        ),
                    },
                ]
            except Exception as e:  # noqa: BLE001 - API/transport error; record, continue
                validation_error = f"{type(e).__name__}: {e}"
                log.warning("policy %s LLM error: %s", policy.id, e)
                break

    sp = StructuredPolicy(
        policy_id=policy.id,
        extracted_text=text[:MAX_TEXT_CHARS],
        structured_json=validated if validated is not None else {"raw": raw},
        llm_metadata={
            "model": settings.openai_model,
            "prompt_system": SYSTEM_PROMPT[:200] + "...",
            "initial_hint": locate_initial(text).marker,
            "attempts": attempts,
        },
        validation_error=validation_error,
    )
    detail = "valid" if validated is not None else f"INVALID: {validation_error}"
    return sp, Result(policy.id, slug, validated is not None, detail)


async def _upsert(rows: list[StructuredPolicy]) -> None:
    """Idempotent on policy_id (UNIQUE in the table)."""
    async with async_session() as session:
        for sp in rows:
            stmt = pg_insert(StructuredPolicy).values(
                policy_id=sp.policy_id,
                extracted_text=sp.extracted_text,
                structured_json=sp.structured_json,
                llm_metadata=sp.llm_metadata,
                validation_error=sp.validation_error,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["policy_id"],
                set_={
                    "extracted_text": stmt.excluded.extracted_text,
                    "structured_json": stmt.excluded.structured_json,
                    "llm_metadata": stmt.excluded.llm_metadata,
                    "validation_error": stmt.excluded.validation_error,
                },
            )
            await session.execute(stmt)
        await session.commit()


async def select_policies(limit: int, slugs: list[str] | None) -> list[tuple[Policy, str]]:
    """Return (policy, stored_location) pairs that have a successful download."""
    from backend.app.models import Download

    async with async_session() as session:
        q = (
            select(Policy, Download.stored_location)
            .join(Download, Download.policy_id == Policy.id)
            .where(Download.stored_location.is_not(None))
            .order_by(Policy.id)
        )
        rows = (await session.execute(q)).all()
    pairs = [(p, loc) for p, loc in rows]
    if slugs:
        wanted = set(slugs)
        pairs = [(p, loc) for p, loc in pairs if _slug(p) in wanted]
    else:
        pairs = pairs[:limit]
    return pairs


async def run(limit: int, slugs: list[str] | None) -> list[Result]:
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY not set (see .env).")
    pairs = await select_policies(limit, slugs)
    log.info("structuring %d policies", len(pairs))
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    sem = asyncio.Semaphore(3)
    results = await asyncio.gather(
        *(structure_one(client, sem, p, loc) for p, loc in pairs)
    )
    await client.close()
    sps = [sp for sp, _ in results]
    await _upsert(sps)
    return [r for _, r in results]


async def _main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--slugs", type=str, default=None, help="comma-separated page slugs")
    args = ap.parse_args()
    slugs = args.slugs.split(",") if args.slugs else None

    results = await run(args.limit, slugs)
    ok = [r for r in results if r.ok]
    print(f"\n{'='*70}\nSTRUCTURED: {len(ok)} valid / {len(results)} attempted\n{'='*70}")
    for r in results:
        flag = "OK " if r.ok else "ERR"
        print(f"  [{flag}] policy {r.policy_id:3} {r.slug:14} {r.detail[:70]}")


if __name__ == "__main__":
    asyncio.run(_main())
