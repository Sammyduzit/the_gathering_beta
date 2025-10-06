"""ARQ Worker Settings and Configuration."""

import structlog

from app.core.arq_db_manager import ARQDatabaseManager
from app.core.config import settings
from app.workers.tasks import generate_ai_conversation_response, generate_ai_room_response

logger = structlog.get_logger(__name__)


async def startup(ctx: dict) -> None:
    """Initialize resources on worker startup."""
    db_manager = ARQDatabaseManager()
    await db_manager.connect()
    ctx["db_manager"] = db_manager
    logger.info("arq_worker_started", redis_url=settings.redis_url)


async def shutdown(ctx: dict) -> None:
    """Clean up resources on worker shutdown."""
    db_manager: ARQDatabaseManager = ctx.get("db_manager")
    if db_manager:
        await db_manager.disconnect()
    logger.info("arq_worker_stopped")


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [
        generate_ai_room_response,
        generate_ai_conversation_response,
    ]

    redis_settings = settings.redis_url

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 300
    keep_result = 3600

    max_tries = 3
    retry_jobs = True
