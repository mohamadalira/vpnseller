from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Referral, Transaction, User
from services.wallet_service import change_wallet_balance


async def register_referral_if_new(
    session: AsyncSession,
    new_user: User,
    referrer_telegram_id: int | None,
    reward_amount: int,
) -> None:
    if not referrer_telegram_id or referrer_telegram_id == new_user.user_id:
        return

    exists = await session.scalar(select(Referral).where(Referral.user_id == new_user.user_id))
    if exists:
        return

    referrer = await session.scalar(select(User).where(User.user_id == referrer_telegram_id))
    if not referrer:
        return

    session.add(Referral(user_id=new_user.user_id, referrer_id=referrer_telegram_id))
    await session.commit()
    await change_wallet_balance(
        session,
        referrer_telegram_id,
        reward_amount,
        reason_method="referral",
        status="approved",
    )


async def referral_stats(session: AsyncSession, user_id: int) -> tuple[int, int]:
    count = await session.scalar(select(func.count(Referral.id)).where(Referral.referrer_id == user_id))
    reward = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.method == "referral",
            Transaction.status == "approved",
        )
    )
    return count or 0, reward or 0
