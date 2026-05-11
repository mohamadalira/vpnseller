from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import BotMessage


DEFAULT_MESSAGES = {
    "start_text": "به ربات فروش کانفیگ خوش آمدید 🌹",
    "membership_required_text": "برای استفاده از ربات باید ابتدا در کانال‌های زیر عضو شوید:",
    "membership_not_ok_text": "هنوز در همه کانال‌ها عضو نشده‌اید.",
    "membership_ok_text": "عضویت شما تایید شد ✅",
    "buy_menu_prompt_text": "پلن موردنظر را انتخاب کنید:",
    "no_plan_text": "در حال حاضر هیچ پلنی ثبت نشده است.",
    "payment_methods_prompt_text": "روش پرداخت را انتخاب کنید:",
    "no_active_payment_method_text": "هیچ روش پرداخت فعالی وجود ندارد.",
    "plan_not_found_text": "پلن یافت نشد.",
    "order_not_found_text": "سفارشی یافت نشد. دوباره تلاش کنید.",
    "wallet_insufficient_text": "موجودی کیف پول کافی نیست.",
    "receipt_received_text": "رسید شما دریافت شد ✅\nپس از بررسی ادمین نتیجه اطلاع‌رسانی می‌شود.",
    "wallet_balance_text": "👛 موجودی کیف پول شما: {balance} تومان",
    "wallet_buy_hint_text": "برای پرداخت با کیف پول، ابتدا از منوی خرید کانفیگ، پلن را انتخاب کنید.",
    "invite_text": "🎁 سیستم دعوت دوستان\n\nلینک دعوت شما:\n{link}\n\nتعداد زیرمجموعه ها: {count}\nپاداش دریافتی: {reward} تومان",
    "my_purchases_empty_text": "هنوز خریدی ثبت نشده است.",
    "order_status_text": "آخرین سفارش شما: {order_uuid}\nوضعیت: {status}",
    "user_not_found_text": "کاربری یافت نشد.",
    "buy_help_text": (
        "1) از منوی خرید، پلن را انتخاب کنید.\n"
        "2) مبلغ را کارت به کارت کنید.\n"
        "3) عکس رسید را ارسال کنید.\n"
        "4) پس از تایید ادمین، کانفیگ ارسال می شود."
    ),
    "post_purchase_text": "✅ پرداخت شما تایید شد.\nکانفیگ شما:\n\n{config}",
    "support_text": "برای پشتیبانی پیام دهید: {support_username}",
    "card_payment_instruction_text": (
        "برای خرید این پلن لطفاً مبلغ زیر را کارت به کارت کنید.\n\n"
        "💳 شماره کارت: {card_number}\n"
        "👤 نام صاحب کارت: {card_holder}\n"
        "💰 مبلغ: {price} تومان\n\n"
        "پس از پرداخت، عکس رسید را ارسال کنید.\n"
        "شماره سفارش: {order_uuid}"
    ),
    "crypto_invoice_text": (
        "🪙 فاکتور کریپتو ایجاد شد:\n\n"
        "ارز: {currency}\n"
        "مبلغ: {amount}\n"
        "آدرس: {address}\n"
        "شماره سفارش: {order_uuid}\n\n"
        "پس از پرداخت، روی دکمه بررسی بزنید."
    ),
}


async def get_message(session: AsyncSession, key: str, fallback: str | None = None) -> str:
    row = await session.scalar(select(BotMessage).where(BotMessage.key == key))
    if row and row.value.strip():
        return row.value
    if fallback is not None:
        return fallback
    return DEFAULT_MESSAGES.get(key, "")


async def set_message(session: AsyncSession, key: str, value: str) -> BotMessage:
    row = await session.scalar(select(BotMessage).where(BotMessage.key == key))
    if not row:
        row = BotMessage(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    await session.commit()
    await session.refresh(row)
    return row


async def list_messages(session: AsyncSession) -> list[tuple[str, str]]:
    rows = (await session.execute(select(BotMessage).order_by(BotMessage.key))).scalars().all()
    existing = {row.key: row.value for row in rows}
    result: list[tuple[str, str]] = []
    for key, default_value in DEFAULT_MESSAGES.items():
        result.append((key, existing.get(key, default_value)))
    for key, value in existing.items():
        if key not in DEFAULT_MESSAGES:
            result.append((key, value))
    return result
