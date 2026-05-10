from pathlib import Path
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ConfigSold


async def export_sold_to_txt(session: AsyncSession, path: str) -> str:
    rows = (await session.execute(select(ConfigSold).order_by(ConfigSold.id))).scalars().all()
    p = Path(path)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(
                f"user_id={r.user_id} | username={r.username} | category={r.category_id} | config={r.config_text} | "
                f"date={r.sold_at} | payment_id={r.payment_id}\n"
            )
    return str(p)


async def export_sold_to_excel(session: AsyncSession, path: str) -> str:
    rows = (await session.execute(select(ConfigSold).order_by(ConfigSold.id))).scalars().all()
    wb = Workbook()
    ws = wb.active
    ws.title = "sales"
    ws.append(["user_id", "username", "category", "config_text", "date", "payment_id"])
    for r in rows:
        ws.append([r.user_id, r.username, r.category_id, r.config_text, str(r.sold_at), r.payment_id])
    wb.save(path)
    return path
