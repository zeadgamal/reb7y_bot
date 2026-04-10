"""
Utilities
"""
import logging
from decimal import Decimal
from typing import List, Dict, Optional
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from services.promo_service import get_active_channels
from config import config

logger = logging.getLogger(__name__)

RANK_EMOJIS = {
    'bronze': '🥉 برونزي',
    'silver': '🥈 فضي',
    'gold': '🥇 ذهبي'
}

TX_TYPE_LABELS = {
    'referral_reward': '🔗 مكافأة إحالة',
    'daily_reward': '🎁 مكافأة يومية',
    'game_reward': '🎮 مكافأة لعبة',
    'withdrawal': '💸 سحب',
    'promo_code': '🎟️ كود ترويجي',
    'admin_add': '💰 إضافة من الإدارة',
    'admin_deduct': '➖ خصم من الإدارة',
    'refund': '↩️ استرداد',
    'ad_reward': '📰 مكافأة إعلان'
}


def format_balance(amount) -> str:
    return f"{float(amount):.2f} جنيه"


def format_rank(rank: str) -> str:
    return RANK_EMOJIS.get(rank, '🥉 برونزي')


def format_tx_type(tx_type: str) -> str:
    return TX_TYPE_LABELS.get(tx_type, tx_type)


async def check_user_subscriptions(bot: Bot, user_id: int) -> tuple[bool, List[Dict]]:
    """Returns (all_subscribed, unjoined_channels)."""
    channels = await get_active_channels()
    if not channels:
        return True, []

    unjoined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch['channel_id'], user_id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.BANNED):
                unjoined.append(ch)
        except Exception as e:
            logger.warning(f"Subscription check error for {ch['channel_id']}: {e}")
            unjoined.append(ch)

    return len(unjoined) == 0, unjoined


def get_referral_link(user_id: int) -> str:
    return f"https://t.me/{config.BOT_USERNAME}?start=ref_{user_id}"


def format_user_profile(user: Dict, referral_link: str) -> str:
    rank = format_rank(user.get('rank', 'bronze'))
    balance = format_balance(user.get('balance', 0))
    total_earned = format_balance(user.get('total_earned', 0))
    referrals = user.get('referral_count', 0)
    streak = user.get('daily_streak', 0)

    return (
        f"👤 **ملفك الشخصي**\n\n"
        f"🏷️ الاسم: {user.get('full_name', 'مستخدم')}\n"
        f"🆔 المعرف: `{user.get('user_id')}`\n"
        f"🏆 الرتبة: {rank}\n\n"
        f"💰 الرصيد الحالي: **{balance}**\n"
        f"📈 إجمالي الأرباح: {total_earned}\n"
        f"💸 إجمالي السحوبات: {format_balance(user.get('total_withdrawn', 0))}\n\n"
        f"👥 عدد الإحالات: **{referrals}** مستخدم\n"
        f"🔥 سلسلة اليومية: {streak} يوم\n\n"
        f"🔗 رابط الدعوة:\n`{referral_link}`"
    )


def format_leaderboard(users: List[Dict]) -> str:
    medals = ['🥇', '🥈', '🥉']
    lines = ["🏆 **لوحة المتصدرين - أكثر الإحالات**\n"]
    for i, u in enumerate(users):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = u.get('username') and f"@{u['username']}" or u.get('full_name', 'مجهول')
        lines.append(f"{medal} {name} — **{u['referral_count']}** إحالة")
    return "\n".join(lines)


def format_withdrawal_request(wd: Dict, user: Dict) -> str:
    return (
        f"💸 **طلب سحب جديد**\n\n"
        f"🔖 رقم الطلب: `{wd['order_id']}`\n"
        f"👤 المستخدم: {user.get('full_name')} (@{user.get('username', 'N/A')})\n"
        f"🆔 ID: `{wd['user_id']}`\n"
        f"💰 المبلغ: **{format_balance(wd['amount'])}**\n"
        f"💳 طريقة الدفع: {wd['payment_method']}\n"
        f"📋 تفاصيل الحساب: `{wd['account_details']}`\n"
        f"🕒 التاريخ: {wd['created_at'].strftime('%Y-%m-%d %H:%M')}"
    )


def format_transaction_history(transactions: List[Dict]) -> str:
    if not transactions:
        return "📭 لا توجد معاملات بعد."
    lines = ["📜 **آخر المعاملات:**\n"]
    for tx in transactions:
        amount = float(tx['amount'])
        sign = "+" if amount > 0 else ""
        date = tx['created_at'].strftime('%m/%d %H:%M')
        tx_type = format_tx_type(tx['type'])
        lines.append(f"• {tx_type}: **{sign}{amount:.2f} جنيه** — {date}")
    return "\n".join(lines)


def format_stats(stats: Dict) -> str:
    return (
        f"📊 **إحصائيات البوت**\n\n"
        f"👥 إجمالي المستخدمين: **{stats['total_users']:,}**\n"
        f"🟢 المستخدمون النشطون (7 أيام): **{stats['active_users']:,}**\n"
        f"⛔ المحظورون: **{stats['banned_users']:,}**\n\n"
        f"💰 إجمالي الأرباح الموزعة: **{float(stats['total_earned']):.2f} جنيه**\n"
        f"💸 إجمالي السحوبات: **{float(stats['total_withdrawn']):.2f} جنيه**\n"
        f"⏳ سحوبات معلقة: **{stats['pending_withdrawals']}**\n"
        f"🔗 إجمالي الإحالات: **{stats['total_referrals']:,}**"
    )
