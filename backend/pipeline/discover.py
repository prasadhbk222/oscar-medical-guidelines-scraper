"""Phase 1/2: discover every guideline PDF link from the Oscar source page.

Strategy (completeness):
  1. The listing page is a Next.js app; the full guideline list is embedded in the
     `__NEXT_DATA__` JSON (not paginated, not lazy-loaded). We parse that JSON and
     walk every module/nested list, so we never depend on rendered DOM or scrolling.
  2. Each list item's link points to a policy *page* (e.g. /medical/cg013v11), not a
     file. We fetch each policy page and read the Contentful asset URL ending in .pdf
     from its `__NEXT_DATA__`. That asset URL is the canonical, stable `pdf_url`.

Run (console only): uv run python -m backend.pipeline.discover
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from bs4 import BeautifulSoup

from backend.app.config import settings
from backend.pipeline.scraper import PoliteClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("discover")

BASE = "https://www.hioscar.com"
# Sections to skip: drafts not yet in effect, and third-party adopted guidelines.
EXCLUDED_SECTIONS = ("upcoming", "adopted")


@dataclass
class Discovered:
    title: str
    source_page_url: str  # the policy page where the PDF was found
    section: str
    pdf_url: str | None = None
    error: str | None = None


def _next_data(html: str) -> dict:
    tag = BeautifulSoup(html, "lxml").find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        raise ValueError("no __NEXT_DATA__ on page")
    return json.loads(tag.string)


def _abs(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE + url
    return url


def parse_listing(html: str) -> list[Discovered]:
    """Walk every module/nested list; return internal PDF-typed link items."""
    data = _next_data(html)
    modules = data["props"]["pageProps"]["modules"]
    items: list[Discovered] = []
    seen_hrefs: set[str] = set()

    def walk(node, section: str):
        if isinstance(node, dict):
            f = node.get("fields", node)
            # A section header refreshes the current section label.
            hdr = f.get("header")
            if isinstance(hdr, str):
                section = hdr
            link = f.get("link")
            if isinstance(link, dict) and link.get("href"):
                href = link["href"]
                text = (link.get("text") or "").strip().upper()
                title = (f.get("item") or f.get("title") or "").strip()
                excluded = any(x in section.lower() for x in EXCLUDED_SECTIONS)
                # PDF-typed, internal links only (external "LINK" items are skipped);
                # skip Upcoming/Adopted sections.
                if (
                    text == "PDF"
                    and href.startswith("/")
                    and not excluded
                    and href not in seen_hrefs
                ):
                    seen_hrefs.add(href)
                    items.append(
                        Discovered(
                            title=title or href,
                            source_page_url=_abs(href),
                            section=section,
                        )
                    )
            for v in f.values():
                walk(v, section)
        elif isinstance(node, list):
            for v in node:
                walk(v, section)

    walk(modules, section="")
    return items


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")


def extract_pdf_url(html: str) -> str:
    """Find the policy document URL inside a policy page's __NEXT_DATA__.

    The document is a Contentful asset (a dict with `url` + `fileName`). Most have a
    `.pdf` URL; some are extensionless but still serve application/pdf. We prefer a
    `.pdf` URL, else fall back to the lone non-image file asset (the document).
    """
    data = _next_data(html)
    pdf_urls: list[str] = []
    other_assets: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            url = node.get("url")
            if isinstance(url, str) and "fileName" in node:  # Contentful asset shape
                low = url.lower()
                if low.endswith(".pdf"):
                    pdf_urls.append(_abs(url))
                elif not low.endswith(IMAGE_EXTS):
                    other_assets.append(_abs(url))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    if pdf_urls:
        return list(dict.fromkeys(pdf_urls))[0]
    if other_assets:
        return list(dict.fromkeys(other_assets))[0]
    raise ValueError("no document asset found on policy page")


async def discover() -> list[Discovered]:
    async with PoliteClient() as client:
        listing = await client.get(settings.source_page_url)
        items = parse_listing(listing.text)
        log.info("listing: %d PDF-typed items", len(items))

        async def resolve(item: Discovered) -> Discovered:
            try:
                resp = await client.get(item.source_page_url)
                item.pdf_url = extract_pdf_url(resp.text)
            except Exception as e:  # noqa: BLE001 - record, never crash discovery
                item.error = f"{type(e).__name__}: {e}"
                log.warning("resolve failed %s: %s", item.source_page_url, item.error)
            return item

        return await asyncio.gather(*(resolve(it) for it in items))


async def persist(items: list[Discovered]) -> int:
    """Idempotent upsert on pdf_url. Returns total policy rows after the write."""
    from sqlalchemy import func, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from backend.app.db import async_session
    from backend.app.models import Policy

    rows = [
        {
            "title": i.title,
            "pdf_url": i.pdf_url,
            "source_page_url": i.source_page_url,
        }
        for i in items
        if i.pdf_url
    ]
    if not rows:
        return 0

    async with async_session() as session:
        stmt = pg_insert(Policy).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["pdf_url"],
            set_={
                "title": stmt.excluded.title,
                "source_page_url": stmt.excluded.source_page_url,
            },
        )
        await session.execute(stmt)
        await session.commit()
        total = await session.scalar(select(func.count()).select_from(Policy))
    return total or 0


async def _main(do_persist: bool = True) -> None:
    items = await discover()
    ok = [i for i in items if i.pdf_url]
    fail = [i for i in items if not i.pdf_url]
    print(f"\n{'='*80}\nDISCOVERED {len(items)} items  |  resolved {len(ok)}  |  failed {len(fail)}\n{'='*80}")
    for i in sorted(ok, key=lambda x: x.source_page_url):
        print(f"[{i.section[:18]:18}] {i.title[:60]:60} {i.source_page_url}")
        print(f"{'':21}-> {i.pdf_url}")
    if fail:
        print(f"\n--- {len(fail)} FAILED TO RESOLVE ---")
        for i in fail:
            print(f"  {i.source_page_url}  ({i.error})")

    if do_persist:
        total = await persist(items)
        print(f"\nPersisted (upsert on pdf_url). policies table now has {total} rows.")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Discover Oscar guideline PDFs.")
    p.add_argument(
        "--no-persist",
        action="store_true",
        help="console only; do not write to the DB",
    )
    args = p.parse_args()
    asyncio.run(_main(do_persist=not args.no_persist))
