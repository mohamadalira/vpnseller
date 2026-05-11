import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot import database
from bot.database import create_tables, init_db
from handlers.admin.panel import router as admin_router
from handlers.user.start import router as user_router
from services.admin_service import get_or_create_settings
from services.config_service import seed_default_categories
from services.nowpayments_webhook import start_nowpayments_webhook_server
from services.payment_method_service import ensure_payment_methods
from utils.middlewares import DbSessionMiddleware, SettingsMiddleware
from utils.rate_limit import RateLimitMiddleware


async def on_startup():
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal مقداردهی نشده است.")
    async with database.SessionLocal() as session:
        await seed_default_categories(session)
        await get_or_create_settings(session)
        await ensure_payment_methods(session)


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    init_db(settings.database_url)
    await create_tables()
    await on_startup()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(RateLimitMiddleware())
    dp.update.middleware(SettingsMiddleware(settings))
    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(user_router)
    dp.include_router(admin_router)

    webhook_runner = None
    if settings.nowpayments_webhook_port > 0:
        webhook_runner = await start_nowpayments_webhook_server(settings)

    try:
        await dp.start_polling(bot)
    finally:
        if webhook_runner:
            await webhook_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
