import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    bot_token: str
    admin_ids: list[int]
    database_url: str
    card_number: str
    card_holder: str
    support_username: str


def _parse_admin_ids(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("BOT_TOKEN تنظیم نشده است")
    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///vpn_seller.db"),
        card_number=os.getenv("CARD_NUMBER", "XXXX-XXXX-XXXX-XXXX"),
        card_holder=os.getenv("CARD_HOLDER", "نام دارنده"),
        support_username=os.getenv("SUPPORT_USERNAME", "@support"),
    )
