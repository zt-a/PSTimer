"""Background retention worker.

Periodically purges completed sessions (and their transactions) older than
``settings.HISTORY_RETENTION_DAYS`` so that raw session history is never kept
for more than one month by default.

Run it as a standalone process (recommended, see docker-compose `worker`
service)::

    python -m app.worker            # loop forever
    python -m app.worker --once     # single pass (useful for cron / tests)
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.analytics import cleanup_history

logger = logging.getLogger("pstimer.worker")


async def run_once() -> None:
    async with AsyncSessionLocal() as db:
        result = await cleanup_history(db)
    logger.info(
        "cleanup: removed %s session(s) and %s transaction(s) older than %s "
        "(retention=%s days)",
        result.deleted_sessions,
        result.deleted_transactions,
        result.older_than.isoformat(),
        result.retention_days,
    )


async def run_forever() -> None:
    interval_seconds = max(settings.CLEANUP_INTERVAL_HOURS, 1) * 3600
    logger.info(
        "retention worker started: every %s h, keeping %s days of history",
        settings.CLEANUP_INTERVAL_HOURS,
        settings.HISTORY_RETENTION_DAYS,
    )
    while True:
        try:
            await run_once()
        except Exception:  # pragma: no cover - keep the loop alive
            logger.exception("cleanup run failed; retrying next cycle")
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="PSTimer history retention worker")
    parser.add_argument(
        "--once", action="store_true", help="run a single cleanup pass and exit"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if args.once:
            asyncio.run(run_once())
        else:
            asyncio.run(run_forever())
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("worker stopped")


if __name__ == "__main__":
    main()
