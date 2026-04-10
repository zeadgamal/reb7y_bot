"""
Middlewares
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from services.security_service import check_rate_limit, is_user_banned, log_activity
from services.settings_service import is_maintenance
from services.user_service import get_user, increment_message_count
from config import config

logger = logging.getLogger(__name__)


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and user.id != config.ADMIN_ID:
            banned, reason = await is_user_banned(user.id)
            if banned:
                if isinstance(event, Message):
                    await event.answer(f"⛔️ تم حظرك من استخدام البوت.\nالسبب: {reason}")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"⛔️ تم حظرك: {reason}", show_alert=True)
                return

            maintenance = await is_maintenance()
            if maintenance:
                if isinstance(event, Message):
                    await event.answer("🔧 البوت في وضع الصيانة. يرجى المحاولة لاحقاً.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🔧 وضع الصيانة", show_alert=True)
                return

        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and user.id != config.ADMIN_ID:
            allowed = await check_rate_limit(user.id, 'global', limit=30, window=60)
            if not allowed:
                if isinstance(event, Message):
                    await event.answer("⚠️ أنت ترسل رسائل بسرعة كبيرة. انتظر قليلاً.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ تباطأ قليلاً!", show_alert=True)
                return

        return await handler(event, data)


class ActivityTrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            db_user = await get_user(user.id)
            if db_user:
                await increment_message_count(user.id)

        return await handler(event, data)
