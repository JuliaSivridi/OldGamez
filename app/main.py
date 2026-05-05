import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.handlers import register_routers


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
        await init_db()

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()
        register_routers(dp)

        await dp.start_polling(bot)
    finally:
        healthcheck_server.close()
        await healthcheck_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
