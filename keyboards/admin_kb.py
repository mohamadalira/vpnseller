from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def admin_menu() -> ReplyKeyboardMarkup:
    items = [
        ["⚙️ مدیریت کانفیگ‌ها", "📦 مشاهده موجودی"],
        ["💰 مدیریت قیمت پلن‌ها", "💳 مدیریت شماره کارت"],
        ["📊 آمار فروش", "📄 کانفیگ‌های فروخته شده"],
        ["📤 خروجی اکسل فروش", "📢 ارسال پیام همگانی"],
        ["📥 پرداخت‌های در انتظار", "📡 مدیریت کانال‌های اجباری"],
        ["👤 مدیریت ادمین‌ها"],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in items],
        resize_keyboard=True,
    )


def approve_payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید پرداخت", callback_data=f"approve:{payment_id}"),
                InlineKeyboardButton(text="❌ رد پرداخت", callback_data=f"reject:{payment_id}"),
            ]
        ]
    )


def category_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 افزودن کانفیگ به پلن", callback_data="cat:stock")],
            [InlineKeyboardButton(text="➕ افزودن پلن جدید", callback_data="cat:add")],
            [InlineKeyboardButton(text="✏️ ویرایش پلن", callback_data="cat:edit")],
            [InlineKeyboardButton(text="❌ حذف پلن", callback_data="cat:delete")],
            [InlineKeyboardButton(text="📋 مشاهده لیست پلن‌ها", callback_data="cat:list")],
        ]
    )


def category_select_kb(rows: list[tuple[int, str]], prefix: str = "catid") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{name} ({cid})", callback_data=f"{prefix}:{cid}")] for cid, name in rows
        ]
    )


def confirm_delete_kb(prefix: str, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله، حذف شود", callback_data=f"{prefix}:yes:{item_id}"),
                InlineKeyboardButton(text="❌ انصراف", callback_data=f"{prefix}:no"),
            ]
        ]
    )


def channels_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن کانال", callback_data="chn:add")],
            [InlineKeyboardButton(text="❌ حذف کانال", callback_data="chn:delete")],
            [InlineKeyboardButton(text="📋 مشاهده لیست کانال‌ها", callback_data="chn:list")],
        ]
    )


def admins_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="adm:add")],
            [InlineKeyboardButton(text="❌ حذف ادمین", callback_data="adm:delete")],
            [InlineKeyboardButton(text="📋 لیست ادمین‌ها", callback_data="adm:list")],
        ]
    )


def card_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 مشاهده شماره کارت فعلی", callback_data="card:view")],
            [InlineKeyboardButton(text="✏️ تغییر شماره کارت", callback_data="card:number")],
            [InlineKeyboardButton(text="✏️ تغییر نام صاحب کارت", callback_data="card:holder")],
        ]
    )
