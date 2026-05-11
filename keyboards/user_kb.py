from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def user_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 خرید کانفیگ"), KeyboardButton(text="👛 کیف پول من")],
            [KeyboardButton(text="🎁 دعوت دوستان"), KeyboardButton(text="📦 خریدهای من")],
            [KeyboardButton(text="📊 وضعیت سفارش"), KeyboardButton(text="📞 پشتیبانی")],
        ],
        resize_keyboard=True,
    )


def channels_keyboard(channels: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, url=link)] for title, link in channels]
    rows.append([InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="check_membership")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_keyboard(rows: list[tuple[int, str, int, int]]) -> InlineKeyboardMarkup:
    kb = []
    for cid, name, price, count in rows:
        kb.append([InlineKeyboardButton(text=f"{name} | {price:,} تومان | موجودی: {count}", callback_data=f"buy:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def payment_methods_keyboard(methods: set[str], category_id: int) -> InlineKeyboardMarkup:
    rows = []
    if "card" in methods:
        rows.append([InlineKeyboardButton(text="💳 کارت به کارت", callback_data=f"paym:card:{category_id}")])
    if "crypto" in methods:
        rows.append([InlineKeyboardButton(text="🪙 پرداخت کریپتو", callback_data=f"paym:crypto:{category_id}")])
    if "wallet" in methods:
        rows.append([InlineKeyboardButton(text="👛 پرداخت با کیف پول", callback_data=f"paym:wallet:{category_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛒 استفاده برای خرید", callback_data="wallet:buy")]]
    )


def crypto_check_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بررسی پرداخت کریپتو", callback_data=f"crypto:check:{order_id}")]
        ]
    )
