from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PaymentMethod

DEFAULT_METHODS = ["card", "crypto", "wallet"]


async def ensure_payment_methods(session: AsyncSession) -> None:
    rows = (await session.execute(select(PaymentMethod.name))).scalars().all()
    exists = set(rows)
    changed = False
    for name in DEFAULT_METHODS:
        if name not in exists:
            session.add(PaymentMethod(name=name, is_active=True))
            changed = True
    if changed:
        await session.commit()


async def list_payment_methods(session: AsyncSession) -> list[PaymentMethod]:
    return (await session.execute(select(PaymentMethod).order_by(PaymentMethod.id))).scalars().all()


async def get_active_method_names(session: AsyncSession) -> set[str]:
    rows = (
        await session.execute(select(PaymentMethod.name).where(PaymentMethod.is_active.is_(True)))
    ).scalars().all()
    return set(rows)


async def toggle_payment_method(session: AsyncSession, name: str) -> tuple[bool, str]:
    row = await session.scalar(select(PaymentMethod).where(PaymentMethod.name == name))
    if not row:
        return False, "روش پرداخت پیدا نشد."
    row.is_active = not row.is_active
    await session.commit()
    state = "فعال" if row.is_active else "غیرفعال"
    return True, f"روش پرداخت {name} {state} شد."
