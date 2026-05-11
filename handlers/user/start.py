from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from keyboards.admin_kb import approve_payment_kb
from keyboards.user_kb import (
    categories_keyboard,
    channels_keyboard,
    crypto_check_keyboard,
    payment_methods_keyboard,
    user_main_menu,
    wallet_actions_keyboard,
)
from models import Admin, AppSetting, Category, ConfigSold, Order, RequiredChannel, User
from services.config_service import category_with_counts
from services.crypto_service import check_crypto_payment, create_crypto_invoice
from services.message_service import get_message
from services.payment_method_service import get_active_method_names
from services.payment_service import create_order, fulfill_order, register_receipt
from services.referral_service import referral_stats, register_referral_if_new
from services.wallet_service import change_wallet_balance, get_or_create_wallet

router = Router()


class BuyState(StatesGroup):
    waiting_receipt = State()


async def ensure_user(session: AsyncSession, message: Message) -> tuple[User, bool]:
    user = await session.scalar(select(User).where(User.user_id == message.from_user.id))
    if user:
        return user, False
    user = User(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def get_payment_settings(session: AsyncSession, fallback: Settings) -> tuple[str, str]:
    row = await session.scalar(select(AppSetting).order_by(AppSetting.id).limit(1))
    if row:
        return row.card_number, row.card_holder_name
    return fallback.card_number, fallback.card_holder


async def check_membership(message: Message, session: AsyncSession, bot) -> tuple[bool, list[tuple[str, str]]]:
    channels = (await session.execute(select(RequiredChannel))).scalars().all()
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, message.from_user.id)
            if member.status in {"left", "kicked"}:
                missing.append((f"@{ch.channel_username}", f"https://t.me/{ch.channel_username}"))
        except Exception:
            missing.append((f"@{ch.channel_username}", f"https://t.me/{ch.channel_username}"))
    return len(missing) == 0, missing


def _extract_referrer(message: Message) -> int | None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip()
    return int(arg) if arg.isdigit() else None


@router.message(F.text.startswith("/start"))
async def start_cmd(message: Message, session: AsyncSession, settings: Settings):
    user, is_new = await ensure_user(session, message)
    if is_new:
        await register_referral_if_new(session, user, _extract_referrer(message), settings.referral_reward)

    ok, missing = await check_membership(message, session, message.bot)
    if not ok:
        membership_required_text = await get_message(session, "membership_required_text")
        await message.answer(
            membership_required_text,
            reply_markup=channels_keyboard(missing),
        )
        return
    start_text = await get_message(session, "start_text")
    await message.answer(start_text, reply_markup=user_main_menu())


@router.callback_query(F.data == "check_membership")
async def check_membership_cb(call: CallbackQuery, session: AsyncSession):
    ok, missing = await check_membership(call.message, session, call.bot)
    if not ok:
        membership_not_ok_text = await get_message(session, "membership_not_ok_text")
        await call.message.answer(membership_not_ok_text, reply_markup=channels_keyboard(missing))
    else:
        membership_ok_text = await get_message(session, "membership_ok_text")
        await call.message.answer(membership_ok_text, reply_markup=user_main_menu())
    await call.answer()


@router.message(F.text == "🛒 خرید کانفیگ")
async def buy_menu(message: Message, session: AsyncSession):
    rows = await category_with_counts(session)
    if not rows:
        await message.answer(await get_message(session, "no_plan_text"))
        return
    await message.answer(await get_message(session, "buy_menu_prompt_text"), reply_markup=categories_keyboard(rows))


@router.callback_query(F.data.startswith("buy:"))
async def buy_category(call: CallbackQuery, session: AsyncSession):
    category_id = int(call.data.split(":")[1])
    methods = await get_active_method_names(session)
    if not methods:
        await call.answer(await get_message(session, "no_active_payment_method_text"), show_alert=True)
        return
    await call.message.answer(
        await get_message(session, "payment_methods_prompt_text"),
        reply_markup=payment_methods_keyboard(methods, category_id),
    )
    await call.answer()


@router.callback_query(F.data.regexp(r"^paym:(card|crypto|wallet):\d+$"))
async def choose_payment_method(call: CallbackQuery, session: AsyncSession, state: FSMContext, settings: Settings):
    _, method, cat_id_text = call.data.split(":")
    category_id = int(cat_id_text)

    category = await session.get(Category, category_id)
    if not category:
        await call.answer(await get_message(session, "plan_not_found_text"), show_alert=True)
        return

    user = await session.scalar(select(User).where(User.user_id == call.from_user.id))
    order = await create_order(session, user.id, category_id)

    if method == "card":
        card_number, card_holder = await get_payment_settings(session, settings)
        await state.set_state(BuyState.waiting_receipt)
        await state.update_data(order_id=order.id)
        text = await get_message(session, "card_payment_instruction_text")
        await call.message.answer(
            text.format(
                card_number=card_number,
                card_holder=card_holder,
                price=f"{category.price:,}",
                order_uuid=order.order_uuid,
            )
        )
        await call.answer()
        return

    if method == "wallet":
        ok, msg, _ = await change_wallet_balance(
            session,
            call.from_user.id,
            -category.price,
            reason_method="wallet",
            status="approved",
            order_id=order.id,
        )
        if not ok:
            await call.message.answer(msg or await get_message(session, "wallet_insufficient_text"))
            await call.answer()
            return
        ok2, config_or_msg = await fulfill_order(session, order.id, payment_marker="WALLET_AUTO")
        if ok2:
            post_text = await get_message(session, "post_purchase_text")
            await call.message.answer(post_text.format(config=config_or_msg))
        else:
            await change_wallet_balance(
                session,
                call.from_user.id,
                category.price,
                reason_method="wallet_refund",
                status="approved",
                order_id=order.id,
            )
            await call.message.answer(config_or_msg)
        await call.answer()
        return

    ok, msg, invoice = await create_crypto_invoice(session, settings, order, call.from_user.id, category.price)
    if not ok or not invoice:
        await call.message.answer(msg)
        await call.answer()
        return

    text = await get_message(session, "crypto_invoice_text")
    await call.message.answer(
        text.format(
            currency=invoice.pay_currency,
            amount=invoice.pay_amount,
            address=invoice.pay_address or "-",
            order_uuid=order.order_uuid,
        ),
        reply_markup=crypto_check_keyboard(order.id),
    )
    await call.answer()


