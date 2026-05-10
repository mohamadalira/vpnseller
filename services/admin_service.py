from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Admin, AppSetting, Category, ConfigAvailable, RequiredChannel


async def get_or_create_settings(session: AsyncSession) -> AppSetting:
    row = await session.scalar(select(AppSetting).order_by(AppSetting.id).limit(1))
    if row:
        return row
    row = AppSetting()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def create_category(session: AsyncSession, name: str, price: int) -> tuple[bool, str]:
    exists = await session.scalar(select(Category).where(Category.name == name))
    if exists:
        return False, "پلنی با این نام قبلا ثبت شده است."
    session.add(Category(name=name, price=price))
    await session.commit()
    return True, "پلن جدید با موفقیت اضافه شد ✅"


async def update_category_name(session: AsyncSession, category_id: int, new_name: str) -> tuple[bool, str]:
    cat = await session.get(Category, category_id)
    if not cat:
        return False, "پلن موردنظر یافت نشد."
    exists = await session.scalar(select(Category).where(Category.name == new_name, Category.id != category_id))
    if exists:
        return False, "پلنی با این نام از قبل وجود دارد."
    cat.name = new_name
    await session.commit()
    return True, "نام پلن با موفقیت تغییر کرد ✅"


async def update_category_price(session: AsyncSession, category_id: int, new_price: int) -> tuple[bool, str]:
    cat = await session.get(Category, category_id)
    if not cat:
        return False, "پلن موردنظر یافت نشد."
    cat.price = new_price
    await session.commit()
    return True, "قیمت پلن با موفقیت تغییر کرد ✅"


async def delete_category_safe(session: AsyncSession, category_id: int) -> tuple[bool, str]:
    cat = await session.get(Category, category_id)
    if not cat:
        return False, "پلن موردنظر یافت نشد."
    cnt = await session.scalar(select(func.count(ConfigAvailable.id)).where(ConfigAvailable.category_id == category_id))
    if cnt and cnt > 0:
        return False, "حذف ممکن نیست: برای این پلن کانفیگ موجود است."
    await session.delete(cat)
    await session.commit()
    return True, "پلن با موفقیت حذف شد ✅"


async def create_channel(session: AsyncSession, channel_id: int, username: str) -> tuple[bool, str]:
    username = username.strip().lstrip("@")
    exists = await session.scalar(
        select(RequiredChannel).where(
            (RequiredChannel.channel_id == channel_id) | (RequiredChannel.channel_username == username)
        )
    )
    if exists:
        return False, "این کانال قبلا ثبت شده است."
    session.add(RequiredChannel(channel_id=channel_id, channel_username=username))
    await session.commit()
    return True, "کانال اجباری اضافه شد ✅"


async def delete_channel(session: AsyncSession, channel_id: int) -> tuple[bool, str]:
    row = await session.scalar(select(RequiredChannel).where(RequiredChannel.channel_id == channel_id))
    if not row:
        return False, "کانال موردنظر یافت نشد."
    await session.delete(row)
    await session.commit()
    return True, "کانال حذف شد ✅"


async def add_admin(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    row = await session.scalar(select(Admin).where(Admin.user_id == user_id))
    if row:
        return False, "این کاربر قبلا ادمین است."
    session.add(Admin(user_id=user_id))
    await session.commit()
    return True, "ادمین جدید اضافه شد ✅"


async def remove_admin(session: AsyncSession, user_id: int, base_admin_ids: list[int]) -> tuple[bool, str]:
    if user_id in base_admin_ids:
        return False, "حذف این ادمین مجاز نیست (ادمین اصلی محیط)."
    row = await session.scalar(select(Admin).where(Admin.user_id == user_id))
    if not row:
        return False, "ادمین موردنظر یافت نشد."
    await session.delete(row)
    await session.commit()
    return True, "ادمین حذف شد ✅"
