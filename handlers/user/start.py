from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from keyboards.user_kb import categories_keyboard, channels_keyboard, user_main_menu
from models import AppSetting, Category, ConfigSold, Order, RequiredChannel, User
from services.config_service import category_with_counts
from services.payment_service import create_order, register_receipt

router = Router()


class BuyState(StatesGroup):
    waiting_receipt = State()


async def ensure_user(session: AsyncSession, message: Message) -> User:
    user = await session.scalar(select(User).where(User.user_id == message.from_user.id))
    if user:
        return user
    user = User(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


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


@router.message(F.text == "/start")
async def start_cmd(message: Message, session: AsyncSession, settings: Settings):
    await ensure_user(session, message)
    ok, missing = await check_membership(message, session, message.bot)
    if not ok:
        await message.answer(
            "برای استفاده از ربات باید ابتدا در کانال‌های زیر عضو شوید:",
            reply_markup=channels_keyboard(missing),
        )
        return
    await message.answer("به ربات فروش کانفیگ خوش آمدید 🌹", reply_markup=user_main_menu())


@router.callback_query(F.data == "check_membership")
async def check_membership_cb(call: CallbackQuery, session: AsyncSession):
    ok, missing = await check_membership(call.message, session, call.bot)
    if not ok:
        await call.message.answer("هنوز در همه کانال‌ها عضو نشده‌اید.", reply_markup=channels_keyboard(missing))
    else:
        await call.message.answer("عضویت شما تایید شد ✅", reply_markup=user_main_menu())
    await call.answer()


@router.message(F.text == "🛒 خرید کانفیگ")
async def buy_menu(message: Message, session: AsyncSession):
    rows = await category_with_counts(session)
    if not rows:
        await message.answer("در حال حاضر هیچ پلنی ثبت نشده است.")
        return
    await message.answer("پلن موردنظر را انتخاب کنید:", reply_markup=categories_keyboard(rows))


@router.callback_query(F.data.startswith("buy:"))
async def buy_category(call: CallbackQuery, session: AsyncSession, state: FSMContext, settings: Settings):
    category_id = int(call.data.split(":")[1])
    category = await session.get(Category, category_id)
    if not category:
        await call.answer("پلن یافت نشد", show_alert=True)
        return

    user = await session.scalar(select(User).where(User.user_id == call.from_user.id))
    order = await create_order(session, user.id, category_id)
    card_number, card_holder = await get_payment_settings(session, settings)

    await state.set_state(BuyState.waiting_receipt)
    await state.update_data(order_id=order.id)
    text = (
        "برای خرید این پلن لطفاً مبلغ زیر را کارت به کارت کنید.\n\n"
        f"💳 شماره کارت: {card_number}\n"
        f"👤 نام صاحب کارت: {card_holder}\n"
        f"💰 مبلغ: {category.price:,} تومان\n\n"
        "پس از پرداخت، عکس رسید را ارسال کنید.\n"
        f"شماره سفارش: {order.order_uuid}"
    )
    await call.message.answer(text)
    await call.answer()


@router.message(BuyState.waiting_receipt, F.photo)
async def receipt_uploaded(message: Message, session: AsyncSession, state: FSMContext, settings: Settings):
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("سفارشی یافت نشد. دوباره تلاش کنید.")
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

    from keyboards.admin_kb import approve_payment_kb

    for admin_id in settings.admin_ids:
        await message.bot.send_photo(
            admin_id,
            message.photo[-1].file_id,
            caption=details,
            reply_markup=approve_payment_kb(payment.id),
        )

    await message.answer("رسید شما دریافت شد ✅\nپس از بررسی ادمین نتیجه اطلاع‌رسانی می‌شود.")
    await state.clear()


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
        await message.answer("هنوز خریدی ثبت نشده است.")
        return

    text = "📦 خریدهای شما:\n\n" + "\n\n".join(
        [f"تاریخ: {sold.sold_at}\nپلن: {name}\nکانفیگ:\n{sold.config_text}" for sold, name in rows]
    )
    await message.answer(text)


@router.message(F.text == "📊 وضعیت سفارش")
async def order_status(message: Message, session: AsyncSession):
    user = await session.scalar(select(User).where(User.user_id == message.from_user.id))
    if not user:
        await message.answer("کاربری یافت نشد.")
        return
    order = await session.scalar(select(Order).where(Order.user_id_fk == user.id).order_by(Order.id.desc()))
    if not order:
        await message.answer("سفارشی یافت نشد.")
        return
    await message.answer(f"آخرین سفارش شما: {order.order_uuid}\nوضعیت: {order.status}")


@router.message(F.text == "📞 پشتیبانی")
async def support(message: Message, settings: Settings):
    await message.answer(f"برای پشتیبانی پیام دهید: {settings.support_username}")


@router.message(F.text == "📚 آموزش استفاده")
async def help_usage(message: Message):
    await message.answer(
        "1) از منوی خرید، پلن را انتخاب کنید.\n"
        "2) مبلغ را کارت به کارت کنید.\n"
        "3) عکس رسید را ارسال کنید.\n"
        "4) پس از تایید ادمین، کانفیگ ارسال می‌شود."
    )
