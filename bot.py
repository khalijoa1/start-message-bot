import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import get_settings
from db import init_db

from handlers import admin, start, fallback

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    settings = get_settings()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties())
    dp = Dispatcher()

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(fallback.router)  # must stay last - catch-all diagnostic

    await init_db()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
