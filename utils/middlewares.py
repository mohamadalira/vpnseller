from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config import Settings
from bot import database


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if database.SessionLocal is None:
            raise RuntimeError("اتصال دیتابیس هنوز آماده نشده است.")
        async with database.SessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


class SettingsMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def __call__(self, handler, event: TelegramObject, data: dict):
        data["settings"] = self.settings
        return await handler(event, data)
