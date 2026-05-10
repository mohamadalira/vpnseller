from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def user_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 خرید کانفیگ"), KeyboardButton(text="📦 خریدهای من")],
            [KeyboardButton(text="📊 وضعیت سفارش"), KeyboardButton(text="📞 پشتیبانی")],
            [KeyboardButton(text="📚 آموزش استفاده")],
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
