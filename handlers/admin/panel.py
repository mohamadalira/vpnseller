from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from keyboards.admin_kb import (
    admin_menu,
    admins_manage_kb,
    card_manage_kb,
    category_manage_kb,
    category_select_kb,
    channels_manage_kb,
    confirm_delete_kb,
)
from models import Admin, AppSetting, Category, ConfigAvailable, ConfigSold, Order, Payment, RequiredChannel, User
from services.admin_service import (
    add_admin,
    create_category,
    create_channel,
    delete_category_safe,
    delete_channel,
    get_or_create_settings,
    remove_admin,
    update_category_name,
    update_category_price,
)
from services.config_service import add_configs_bulk, category_with_counts, inventory_stats
from services.export_service import export_sold_to_excel, export_sold_to_txt
from services.payment_service import approve_payment, reject_payment
from utils.auth import admin_guard

router = Router()


class AdminState(StatesGroup):
    add_config_category = State()
    add_config_text = State()
    broadcast = State()

    add_plan_name = State()
    add_plan_price = State()

    edit_plan_name = State()
    edit_plan_price = State()

    price_change = State()

    card_number = State()
    card_holder = State()

    add_channel = State()
    delete_channel = State()

    add_admin = State()
    delete_admin = State()


async def _is_admin_user(call: CallbackQuery, session: AsyncSession, settings: Settings) -> bool:
    user_id = call.from_user.id
    if user_id in settings.admin_ids:
        return True
    row = await session.scalar(select(Admin).where(Admin.user_id == user_id))
    return row is not None


