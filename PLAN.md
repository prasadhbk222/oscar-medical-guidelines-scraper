# PLAN — Oscar Medical Guidelines Scraper + Tree Explorer

Phased build. Each phase ends at a **verification gate**: I print what to check, you confirm, then we commit.

## Stack (confirmed)
- Package manager: `uv`
- Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg
- DB: Postgres 16 (Docker) + pgweb GUI (Docker)
- Scraping: httpx + BeautifulSoup (lxml)
- PDF text: pypdf
- LLM: **OpenAI** (`OPENAI_MODEL`, default `gpt-4o-mini`)
- Frontend: React + Vite

## Phases
- [ ] **Phase 0 — Scaffolding.** uv project, git, .gitignore, .env(.example), docker-compose (Postgres + pgweb), doc skeletons, DB models/schema, init_db. _Gate: `docker compose up` + pgweb reachable + `uv run` works + tables created._
- [ ] **Phase 1 — PDF discovery (console only).** Scrape source page, list every guideline PDF (title + pdf_url + source_page_url). _Gate: eyeball console list for completeness._
- [ ] **Phase 2 — Persist discovery.** Idempotent upsert on `pdf_url`. _Gate: rows in pgweb match console; rerun adds nothing._
- [ ] **Phase 3 — PDF download.** Retry + throttle; persist outcome to `downloads`. _Gate: download dir + table, failures recorded._
- [ ] **Phase 4 — Structuring pipeline (≥10).** Extract text → OpenAI → criteria tree → validate → store. Initial-only selection. Tests. _Gate: ≥10 structured_json rows match oscar.json shape._
- [ ] **Phase 5 — Frontend.** Policy list + structured-tree detail view (expand/collapse, AND/OR vs leaf). _Gate: browse UI._
- [ ] **Final.** README update, fresh-clone/unzip end-to-end check, WALKTHROUGH architecture + data-flow diagrams.

## Data model
- `policies`: title, pdf_url (UNIQUE), source_page_url, discovered_at
- `downloads`: policy_id, stored_location, http_status, error, downloaded_at
- `structured_policies`: policy_id, extracted_text, structured_json, llm_metadata, validation_error, structured_at
