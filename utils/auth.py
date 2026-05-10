from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Admin


async def is_admin(session: AsyncSession, user_id: int, base_admin_ids: list[int]) -> bool:
    if user_id in base_admin_ids:
        return True
    row = await session.scalar(select(Admin).where(Admin.user_id == user_id))
    return row is not None


async def admin_guard(message: Message, session: AsyncSession, base_admin_ids: list[int]) -> bool:
    ok = await is_admin(session, message.from_user.id, base_admin_ids)
    if not ok:
        await message.answer("⛔️ شما دسترسی به پنل مدیریت ندارید.")
        return False
    return True
