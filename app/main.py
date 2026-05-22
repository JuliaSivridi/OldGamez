import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import get_settings
from app.handlers import register_routers
from app.services.sessions import delete_stale_sessions, expire_stale_group_matches, expire_stale_private_duels
from app.web import create_app


_DAILY  = 24 * 60 * 60       # seconds
_WEEKLY = 7 * 24 * 60 * 60   # seconds


async def cleanup_loop() -> None:
    log = logging.getLogger(__name__)
    days_since_deletion = 0
    while True:
        await asyncio.sleep(_DAILY)
        days_since_deletion += 1

        # Daily: mark stale pending sessions as expired
        try:
            await expire_stale_private_duels()
            await expire_stale_group_matches()
            log.info("Daily expiry: stale pending sessions marked expired")
        except Exception:
            log.exception("Error during session expiry")

        # Weekly: hard-delete expired + abandoned records
        if days_since_deletion >= 7:
            days_since_deletion = 0
            try:
                n = await delete_stale_sessions()
                log.info("Weekly cleanup: deleted %d expired/abandoned sessions", n)
            except Exception:
                log.exception("Error during session deletion")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log = logging.getLogger(__name__)
    settings = get_settings()

    runner = web.AppRunner(create_app())
    await runner.setup()
    site = web.TCPSite(runner, settings.healthcheck_host, settings.healthcheck_port)
    await site.start()
    log.info("Web server listening on %s:%s", settings.healthcheck_host, settings.healthcheck_port)

    try:
        await expire_stale_private_duels()
        await expire_stale_group_matches()

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        dp = Dispatcher()
        register_routers(dp)

        cleanup_task = asyncio.create_task(cleanup_loop())
        try:
            await dp.start_polling(bot)
        finally:
            cleanup_task.cancel()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