@router.callback_query(F.data.regexp(r"^crypto:check:\d+$"))
async def crypto_check_cb(call: CallbackQuery, session: AsyncSession, settings: Settings):
    order_id = int(call.data.split(":")[2])
    ok, msg = await check_crypto_payment(session, settings, order_id)
    if ok:
        post_text = await get_message(session, "post_purchase_text")
        await call.message.answer(post_text.format(config=msg))
    else:
        await call.message.answer(msg)
    await call.answer()


@router.message(BuyState.waiting_receipt, F.photo)
async def receipt_uploaded(message: Message, session: AsyncSession, state: FSMContext, settings: Settings):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer(await get_message(session, "order_not_found_text"))
        return

    payment = await register_receipt(session, order_id, message.photo[-1].file_id)
    order = await session.get(Order, order_id)
    user = await session.scalar(select(User).where(User.user_id == message.from_user.id))
    category = await session.get(Category, order.category_id)
    details = (
        "رسید جدید دریافت شد:\n"
        f"نام کاربر: {user.first_name or '-'}\n"
        f"آیدی کاربر: {user.user_id}\n"
        f"پلن: {category.name}\n"
        f"شماره سفارش: {order.order_uuid}\n"
        f"زمان ارسال: {payment.created_at}"
    )

    db_admins = (await session.execute(select(Admin.user_id))).scalars().all()
    admin_ids = sorted(set(settings.admin_ids + list(db_admins)))
    for admin_id in admin_ids:
        await message.bot.send_photo(
            admin_id,
            message.photo[-1].file_id,
            caption=details,
            reply_markup=approve_payment_kb(payment.id),
        )

    await message.answer(await get_message(session, "receipt_received_text"))
    await state.clear()


@router.message(F.text == "👛 کیف پول من")
async def wallet_menu(message: Message, session: AsyncSession):
    wallet = await get_or_create_wallet(session, message.from_user.id)
    wallet_text = await get_message(session, "wallet_balance_text")
    await message.answer(
        wallet_text.format(balance=f"{wallet.balance:,}"),
        reply_markup=wallet_actions_keyboard(),
    )


@router.callback_query(F.data == "wallet:buy")
async def wallet_buy_info(call: CallbackQuery, session: AsyncSession):
    await call.message.answer(await get_message(session, "wallet_buy_hint_text"))
    await call.answer()


@router.message(F.text == "🎁 دعوت دوستان")
async def invite_friends(message: Message, session: AsyncSession):
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    cnt, reward = await referral_stats(session, message.from_user.id)
    invite_text = await get_message(session, "invite_text")
    await message.answer(invite_text.format(link=link, count=cnt, reward=f"{reward:,}"))


@router.message(F.text == "📦 خریدهای من")
async def my_purchases(message: Message, session: AsyncSession):
    rows = (
        await session.execute(
            select(ConfigSold, Category.name)
            .join(Category, Category.id == ConfigSold.category_id)
            .where(ConfigSold.user_id == message.from_user.id)
            .order_by(ConfigSold.id.desc())
            .limit(20)
        )
    ).all()
    if not rows:
        await message.answer(await get_message(session, "my_purchases_empty_text"))
        return

    text = "📦 خریدهای شما:\n\n" + "\n\n".join(
        [f"تاریخ: {sold.sold_at}\nپلن: {name}\nکانفیگ:\n{sold.config_text}" for sold, name in rows]
    )
    await message.answer(text)


@router.message(F.text == "📊 وضعیت سفارش")
async def order_status(message: Message, session: AsyncSession):
    user = await session.scalar(select(User).where(User.user_id == message.from_user.id))
    if not user:
        await message.answer(await get_message(session, "user_not_found_text"))
        return
    order = await session.scalar(select(Order).where(Order.user_id_fk == user.id).order_by(Order.id.desc()))
    if not order:
        await message.answer(await get_message(session, "order_not_found_text"))
        return
    order_status_text = await get_message(session, "order_status_text")
    await message.answer(order_status_text.format(order_uuid=order.order_uuid, status=order.status))


@router.message(F.text == "📞 پشتیبانی")
async def support(message: Message, session: AsyncSession, settings: Settings):
    support_text = await get_message(session, "support_text")
    await message.answer(support_text.format(support_username=settings.support_username))
