"""
Games Handler - Spin Wheel & Guess Number
"""
import random
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.user_service import get_user, add_balance
from services.settings_service import get_all_settings, is_ads_enabled
from keyboards.keyboards import games_keyboard, spin_keyboard, guess_keyboard, back_keyboard
from utils.utils import format_balance

logger = logging.getLogger(__name__)
router = Router()


class GuessState(StatesGroup):
    waiting_guess = State()


SPIN_SLOTS = [
    ("💀 خسرت!", 0, 0.20),
    ("😢 لا شيء", 0, 0.20),
    ("🌟 0.50 جنيه", 0.50, 0.20),
    ("💰 1.00 جنيه", 1.00, 0.15),
    ("🎯 2.00 جنيه", 2.00, 0.12),
    ("🔥 3.00 جنيه", 3.00, 0.07),
    ("💎 5.00 جنيه", 5.00, 0.05),
    ("🚀 10.00 جنيه", 10.00, 0.01),
]


def weighted_spin() -> tuple[str, float]:
    labels = [s[0] for s in SPIN_SLOTS]
    rewards = [s[1] for s in SPIN_SLOTS]
    weights = [s[2] for s in SPIN_SLOTS]
    idx = random.choices(range(len(SPIN_SLOTS)), weights=weights, k=1)[0]
    return labels[idx], rewards[idx]


@router.message(F.text == "🎮 ألعاب")
async def games_menu_handler(message: Message):
    settings = await get_all_settings()
    spin_cooldown = int(settings.get('spin_cooldown_hours', 24))
    spin_max = float(settings.get('spin_max_reward', 5.00))

    text = (
        f"🎮 **ألعاب Reb7y**\n\n"
        f"🎰 **عجلة الحظ**\n"
        f"   جرب حظك وربح حتى {format_balance(spin_max)}\n"
        f"   مرة كل {spin_cooldown} ساعة\n\n"
        f"🔢 **خمّن الرقم**\n"
        f"   خمّن الرقم الصحيح وربح!\n"
        f"   مرة كل 24 ساعة\n\n"
        f"اختر لعبة:"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=games_keyboard())


# =============================================
# Spin Wheel
# =============================================

