import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import get_settings
from app.handlers import register_routers
from app.services.sessions import expire_stale_private_duels


async def start_healthcheck_server(host: str, port: int) -> asyncio.AbstractServer:
    async def handle_client(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            await reader.read(1024)
            body = b"ok"
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host, port)
    logging.getLogger(__name__).info(
        "Healthcheck server listening on %s:%s",
        host,
        port,
    )
    return server


DUEL_CLEANUP_INTERVAL = 24 * 60 * 60  # seconds


async def cleanup_loop() -> None:
    log = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(DUEL_CLEANUP_INTERVAL)
        try:
            await expire_stale_private_duels()
            log.info("Stale duel invites cleaned up")
        except Exception:
            log.exception("Error during stale duel cleanup")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = get_settings()
    healthcheck_server = await start_healthcheck_server(
        settings.healthcheck_host,
        settings.healthcheck_port,
    )

    try:
        await expire_stale_private_duels()

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
        healthcheck_server.close()
        await healthcheck_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
