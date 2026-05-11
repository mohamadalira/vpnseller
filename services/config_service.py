from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, ConfigAvailable, ConfigSold


DEFAULT_CATEGORIES = [
    ("1 گیگ", 50000),
    ("2 گیگ", 90000),
    ("3 گیگ", 130000),
    ("4 گیگ", 170000),
    ("5 گیگ", 210000),
]


async def seed_default_categories(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count(Category.id)))
    if count == 0:
        session.add_all([Category(name=name, price=price) for name, price in DEFAULT_CATEGORIES])
        await session.commit()


async def category_with_counts(session: AsyncSession) -> list[tuple[int, str, int, int]]:
    rows = await session.execute(
        select(
            Category.id,
            Category.name,
            Category.price,
            func.count(ConfigAvailable.id).label("available_count"),
        )
        .outerjoin(ConfigAvailable, Category.id == ConfigAvailable.category_id)
        .group_by(Category.id)
        .order_by(Category.id)
    )
    return rows.all()


async def pop_config(session: AsyncSession, category_id: int) -> ConfigAvailable | None:
    row = await session.scalar(
        select(ConfigAvailable)
        .where(ConfigAvailable.category_id == category_id)
        .order_by(ConfigAvailable.id)
        .limit(1)
        .with_for_update()
    )
    if row:
        await session.delete(row)
    return row


async def inventory_stats(session: AsyncSession):
    rows = await session.execute(
        select(
            Category.name,
            func.count(func.distinct(ConfigAvailable.id)),
            func.count(func.distinct(ConfigSold.id)),
        )
        .outerjoin(ConfigAvailable, ConfigAvailable.category_id == Category.id)
        .outerjoin(ConfigSold, ConfigSold.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.id)
    )
    return rows.all()


async def add_configs_bulk(session: AsyncSession, category_id: int, configs: list[str]) -> int:
    clean = [c.strip() for c in configs if c.strip()]
    session.add_all([ConfigAvailable(category_id=category_id, config_text=x) for x in clean])
    await session.commit()
    return len(clean)


async def clear_inventory_by_category(session: AsyncSession, category_id: int) -> int:
    result = await session.execute(delete(ConfigAvailable).where(ConfigAvailable.category_id == category_id))
    await session.commit()
    return result.rowcount or 0


async def clear_inventory_all(session: AsyncSession) -> int:
    result = await session.execute(delete(ConfigAvailable))
    await session.commit()
    return result.rowcount or 0
