import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 5, window: int = 3):
        self.limit = limit
        self.window = window
        self.buckets = defaultdict(deque)

    async def __call__(self, handler, event: TelegramObject, data):
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
            now = time.time()
            q = self.buckets[uid]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                await event.answer("⏳ لطفاً کمی صبر کنید و دوباره تلاش کنید.")
                return
            q.append(now)
        return await handler(event, data)