@router.callback_query(F.data == "game:spin")
async def spin_menu(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    settings = await get_all_settings()
    cooldown_hours = int(settings.get('spin_cooldown_hours', 24))
    last_spin = user.get('last_spin')

    if last_spin:
        next_spin = last_spin + timedelta(hours=cooldown_hours)
        if datetime.now() < next_spin:
            remaining = next_spin - datetime.now()
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            await callback.answer(
                f"⏳ العجلة متاحة بعد {h} ساعة و {m} دقيقة",
                show_alert=True
            )
            return

    await callback.message.edit_text(
        "🎰 **عجلة الحظ**\n\n"
        "اضغط الزر للدوران!\n\n"
        "🌟 0.50 | 💰 1.00 | 🎯 2.00\n"
        "🔥 3.00 | 💎 5.00 | 🚀 10.00",
        parse_mode="Markdown",
        reply_markup=spin_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "game:spin:do")
async def do_spin(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    settings = await get_all_settings()
    cooldown_hours = int(settings.get('spin_cooldown_hours', 24))
    last_spin = user.get('last_spin')

    if last_spin:
        next_spin = last_spin + timedelta(hours=cooldown_hours)
        if datetime.now() < next_spin:
            await callback.answer("⏳ ليس وقت الدوران بعد!", show_alert=True)
            return

    label, reward = weighted_spin()

    # Apply multiplier & boost
    multiplier = Decimal(str(user.get('rank_multiplier', 1.0)))
    boost = settings.get('boost_active', 'false').lower() == 'true'
    boost_mult = Decimal(settings.get('boost_multiplier', '2.0'))

    final_reward = Decimal(str(reward)) * multiplier
    if boost:
        final_reward *= boost_mult

    # Update last spin
    from database import execute
    await execute("UPDATE users SET last_spin = NOW() WHERE user_id = $1", callback.from_user.id)

    if final_reward > 0:
        await add_balance(
            callback.from_user.id, final_reward,
            'game_reward', f'عجلة الحظ: {label}'
        )
        result_text = (
            f"🎰 **نتيجة العجلة**\n\n"
            f"{'🎊' * 5}\n"
            f"**{label}**\n"
            f"💰 ربحت: **{format_balance(final_reward)}**\n"
            f"{'🎊' * 5}\n\n"
            f"تمت إضافة المبلغ لرصيدك!"
        )
    else:
        result_text = (
            f"🎰 **نتيجة العجلة**\n\n"
            f"😢 **{label}**\n\n"
            f"حظاً أوفر في المرة القادمة!"
        )

    await callback.message.edit_text(
        result_text, parse_mode="Markdown",
        reply_markup=back_keyboard("game:spin")
    )
    await callback.answer()

    # Show ad after game
    if await is_ads_enabled():
        from handlers.daily import show_ad
        await show_ad(callback.message, 'after_game')


# =============================================
# Guess Number
# =============================================

@router.callback_query(F.data == "game:guess")
async def guess_menu(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    last_guess = user.get('last_guess')

    if last_guess:
        next_guess = last_guess + timedelta(hours=24)
        if datetime.now() < next_guess:
            remaining = next_guess - datetime.now()
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            await callback.answer(
                f"⏳ اللعبة متاحة بعد {h} ساعة و {m} دقيقة",
                show_alert=True
            )
            return

    settings = await get_all_settings()
    max_attempts = int(settings.get('guess_max_attempts', 3))
    secret = random.randint(1, 10)

    await state.set_state(GuessState.waiting_guess)
    await state.update_data(secret=secret, attempts=0, max_attempts=max_attempts)

    numbers = list(range(1, 11))
    await callback.message.edit_text(
        f"🔢 **خمّن الرقم**\n\n"
        f"خمّن رقماً بين 1 و 10\n"
        f"لديك **{max_attempts}** محاولات!\n\n"
        f"اختر رقماً:",
        parse_mode="Markdown",
        reply_markup=guess_keyboard(numbers)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("game:guess:"), GuessState.waiting_guess)
async def handle_guess(callback: CallbackQuery, state: FSMContext):
    guess = int(callback.data.split(":")[2])
    data = await state.get_data()
    secret = data['secret']
    attempts = data['attempts'] + 1
    max_attempts = data['max_attempts']

    settings = await get_all_settings()
    reward_amount = float(settings.get('guess_reward', 1.00))
    user = await get_user(callback.from_user.id)
    multiplier = float(user.get('rank_multiplier', 1.0))

    if guess == secret:
        final_reward = Decimal(str(reward_amount * multiplier))
        boost = settings.get('boost_active', 'false').lower() == 'true'
        if boost:
            final_reward *= Decimal(settings.get('boost_multiplier', '2.0'))

        await add_balance(callback.from_user.id, final_reward, 'game_reward', 'لعبة التخمين')
        from database import execute
        await execute("UPDATE users SET last_guess = NOW() WHERE user_id = $1", callback.from_user.id)
        await state.clear()

        await callback.message.edit_text(
            f"🎉 **صحيح!**\n\n"
            f"الرقم كان **{secret}**\n"
            f"💰 ربحت: **{format_balance(final_reward)}**\n\n"
            f"تمت إضافة المبلغ لرصيدك!",
            parse_mode="Markdown",
            reply_markup=back_keyboard("game:guess")
        )
    elif attempts >= max_attempts:
        from database import execute
        await execute("UPDATE users SET last_guess = NOW() WHERE user_id = $1", callback.from_user.id)
        await state.clear()
        await callback.message.edit_text(
            f"😢 **انتهت المحاولات!**\n\n"
            f"الرقم الصحيح كان **{secret}**\n\n"
            f"حظاً أوفر في المرة القادمة!",
            parse_mode="Markdown",
            reply_markup=back_keyboard("game:guess")
        )
    else:
        remaining = max_attempts - attempts
        hint = "⬆️ أكبر" if guess < secret else "⬇️ أصغر"
        await state.update_data(attempts=attempts)

        numbers = list(range(1, 11))
        await callback.message.edit_text(
            f"🔢 **خمّن الرقم**\n\n"
            f"تخمينك: **{guess}** — {hint}\n"
            f"محاولات متبقية: **{remaining}**\n\n"
            f"حاول مجدداً:",
            parse_mode="Markdown",
            reply_markup=guess_keyboard(numbers)
        )

    await callback.answer()
