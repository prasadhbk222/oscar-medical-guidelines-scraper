# Oscar Guidelines Scraper — common commands.
# Run `make help` for the list. Requires: uv, Docker, Node 18+ (frontend).

API_PORT ?= 8008

.PHONY: help up down setup db discover download structure seed api web-install web test clean

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Start Postgres + pgweb (docker)
	docker compose up -d

down:  ## Stop containers
	docker compose down

setup:  ## Install Python deps + create tables (run `up` first)
	uv sync
	uv run python -m backend.app.init_db

db:  ## Create/refresh DB tables
	uv run python -m backend.app.init_db

discover:  ## Discover + persist all guideline PDF links
	uv run python -m backend.pipeline.discover

download:  ## Download all discovered PDFs
	uv run python -m backend.pipeline.download

structure:  ## Structure policies (LLM); override N via `make structure LIMIT=20`
	uv run python -m backend.pipeline.structure $(if $(LIMIT),--limit $(LIMIT),)

seed: discover download structure  ## Run the full pipeline end to end

api:  ## Run the FastAPI backend (port 8008)
	uv run uvicorn backend.app.main:app --port $(API_PORT) --reload

web-install:  ## Install frontend deps
	cd frontend && npm install

web:  ## Run the Vite dev server (needs Node 18+; proxies /api -> :8008)
	cd frontend && npm run dev

test:  ## Run the test suite
	uv run pytest -q

clean:  ## Stop containers + drop volumes + delete downloaded PDFs
	docker compose down -v
	rm -rf data/pdfs/* frontend/dist
