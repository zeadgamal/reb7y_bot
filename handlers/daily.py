"""
Daily Reward & Promo Code Handlers
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.user_service import get_user, add_balance, update_user
from services.settings_service import get_daily_reward, get_all_settings, is_ads_enabled
from services.promo_service import redeem_promo_code, get_active_ads, record_ad_view
from keyboards.keyboards import back_keyboard, cancel_keyboard, ad_keyboard
from utils.utils import format_balance

logger = logging.getLogger(__name__)
router = Router()


class PromoState(StatesGroup):
    waiting_code = State()


# =============================================
# Daily Reward
# =============================================

@router.message(F.text == "🎁 مكافأة يومية")
async def daily_reward_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("يرجى استخدام /start أولاً")
        return

    now = datetime.now()
    last_claim = user.get('last_daily_claim')
    next_claim_time = None

    if last_claim:
        next_claim_time = last_claim + timedelta(hours=24)
        if now < next_claim_time:
            remaining = next_claim_time - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            await message.answer(
                f"⏳ **لقد حصلت على مكافأتك اليوم!**\n\n"
                f"🕒 الوقت المتبقي: **{hours} ساعة و {minutes} دقيقة**\n\n"
                f"عد لاحقاً للحصول على مكافأتك التالية 🔥",
                parse_mode="Markdown"
            )
            return

    # Calculate reward with streak
    base_reward = await get_daily_reward()
    settings = await get_all_settings()
    streak_bonus = float(settings.get('daily_reward_streak_bonus', 0.5))
    current_streak = user.get('daily_streak', 0)

    # Check if streak continues
    if last_claim and now < last_claim + timedelta(hours=48):
        new_streak = current_streak + 1
    else:
        new_streak = 1

    # Apply streak bonus
    streak_addition = streak_bonus * (new_streak - 1)
    total_reward = Decimal(str(base_reward + streak_addition))

    # Apply rank multiplier
    multiplier = Decimal(str(user.get('rank_multiplier', 1.0)))
    final_reward = total_reward * multiplier

    # Check boost
    boost = settings.get('boost_active', 'false').lower() == 'true'
    if boost:
        boost_mult = Decimal(settings.get('boost_multiplier', '2.0'))
        final_reward = final_reward * boost_mult

    # Add balance
    await add_balance(
        message.from_user.id, final_reward, 'daily_reward',
        f'مكافأة يومية - اليوم {new_streak}'
    )
    await update_user(message.from_user.id, last_daily_claim=now, daily_streak=new_streak)

    streak_emoji = "🔥" if new_streak >= 7 else "✨"
    boost_text = f"\n🚀 **بوست نشط!** تم مضاعفة المكافأة!" if boost else ""

    await message.answer(
        f"🎁 **تم استلام مكافأتك اليومية!**\n\n"
        f"💰 المكافأة: **{format_balance(final_reward)}**\n"
        f"{streak_emoji} سلسلة متواصلة: **{new_streak} يوم**\n"
        f"{'🔥 احتفظ بسلسلتك! عد غداً!' if new_streak > 1 else '💡 عد غداً لزيادة مكافأتك!'}"
        f"{boost_text}",
        parse_mode="Markdown"
    )

    # Show ad after daily claim
    if await is_ads_enabled():
        await show_ad(message, 'after_daily')


async def show_ad(message: Message, trigger: str):
    ads = await get_active_ads(trigger)
    if not ads:
        return
    ad = ads[0]
    is_first_view = await record_ad_view(ad['id'], message.from_user.id)

    reward_text = ""
    if is_first_view and float(ad.get('reward_for_view', 0)) > 0:
        reward_text = f"\n\n🎁 شاهد الإعلان واحصل على **{format_balance(ad['reward_for_view'])}**!"

    text = f"📢 **إعلان**\n\n{ad['content']}{reward_text}"
    kb = ad_keyboard(ad)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("ad:claim:"))
async def ad_claim_callback(callback: CallbackQuery):
    ad_id = int(callback.data.split(":")[2])
    from database import fetchrow
    ad = await fetchrow("SELECT * FROM ads WHERE id = $1", ad_id)
    if not ad:
        await callback.answer("الإعلان غير موجود", show_alert=True)
        return

    reward = Decimal(str(ad['reward_for_view']))
    if reward <= 0:
        await callback.answer("لا توجد مكافأة لهذا الإعلان", show_alert=True)
        return

    # Check if already claimed today
    from database import fetchval
    already = await fetchval("""
        SELECT COUNT(*) FROM ad_views
        WHERE ad_id = $1 AND user_id = $2 AND viewed_at > NOW() - INTERVAL '24 hours'
    """, ad_id, callback.from_user.id)

    if already > 1:
        await callback.answer("لقد حصلت على مكافأة هذا الإعلان اليوم مسبقاً", show_alert=True)
        return

    await add_balance(callback.from_user.id, reward, 'ad_reward', f'مكافأة مشاهدة إعلان #{ad_id}')
    await callback.answer(f"✅ حصلت على {format_balance(reward)}!", show_alert=True)
    await callback.message.delete()


# =============================================
# Promo Codes
# =============================================

@router.message(F.text == "🎟️ كود ترويجي")
async def promo_menu_handler(message: Message, state: FSMContext):
    await state.set_state(PromoState.waiting_code)
    await message.answer(
        "🎟️ **الأكواد الترويجية**\n\n"
        "أرسل الكود الترويجي للحصول على مكافأتك:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )


@router.message(PromoState.waiting_code)
async def handle_promo_code(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    success, msg, reward = await redeem_promo_code(code, user_id)

    if success and reward:
        await add_balance(user_id, reward, 'promo_code', f'كود ترويجي: {code}')
        await state.clear()
        await message.answer(
            f"✅ **تم استرداد الكود بنجاح!**\n\n"
            f"🎟️ الكود: `{code}`\n"
            f"💰 المكافأة: **{format_balance(reward)}**\n\n"
            f"تمت إضافة المبلغ لرصيدك!",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"❌ **خطأ في الكود**\n\n{msg}",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
