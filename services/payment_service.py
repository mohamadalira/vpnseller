import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConfigSold, Order, Payment, User
from services.config_service import pop_config


async def create_order(session: AsyncSession, user_db_id: int, category_id: int) -> Order:
    order = Order(order_uuid=uuid.uuid4().hex[:10].upper(), user_id_fk=user_db_id, category_id=category_id)
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def register_receipt(session: AsyncSession, order_id: int, file_id: str) -> Payment:
    payment = Payment(order_id=order_id, receipt_file_id=file_id, status="waiting_approval")
    order = await session.get(Order, order_id)
    order.status = "waiting_approval"
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def approve_payment(session: AsyncSession, payment_id: int) -> tuple[bool, str]:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.status != "waiting_approval":
        return False, "پرداخت معتبر نیست یا قبلا بررسی شده است."

    order = await session.get(Order, payment.order_id)
    config = await pop_config(session, order.category_id)
    if not config:
        return False, "موجودی پلن انتخابی تمام شده است."

    user = await session.scalar(select(User).where(User.id == order.user_id_fk))
    sold = ConfigSold(
        category_id=order.category_id,
        user_id=user.user_id,
        username=user.username,
        order_id=order.id,
        payment_id=payment.id,
        config_text=config.config_text,
        sold_at=datetime.utcnow(),
    )
    session.add(sold)
    payment.status = "approved"
    order.status = "approved"
    user.total_purchases += 1
    await session.commit()
    return True, config.config_text


async def reject_payment(session: AsyncSession, payment_id: int) -> tuple[bool, str]:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.status != "waiting_approval":
        return False, "پرداخت معتبر نیست یا قبلا بررسی شده است."
    order = await session.get(Order, payment.order_id)
    payment.status = "rejected"
    order.status = "rejected"
    await session.commit()
    return True, "پرداخت رد شد."
