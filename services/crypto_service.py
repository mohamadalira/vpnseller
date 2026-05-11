import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from models import CryptoInvoice, Order, Transaction
from services.payment_service import fulfill_order


async def create_crypto_invoice(
    session: AsyncSession,
    settings: Settings,
    order: Order,
    user_tg_id: int,
    amount_irt: int,
) -> tuple[bool, str, CryptoInvoice | None]:
    if not settings.nowpayments_api_key:
        return False, "کلید NOWPayments تنظیم نشده است.", None

    payload = {
        "price_amount": amount_irt,
        "price_currency": "irt",
        "pay_currency": settings.crypto_pay_currency,
        "order_id": order.order_uuid,
        "order_description": f"VPN order {order.order_uuid}",
    }
    headers = {"x-api-key": settings.nowpayments_api_key, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as client:
        async with client.post(f"{settings.nowpayments_base_url}/payment", json=payload, headers=headers) as resp:
            if resp.status >= 300:
                return False, "ساخت پرداخت کریپتو ناموفق بود.", None
            data = await resp.json()

    invoice = CryptoInvoice(
        order_id=order.id,
        user_id=user_tg_id,
        pay_currency=(data.get("pay_currency") or settings.crypto_pay_currency).upper(),
        pay_amount=float(data.get("pay_amount") or 0),
        pay_address=data.get("pay_address"),
        external_invoice_id=str(data.get("payment_id") or ""),
        status=data.get("payment_status") or "waiting",
    )
    session.add(invoice)
    session.add(
        Transaction(
            user_id=user_tg_id,
            order_id=order.id,
            amount=amount_irt,
            method="crypto",
            status="pending",
            txid=invoice.external_invoice_id,
        )
    )
    order.status = "crypto_waiting"
    await session.commit()
    await session.refresh(invoice)
    return True, "فاکتور کریپتو ایجاد شد.", invoice


async def check_crypto_payment(
    session: AsyncSession,
    settings: Settings,
    order_id: int,
) -> tuple[bool, str]:
    invoice = await session.scalar(select(CryptoInvoice).where(CryptoInvoice.order_id == order_id))
    if not invoice or not invoice.external_invoice_id:
        return False, "فاکتور کریپتو یافت نشد."
    if not settings.nowpayments_api_key:
        return False, "کلید NOWPayments تنظیم نشده است."

    headers = {"x-api-key": settings.nowpayments_api_key}
    async with aiohttp.ClientSession() as client:
        async with client.get(
            f"{settings.nowpayments_base_url}/payment/{invoice.external_invoice_id}", headers=headers
        ) as resp:
            if resp.status >= 300:
                return False, "خطا در استعلام وضعیت پرداخت."
            data = await resp.json()

    status = (data.get("payment_status") or "").lower()
    invoice.status = status or invoice.status

    tx = await session.scalar(
        select(Transaction).where(Transaction.order_id == order_id, Transaction.method == "crypto")
    )
    if status in {"finished", "confirmed", "sending"}:
        if tx:
            tx.status = "approved"
        ok, msg = await fulfill_order(session, order_id, payment_marker="CRYPTO_AUTO")
        return ok, msg

    if status in {"failed", "expired", "refunded"}:
        if tx:
            tx.status = "failed"
        order = await session.get(Order, order_id)
        if order:
            order.status = "rejected"
        await session.commit()
        return False, "پرداخت کریپتو ناموفق یا منقضی شده است."

    await session.commit()
    return False, "پرداخت هنوز تایید نشده است."
