"""Create all tables. Run: uv run python -m backend.app.init_db"""

import asyncio

from backend.app.db import init_db


async def main() -> None:
    await init_db()
    print("Tables created (policies, downloads, structured_policies).")


if __name__ == "__main__":
    asyncio.run(main())
