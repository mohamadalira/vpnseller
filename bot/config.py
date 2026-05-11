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
    nowpayments_api_key: str
    nowpayments_base_url: str
    crypto_pay_currency: str
    referral_reward: int
    nowpayments_ipn_secret: str
    nowpayments_webhook_host: str
    nowpayments_webhook_port: int
    nowpayments_webhook_path: str


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
        nowpayments_api_key=os.getenv("NOWPAYMENTS_API_KEY", ""),
        nowpayments_base_url=os.getenv("NOWPAYMENTS_BASE_URL", "https://api.nowpayments.io/v1"),
        crypto_pay_currency=os.getenv("CRYPTO_PAY_CURRENCY", "usdttrc20"),
        referral_reward=int(os.getenv("REFERRAL_REWARD", "10000")),
        nowpayments_ipn_secret=os.getenv("NOWPAYMENTS_IPN_SECRET", ""),
        nowpayments_webhook_host=os.getenv("NOWPAYMENTS_WEBHOOK_HOST", "0.0.0.0"),
        nowpayments_webhook_port=int(os.getenv("NOWPAYMENTS_WEBHOOK_PORT", "8081")),
        nowpayments_webhook_path=os.getenv("NOWPAYMENTS_WEBHOOK_PATH", "/nowpayments/webhook"),
    )
