from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Transaction, Wallet


async def get_or_create_wallet(session: AsyncSession, user_id: int) -> Wallet:
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user_id))
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id, balance=0)
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return wallet


async def change_wallet_balance(
    session: AsyncSession,
    user_id: int,
    amount_delta: int,
    reason_method: str,
    status: str = "approved",
    order_id: int | None = None,
    txid: str | None = None,
) -> tuple[bool, str, int]:
    wallet = await get_or_create_wallet(session, user_id)
    new_balance = wallet.balance + amount_delta
    if new_balance < 0:
        return False, "موجودی کیف پول کافی نیست.", wallet.balance

    wallet.balance = new_balance
    session.add(
        Transaction(
            user_id=user_id,
            order_id=order_id,
            amount=abs(amount_delta),
            method=reason_method,
            status=status,
            txid=txid,
        )
    )
    await session.commit()
    return True, "عملیات کیف پول انجام شد.", wallet.balance