@router.message(F.text == "/admin")
async def admin_panel(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await message.answer("به پنل مدیریت خوش آمدید.", reply_markup=admin_menu())


@router.callback_query(F.data.startswith("approve:"))
async def approve_cb(call: CallbackQuery, session: AsyncSession):
    payment_id = int(call.data.split(":")[1])
    ok, msg = await approve_payment(session, payment_id)
    payment = await session.get(Payment, payment_id)
    if ok and payment:
        order = await session.get(Order, payment.order_id)
        user = await session.scalar(select(User).where(User.id == order.user_id_fk))
        await call.bot.send_message(user.user_id, f"✅ پرداخت شما تایید شد.\nکانفیگ شما:\n\n{msg}")
        await call.message.answer("پرداخت تایید شد و کانفیگ ارسال گردید.")
    else:
        await call.message.answer(msg)
    await call.answer()


@router.callback_query(F.data.startswith("reject:"))
async def reject_cb(call: CallbackQuery, session: AsyncSession):
    payment_id = int(call.data.split(":")[1])
    ok, msg = await reject_payment(session, payment_id)
    payment = await session.get(Payment, payment_id)
    if ok and payment:
        order = await session.get(Order, payment.order_id)
        user = await session.scalar(select(User).where(User.id == order.user_id_fk))
        await call.bot.send_message(user.user_id, "❌ پرداخت شما رد شد. لطفا با پشتیبانی تماس بگیرید.")
    await call.message.answer(msg)
    await call.answer()


@router.message(F.text == "📦 مشاهده موجودی")
async def show_inventory(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    rows = await inventory_stats(session)
    if not rows:
        await message.answer("پلنی ثبت نشده است.")
        return
    text = "داشبورد موجودی:\n\n" + "\n".join([f"{name} | {available} | {sold}" for name, available, sold in rows])
    text += "\n\n(فرمت: پلن | موجودی | فروخته شده)"
    await message.answer(text)


@router.message(F.text == "📊 آمار فروش")
async def stats(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    users = await session.scalar(select(func.count(User.id)))
    sales = await session.scalar(select(func.count(ConfigSold.id)))
    income = await session.scalar(
        select(func.coalesce(func.sum(Category.price), 0)).join(ConfigSold, ConfigSold.category_id == Category.id)
    )
    inv = await session.scalar(select(func.count(ConfigAvailable.id)))
    await message.answer(
        f"تعداد کاربران: {users}\nتعداد فروش: {sales}\nدرآمد کل: {income:,} تومان\nموجودی کل کانفیگ‌ها: {inv}"
    )


@router.message(F.text == "📥 پرداخت‌های در انتظار")
async def pending_payments(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    rows = (
        await session.execute(select(Payment).where(Payment.status == "waiting_approval").order_by(Payment.id.desc()))
    ).scalars().all()
    if not rows:
        await message.answer("پرداخت در انتظاری وجود ندارد.")
        return
    await message.answer(f"تعداد {len(rows)} پرداخت در انتظار تایید است. رسیدها در چت ادمین ارسال شده‌اند.")


@router.message(F.text == "⚙️ مدیریت کانفیگ‌ها")
async def category_management_entry(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await message.answer("مدیریت پلن‌ها:", reply_markup=category_manage_kb())


@router.callback_query(F.data == "cat:list")
async def category_list(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    rows = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    if not rows:
        await call.message.answer("هیچ پلنی ثبت نشده است.")
    else:
        text = "📋 لیست پلن‌ها:\n\n" + "\n".join(
            [f"شناسه: {c.id} | نام: {c.name} | قیمت: {c.price:,} تومان" for c in rows]
        )
        await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "cat:add")
async def category_add_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.add_plan_name)
    await call.message.answer("نام پلن را وارد کنید:")
    await call.answer()


@router.message(AdminState.add_plan_name)
async def category_add_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("نام پلن معتبر نیست.")
        return
    await state.update_data(new_plan_name=name)
    await state.set_state(AdminState.add_plan_price)
    await message.answer("قیمت پلن را وارد کنید (فقط عدد):")


@router.message(AdminState.add_plan_price)
async def category_add_price(message: Message, state: FSMContext, session: AsyncSession):
    if not (message.text or "").isdigit():
        await message.answer("قیمت باید عدد باشد.")
        return
    data = await state.get_data()
    ok, msg = await create_category(session, data["new_plan_name"], int(message.text))
    await message.answer(msg)
    await state.clear()


@router.callback_query(F.data == "cat:edit")
async def category_edit_start(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    rows = (await session.execute(select(Category.id, Category.name).order_by(Category.id))).all()
    if not rows:
        await call.message.answer("هیچ پلنی وجود ندارد.")
    else:
        await call.message.answer("پلن موردنظر برای ویرایش را انتخاب کنید:", reply_markup=category_select_kb(rows, "catid"))
    await call.answer()


@router.callback_query(F.data.startswith("catid:"))
async def category_edit_choose(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    category_id = int(call.data.split(":")[1])
    await state.update_data(edit_category_id=category_id)
    await call.message.answer("گزینه ویرایش را ارسال کنید:\n1) تغییر نام\n2) تغییر قیمت")
    await call.answer()


@router.message(F.text == "1) تغییر نام")
async def choose_edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    if "edit_category_id" not in data:
        return
    await state.set_state(AdminState.edit_plan_name)
    await message.answer("نام جدید پلن را وارد کنید:")


@router.message(F.text == "2) تغییر قیمت")
async def choose_edit_price(message: Message, state: FSMContext):
    data = await state.get_data()
    if "edit_category_id" not in data:
        return
    await state.set_state(AdminState.edit_plan_price)
    await message.answer("قیمت جدید پلن را وارد کنید:")


@router.message(AdminState.edit_plan_name)
async def edit_name_submit(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    ok, msg = await update_category_name(session, data["edit_category_id"], (message.text or "").strip())
    await message.answer(msg)
    await state.clear()


@router.message(AdminState.edit_plan_price)
async def edit_price_submit(message: Message, state: FSMContext, session: AsyncSession):
    if not (message.text or "").isdigit():
        await message.answer("قیمت باید عدد باشد.")
        return
    data = await state.get_data()
    ok, msg = await update_category_price(session, data["edit_category_id"], int(message.text))
    await message.answer(msg)
    await state.clear()


@router.callback_query(F.data == "cat:delete")
async def category_delete_start(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    rows = (await session.execute(select(Category.id, Category.name).order_by(Category.id))).all()
    if not rows:
        await call.message.answer("هیچ پلنی برای حذف وجود ندارد.")
    else:
        await call.message.answer("پلن را انتخاب کنید:", reply_markup=category_select_kb(rows, "catdel"))
        await call.message.answer("پس از انتخاب، تایید حذف نمایش داده می‌شود.")
    await call.answer()


@router.callback_query(F.data.regexp(r"^catdel:\\d+$"))
async def category_delete_confirm(call: CallbackQuery):
    category_id = int(call.data.split(":")[1])
    await call.message.answer(
        "آیا از حذف این پلن مطمئن هستید؟",
        reply_markup=confirm_delete_kb("catdel", category_id),
    )
    await call.answer()


@router.callback_query(F.data == "cat:stock")
async def add_stock_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    rows = await category_with_counts(session)
    text = "برای افزودن کانفیگ، شناسه پلن را ارسال کنید:\n" + "\n".join([f"{cid}) {name}" for cid, name, _, _ in rows])
    await state.set_state(AdminState.add_config_category)
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data.startswith("catdel:yes:"))
async def category_delete_apply(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    category_id = int(call.data.split(":")[2])
    ok, msg = await delete_category_safe(session, category_id)
    await call.message.answer(msg)
    await call.answer()


@router.callback_query(F.data == "catdel:no")
async def category_delete_cancel(call: CallbackQuery):
    await call.message.answer("عملیات حذف لغو شد.")
    await call.answer()


@router.message(F.text == "💰 مدیریت قیمت پلن‌ها")
async def price_manage_start(message: Message, session: AsyncSession, settings: Settings, state: FSMContext):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    rows = (await session.execute(select(Category).order_by(Category.id))).scalars().all()
    if not rows:
        await message.answer("هیچ پلنی ثبت نشده است.")
        return
    text = "لیست پلن‌ها:\n" + "\n".join([f"{c.id}) {c.name} — {c.price:,} تومان" for c in rows])
    text += "\n\nشناسه پلن را ارسال کنید."
    await state.set_state(AdminState.price_change)
    await message.answer(text)


@router.message(AdminState.price_change)
async def price_manage_submit(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    if "price_category_id" not in data:
        if not (message.text or "").isdigit():
            await message.answer("شناسه پلن معتبر نیست.")
            return
        await state.update_data(price_category_id=int(message.text))
        await message.answer("قیمت جدید را وارد کنید:")
        return

    if not (message.text or "").isdigit():
        await message.answer("قیمت باید عدد باشد.")
        return
    ok, msg = await update_category_price(session, data["price_category_id"], int(message.text))
    await message.answer(msg)
    await state.clear()


@router.message(F.text == "💳 مدیریت شماره کارت")
async def card_manage_start(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await get_or_create_settings(session)
    await message.answer("مدیریت اطلاعات پرداخت:", reply_markup=card_manage_kb())


@router.callback_query(F.data == "card:view")
async def card_view(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    st = await get_or_create_settings(session)
    await call.message.answer(f"💳 شماره کارت: {st.card_number}\n👤 نام صاحب کارت: {st.card_holder_name}")
    await call.answer()


@router.callback_query(F.data == "card:number")
async def card_number_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.card_number)
    await call.message.answer("شماره کارت جدید را وارد کنید:")
    await call.answer()


@router.message(AdminState.card_number)
async def card_number_submit(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 8:
        await message.answer("شماره کارت معتبر نیست.")
        return
    st = await get_or_create_settings(session)
    st.card_number = value
    await session.commit()
    await message.answer("شماره کارت با موفقیت به‌روزرسانی شد ✅")
    await state.clear()


@router.callback_query(F.data == "card:holder")
async def card_holder_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.card_holder)
    await call.message.answer("نام جدید صاحب کارت را وارد کنید:")
    await call.answer()


@router.message(AdminState.card_holder)
async def card_holder_submit(message: Message, session: AsyncSession, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 3:
        await message.answer("نام وارد شده معتبر نیست.")
        return
    st = await get_or_create_settings(session)
    st.card_holder_name = value
    await session.commit()
    await message.answer("نام صاحب کارت با موفقیت به‌روزرسانی شد ✅")
    await state.clear()


@router.message(F.text == "📡 مدیریت کانال‌های اجباری")
async def channels_manage_start(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await message.answer("مدیریت کانال‌های اجباری:", reply_markup=channels_manage_kb())


@router.callback_query(F.data == "chn:list")
async def channels_list(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    rows = (await session.execute(select(RequiredChannel).order_by(RequiredChannel.id))).scalars().all()
    if not rows:
        await call.message.answer("لیست کانال‌های اجباری خالی است.")
    else:
        await call.message.answer(
            "📋 لیست کانال‌ها:\n\n" + "\n".join([f"{c.channel_id} | @{c.channel_username}" for c in rows])
        )
    await call.answer()


@router.callback_query(F.data == "chn:add")
async def channels_add_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.add_channel)
    await call.message.answer("اطلاعات کانال را ارسال کنید:\nchannel_id | channel_username")
    await call.answer()


@router.message(AdminState.add_channel)
async def channels_add_submit(message: Message, session: AsyncSession, state: FSMContext):
    try:
        raw_id, username = [x.strip() for x in (message.text or "").split("|", 1)]
        ok, msg = await create_channel(session, int(raw_id), username)
        await message.answer(msg)
        await state.clear()
    except Exception:
        await message.answer("فرمت اشتباه است. نمونه صحیح: -1001234567890 | my_channel")


@router.callback_query(F.data == "chn:delete")
async def channels_delete_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.delete_channel)
    await call.message.answer("channel_id کانال موردنظر برای حذف را ارسال کنید:")
    await call.answer()


@router.message(AdminState.delete_channel)
async def channels_delete_submit(message: Message, session: AsyncSession, state: FSMContext):
    if not (message.text or "").lstrip("-").isdigit():
        await message.answer("channel_id معتبر نیست.")
        return
    ok, msg = await delete_channel(session, int(message.text))
    await message.answer(msg)
    await state.clear()


@router.message(F.text == "👤 مدیریت ادمین‌ها")
async def admins_manage_start(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await message.answer("مدیریت ادمین‌ها:", reply_markup=admins_manage_kb())


@router.callback_query(F.data == "adm:list")
async def admins_list(call: CallbackQuery, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    db_admins = (await session.execute(select(Admin.user_id).order_by(Admin.id))).scalars().all()
    env_admins = settings.admin_ids
    text = "📋 لیست ادمین‌ها:\n\n"
    text += "ادمین‌های ENV:\n" + ("\n".join([str(x) for x in env_admins]) if env_admins else "-")
    text += "\n\nادمین‌های دیتابیس:\n" + ("\n".join([str(x) for x in db_admins]) if db_admins else "-")
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "adm:add")
async def admins_add_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.add_admin)
    await call.message.answer("user_id ادمین جدید را ارسال کنید:")
    await call.answer()


@router.message(AdminState.add_admin)
async def admins_add_submit(message: Message, session: AsyncSession, state: FSMContext):
    if not (message.text or "").isdigit():
        await message.answer("user_id باید عدد باشد.")
        return
    ok, msg = await add_admin(session, int(message.text))
    await message.answer(msg)
    await state.clear()


@router.callback_query(F.data == "adm:delete")
async def admins_delete_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    if not await _is_admin_user(call, session, settings):
        return await call.answer("دسترسی ندارید", show_alert=True)
    await state.set_state(AdminState.delete_admin)
    await call.message.answer("user_id ادمینی که می‌خواهید حذف شود را ارسال کنید:")
    await call.answer()


@router.message(AdminState.delete_admin)
async def admins_delete_submit(message: Message, session: AsyncSession, state: FSMContext, settings: Settings):
    if not (message.text or "").isdigit():
        await message.answer("user_id باید عدد باشد.")
        return
    ok, msg = await remove_admin(session, int(message.text), settings.admin_ids)
    await message.answer(msg)
    await state.clear()


@router.message(F.text == "📤 خروجی اکسل فروش")
async def export_excel(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    p = await export_sold_to_excel(session, "sold_configs.xlsx")
    await message.answer_document(FSInputFile(p), caption="خروجی اکسل فروش")


@router.message(F.text == "📄 کانفیگ‌های فروخته شده")
async def export_txt(message: Message, session: AsyncSession, settings: Settings):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    p = await export_sold_to_txt(session, "sold_configs.txt")
    await message.answer_document(FSInputFile(p), caption="خروجی TXT کانفیگ‌های فروخته شده")


@router.message(F.text == "📢 ارسال پیام همگانی")
async def ask_broadcast(message: Message, session: AsyncSession, settings: Settings, state: FSMContext):
    if not await admin_guard(message, session, settings.admin_ids):
        return
    await state.set_state(AdminState.broadcast)
    await message.answer("پیام همگانی را ارسال کنید (متن/عکس/ویدیو).")


@router.message(AdminState.broadcast)
async def send_broadcast(message: Message, session: AsyncSession, state: FSMContext):
    users = (await session.execute(select(User.user_id))).scalars().all()
    sent = 0
    for uid in users:
        try:
            await message.send_copy(chat_id=uid)
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"ارسال همگانی انجام شد. تعداد موفق: {sent}")


@router.message(AdminState.add_config_category)
async def choose_category(message: Message, state: FSMContext):
    if not (message.text or "").isdigit():
        await message.answer("شناسه پلن نامعتبر است.")
        return
    await state.update_data(category_id=int(message.text))
    await state.set_state(AdminState.add_config_text)
    await message.answer("کانفیگ‌ها را Paste کنید یا فایل TXT ارسال کنید.")


@router.message(AdminState.add_config_text, F.document)
async def add_configs_txt(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    category_id = data["category_id"]
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".txt"):
        await message.answer("فقط فایل TXT مجاز است.")
        return
    file = await message.bot.get_file(doc.file_id)
    content = await message.bot.download_file(file.file_path)
    text = content.read().decode("utf-8", errors="ignore")
    count = await add_configs_bulk(session, category_id, text.splitlines())
    await message.answer(f"{count} کانفیگ اضافه شد ✅")
    await state.clear()


@router.message(AdminState.add_config_text)
async def add_configs_paste(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    category_id = data["category_id"]
    count = await add_configs_bulk(session, category_id, (message.text or "").splitlines())
    await message.answer(f"{count} کانفیگ اضافه شد ✅")
    await state.clear()
