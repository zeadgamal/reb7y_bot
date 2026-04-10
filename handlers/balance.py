"""
Balance, Referral, Stats & Leaderboard Handlers
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from services.user_service import (
    get_user, get_transaction_history, get_top_referrers
)
from keyboards.keyboards import (
    balance_keyboard, leaderboard_keyboard, back_keyboard
)
from utils.utils import (
    format_balance, format_rank, get_referral_link,
    format_transaction_history, format_leaderboard
)
from config import config

logger = logging.getLogger(__name__)
router = Router()


# =============================================
# Balance Handler
# =============================================

@router.message(F.text == "💰 رصيدي")
async def balance_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("يرجى استخدام /start أولاً")
        return

    rank = format_rank(user.get('rank', 'bronze'))
    balance = format_balance(user.get('balance', 0))
    total_earned = format_balance(user.get('total_earned', 0))
    total_withdrawn = format_balance(user.get('total_withdrawn', 0))
    multiplier = float(user.get('rank_multiplier', 1.0))

    text = (
        f"💰 **محفظتك**\n\n"
        f"{'━' * 25}\n"
        f"💵 الرصيد المتاح: **{balance}**\n"
        f"📈 إجمالي الأرباح: {total_earned}\n"
        f"💸 إجمالي السحوبات: {total_withdrawn}\n"
        f"{'━' * 25}\n\n"
        f"🏆 رتبتك: {rank}\n"
        f"⚡ مضاعف الأرباح: **{multiplier}×**\n"
        f"👥 إحالاتك: **{user.get('referral_count', 0)}** مستخدم"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=balance_keyboard(user['user_id']))


@router.callback_query(F.data == "tx_history")
async def tx_history_callback(callback: CallbackQuery):
    transactions = await get_transaction_history(callback.from_user.id, limit=10)
    text = format_transaction_history(transactions)
    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=back_keyboard("main_menu")
    )
    await callback.answer()


# =============================================
# Referral Link Handler
# =============================================

@router.message(F.text == "🔗 رابط الدعوة")
async def referral_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("يرجى استخدام /start أولاً")
        return

    from services.settings_service import get_referral_reward, get_all_settings
    reward = await get_referral_reward()
    settings = await get_all_settings()
    silver_threshold = int(settings.get('silver_threshold', 20))
    gold_threshold = int(settings.get('gold_threshold', 50))
    referral_count = user.get('referral_count', 0)
    link = get_referral_link(message.from_user.id)

    text = (
        f"🔗 **رابط الدعوة الخاص بك**\n\n"
        f"`{link}`\n\n"
        f"💰 مكافأة كل إحالة: **{reward:.2f} جنيه**\n"
        f"👥 إحالاتك حتى الآن: **{referral_count}**\n\n"
        f"{'━' * 25}\n"
        f"📊 **نظام الرتب:**\n"
        f"🥉 برونزي: الافتراضي\n"
        f"🥈 فضي: {silver_threshold} إحالة (مضاعف ×1.2)\n"
        f"🥇 ذهبي: {gold_threshold} إحالة (مضاعف ×1.5)\n\n"
        f"شارك رابطك وابدأ الكسب! 🚀"
    )

    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "referral_link")
async def referral_link_callback(callback: CallbackQuery):
    link = get_referral_link(callback.from_user.id)
    await callback.answer(f"رابطك: {link}", show_alert=True)


# =============================================
# Statistics Handler
# =============================================

@router.message(F.text == "📊 إحصائياتي")
async def stats_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("يرجى استخدام /start أولاً")
        return

    from database import fetchval
    pending_wd = await fetchval(
        "SELECT COUNT(*) FROM withdrawals WHERE user_id = $1 AND status = 'pending'",
        message.from_user.id
    )
    approved_wd = await fetchval(
        "SELECT COUNT(*) FROM withdrawals WHERE user_id = $1 AND status = 'approved'",
        message.from_user.id
    )

    join_date = user.get('created_at')
    join_str = join_date.strftime('%Y-%m-%d') if join_date else 'غير معروف'
    last_activity = user.get('last_activity')
    last_str = last_activity.strftime('%Y-%m-%d %H:%M') if last_activity else 'غير معروف'

    rank = format_rank(user.get('rank', 'bronze'))
    text = (
        f"📊 **إحصائياتك**\n\n"
        f"🏆 الرتبة: {rank}\n"
        f"⚡ مضاعف الأرباح: **{float(user.get('rank_multiplier', 1.0))}×**\n\n"
        f"💰 الرصيد الحالي: **{format_balance(user.get('balance', 0))}**\n"
        f"📈 إجمالي الأرباح: {format_balance(user.get('total_earned', 0))}\n"
        f"💸 إجمالي السحوبات: {format_balance(user.get('total_withdrawn', 0))}\n\n"
        f"👥 عدد الإحالات: **{user.get('referral_count', 0)}**\n"
        f"💬 عدد الرسائل: {user.get('total_messages', 0)}\n"
        f"🔥 سلسلة اليومية: **{user.get('daily_streak', 0)} يوم**\n\n"
        f"⏳ سحوبات معلقة: {pending_wd}\n"
        f"✅ سحوبات مقبولة: {approved_wd}\n\n"
        f"📅 تاريخ الانضمام: {join_str}\n"
        f"⏰ آخر نشاط: {last_str}"
    )

    await message.answer(text, parse_mode="Markdown")


# =============================================
# Leaderboard Handler
# =============================================

@router.message(F.text == "🏆 المتصدرون")
async def leaderboard_handler(message: Message):
    top_users = await get_top_referrers(10)
    text = format_leaderboard(top_users)

    # Find current user's position
    from database import fetchval
    position = await fetchval("""
        SELECT position FROM (
            SELECT user_id, ROW_NUMBER() OVER (ORDER BY referral_count DESC) as position
            FROM users WHERE is_banned = FALSE
        ) ranked WHERE user_id = $1
    """, message.from_user.id)

    if position:
        text += f"\n\n📍 **موقعك: المركز #{position}**"

    await message.answer(text, parse_mode="Markdown", reply_markup=leaderboard_keyboard())


@router.callback_query(F.data == "leaderboard_refresh")
async def leaderboard_refresh(callback: CallbackQuery):
    top_users = await get_top_referrers(10)
    text = format_leaderboard(top_users)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=leaderboard_keyboard())
    await callback.answer("✅ تم التحديث")


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    from keyboards.keyboards import main_menu_keyboard
    await callback.message.delete()
    await callback.answer()
