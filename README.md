# ربات فروش کانفیگ VPN (aiogram + SQLAlchemy)

این پروژه یک ربات تلگرام تولیدی برای فروش کانفیگ است که رابط کاربری آن کاملاً فارسی طراحی شده است.

## امکانات
- عضویت اجباری در کانال‌ها قبل از استفاده
- ثبت کاربر و جلوگیری از ثبت تکراری
- خرید پلن، ارسال رسید و تایید/رد توسط ادمین
- مدیریت موجودی کانفیگ (موجود/فروخته‌شده)
- پنل مدیریت فارسی
- خروجی TXT و Excel از فروش‌ها
- پیام همگانی
- آمار فروش

## نصب و اجرا

### 1) پیش‌نیاز
- Python 3.11+

### 2) نصب وابستگی‌ها
```bash
cd project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) تنظیم متغیرهای محیطی
یک فایل `.env` در پوشه `project` بسازید:

```env
BOT_TOKEN=8691172430:AAFis21Pt-naVr53NeGnJIqc4gLIFsU4t04
ADMIN_IDS=5633852960
DATABASE_URL=sqlite+aiosqlite:///vpn_seller.db
CARD_NUMBER=6037-9981-6787-6506
CARD_HOLDER=محمدعلی رئیسی
SUPPORT_USERNAME=@vaslimo1
```

> برای PostgreSQL از این فرمت استفاده کنید:
> `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname`

### 4) اجرای ربات
```bash
python -m bot.main
```

## Docker

### Dockerfile
فایل `Dockerfile` آماده است.

### Build و Run
```bash
docker build -t vpn-seller-bot .
docker run -d --name vpn-bot --env-file .env vpn-seller-bot
```

## استقرار روی VPS
1. کد را روی سرور کپی کنید.
2. Python و virtualenv نصب کنید.
3. `.env` را تنظیم کنید.
4. با `systemd` یا `docker` سرویس را دائمی اجرا کنید.

نمونه `systemd`:
```ini
[Unit]
Description=VPN Seller Bot
After=network.target

[Service]
WorkingDirectory=/opt/vpn-seller/project
ExecStart=/opt/vpn-seller/project/.venv/bin/python -m bot.main
Restart=always
User=www-data
EnvironmentFile=/opt/vpn-seller/project/.env

[Install]
WantedBy=multi-user.target
```

سپس:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn-bot
sudo systemctl start vpn-bot
```

## نکات امنیتی
- فقط ادمین‌ها به `/admin` دسترسی دارند.
- محدودکننده نرخ پیام برای جلوگیری از اسپم فعال است.
- هر کانفیگ فقط یکبار فروخته می‌شود.

