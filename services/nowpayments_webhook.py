import hashlib
import hmac
import json
import logging

from aiohttp import web
from sqlalchemy import select

from bot import database
from bot.config import Settings
from models import CryptoInvoice, Transaction
from services.payment_service import fulfill_order

logger = logging.getLogger(__name__)


def _verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature or "")


async def handle_nowpayments_webhook(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    raw_body = await request.read()
    signature = request.headers.get("x-nowpayments-sig", "")

    if not _verify_signature(raw_body, signature, settings.nowpayments_ipn_secret):
        return web.json_response({"ok": False, "error": "invalid signature"}, status=403)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    payment_id = str(payload.get("payment_id") or "")
    status = (payload.get("payment_status") or "").lower()
    tx_hash = payload.get("payin_hash") or payload.get("actually_paid")
    if not payment_id:
        return web.json_response({"ok": False, "error": "missing payment_id"}, status=400)

    if database.SessionLocal is None:
        return web.json_response({"ok": False, "error": "database not ready"}, status=500)

    async with database.SessionLocal() as session:
        invoice = await session.scalar(select(CryptoInvoice).where(CryptoInvoice.external_invoice_id == payment_id))
        if not invoice:
            return web.json_response({"ok": True, "ignored": "invoice not found"})

        invoice.status = status or invoice.status
        tx = await session.scalar(
            select(Transaction).where(Transaction.order_id == invoice.order_id, Transaction.method == "crypto")
        )

        if status in {"finished", "confirmed", "sending"}:
            if tx:
                tx.status = "approved"
                if tx_hash:
                    tx.txid = str(tx_hash)
            ok, msg = await fulfill_order(session, invoice.order_id, payment_marker="CRYPTO_AUTO_WEBHOOK")
            logger.info("crypto webhook fulfill order=%s ok=%s msg=%s", invoice.order_id, ok, msg)
        elif status in {"failed", "expired", "refunded"}:
            if tx:
                tx.status = "failed"
                if tx_hash:
                    tx.txid = str(tx_hash)
            await session.commit()
        else:
            await session.commit()

    return web.json_response({"ok": True})


async def start_nowpayments_webhook_server(settings: Settings) -> web.AppRunner:
    app = web.Application()
    app["settings"] = settings
    app.router.add_post(settings.nowpayments_webhook_path, handle_nowpayments_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.nowpayments_webhook_host, port=settings.nowpayments_webhook_port)
    await site.start()
    logger.info(
        "NOWPayments webhook server started on %s:%s%s",
        settings.nowpayments_webhook_host,
        settings.nowpayments_webhook_port,
        settings.nowpayments_webhook_path,
    )
    return runner
