# SETUP

## Prerequisites
- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node 18+ (frontend, Phase 5)

## 1. Configure secrets
```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

## 2. Start Postgres + pgweb
```bash
docker compose up -d
```
- Postgres: `localhost:5435` (user/pass/db = `oscar`/`oscar`/`oscar`) — host port 5435 to avoid clashing with a native Postgres on 5432
- pgweb GUI: http://localhost:8081

## 3. Install Python deps
```bash
uv sync
```

## 4. Create DB tables
```bash
uv run python -m backend.app.init_db
```

## Pipeline (added per phase)
- Discovery: `uv run python -m backend.pipeline.discover`   _(Phase 1/2)_
- Download:  `uv run python -m backend.pipeline.download`   _(Phase 3)_
- Structure: `uv run python -m backend.pipeline.structure`  _(Phase 4)_

## Backend API (Phase 5)
```bash
uv run uvicorn backend.app.main:app --reload
```

## Frontend (Phase 5)
```bash
cd frontend && npm install && npm run dev
```
