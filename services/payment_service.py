import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, ConfigSold, Order, Payment, Transaction, User
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
    user_tg_id = await session.scalar(select(User.user_id).join(Order, User.id == Order.user_id_fk).where(Order.id == order_id))
    amount = await session.scalar(
        select(Category.price).join(Order, Category.id == Order.category_id).where(Order.id == order_id)
    )
    session.add(Transaction(user_id=user_tg_id, order_id=order_id, amount=amount or 0, method="card", status="pending"))
    await session.commit()
    await session.refresh(payment)
    return payment


async def approve_payment(session: AsyncSession, payment_id: int) -> tuple[bool, str]:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.status != "waiting_approval":
        return False, "پرداخت معتبر نیست یا قبلا بررسی شده است."

    order = await session.get(Order, payment.order_id)
    ok, msg = await fulfill_order(session, order.id, payment.id)
    if ok:
        payment.status = "approved"
        tx = await session.scalar(select(Transaction).where(Transaction.order_id == order.id, Transaction.method == "card"))
        if tx:
            tx.status = "approved"
        await session.commit()
        return True, msg
    return False, msg


async def reject_payment(session: AsyncSession, payment_id: int) -> tuple[bool, str]:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.status != "waiting_approval":
        return False, "پرداخت معتبر نیست یا قبلا بررسی شده است."
    order = await session.get(Order, payment.order_id)
    payment.status = "rejected"
    order.status = "rejected"
    tx = await session.scalar(select(Transaction).where(Transaction.order_id == order.id, Transaction.method == "card"))
    if tx:
        tx.status = "failed"
    await session.commit()
    return True, "پرداخت رد شد."


async def fulfill_order(
    session: AsyncSession, order_id: int, payment_id: int | None = None, payment_marker: str = "AUTO"
) -> tuple[bool, str]:
    order = await session.get(Order, order_id)
    if not order:
        return False, "سفارش یافت نشد."
    if order.status == "approved":
        sold = await session.scalar(select(ConfigSold).where(ConfigSold.order_id == order.id))
        return True, sold.config_text if sold else "سفارش قبلا تحویل شده است."

    config = await pop_config(session, order.category_id)
    if not config:
        return False, "موجودی پلن انتخابی تمام شده است."

    user = await session.scalar(select(User).where(User.id == order.user_id_fk))
    if payment_id is None:
        auto_payment = Payment(order_id=order.id, receipt_file_id=payment_marker, status="approved")
        session.add(auto_payment)
        await session.flush()
        payment_id = auto_payment.id

    sold = ConfigSold(
        category_id=order.category_id,
        user_id=user.user_id,
        username=user.username,
        order_id=order.id,
        payment_id=payment_id,
        config_text=config.config_text,
        sold_at=datetime.utcnow(),
    )
    session.add(sold)
    order.status = "approved"
    user.total_purchases += 1
    await session.commit()
    return True, config.config_text
