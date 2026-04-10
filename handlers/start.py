"""
Start Handler - Registration, Referral, CAPTCHA
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

from services.user_service import get_user, create_user, update_user
from services.settings_service import get_all_settings, get_referral_reward
from services.security_service import (
    generate_math_captcha, verify_captcha,
    detect_suspicious_referral, log_activity
)
from services.user_service import add_balance, update_rank
from database import execute, fetchval
from keyboards.keyboards import main_menu_keyboard, subscription_keyboard, cancel_keyboard
from utils.utils import check_user_subscriptions, get_referral_link, format_rank
from config import config
from decimal import Decimal

logger = logging.getLogger(__name__)
router = Router()


async def send_captcha(message: Message, state: FSMContext):
    question, _ = await generate_math_captcha(message.from_user.id)
    await state.set_state("waiting_captcha")
    await message.answer(
        f"🔐 **التحقق من الهوية**\n\n"
        f"لحماية البوت من الحسابات الوهمية، يرجى حل هذه العملية الحسابية:\n\n"
        f"📝 **{question}**\n\n"
        f"أرسل الإجابة كرقم فقط.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    # Parse referral argument
    referred_by = None
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.split("ref_")[1])
            if referrer_id != user_id:
                referrer = await get_user(referrer_id)
                if referrer:
                    referred_by = referrer_id
        except (ValueError, IndexError):
            pass

    # Get or create user
    existing = await get_user(user_id)
    is_new = existing is None

    user = await create_user(user_id, username, full_name, referred_by if is_new else None)

    await log_activity(user_id, 'start', {'is_new': is_new, 'referred_by': referred_by})

    # Check forced subscriptions
    from aiogram import Bot
    bot: Bot = message.bot
    subscribed, unjoined = await check_user_subscriptions(bot, user_id)

    if not subscribed:
        await message.answer(
            "📢 **يجب الاشتراك في القنوات التالية أولاً:**\n\n"
            "اشترك في جميع القنوات ثم اضغط على زر التحقق.",
            parse_mode="Markdown",
            reply_markup=subscription_keyboard(unjoined)
        )
        return

    # New user needs CAPTCHA
    if is_new and not user.get('captcha_verified'):
        await state.update_data(referred_by=referred_by)
        await send_captcha(message, state)
        return

    # Existing user not verified
    if not user.get('captcha_verified'):
        await state.update_data(referred_by=referred_by)
        await send_captcha(message, state)
        return

    await send_welcome(message, user, is_new)


async def send_welcome(message: Message, user: dict, is_new: bool):
    rank = format_rank(user.get('rank', 'bronze'))
    referral_link = get_referral_link(user['user_id'])

    if is_new:
        text = (
            f"🎉 **أهلاً بك في Reb7y Bot!**\n\n"
            f"💸 اربح المال عن طريق دعوة أصدقائك!\n"
            f"كل ما عليك هو مشاركة رابط الدعوة الخاص بك.\n\n"
            f"🔗 رابط دعوتك:\n`{referral_link}`\n\n"
            f"🏆 رتبتك الحالية: {rank}\n"
            f"💰 رصيدك: **0.00 جنيه**\n\n"
            f"استخدم القائمة أدناه للبدء 👇"
        )
    else:
        text = (
            f"👋 **أهلاً بعودتك، {user.get('full_name', 'صديقي')}!**\n\n"
            f"🏆 رتبتك: {rank}\n"
            f"💰 رصيدك: **{float(user.get('balance', 0)):.2f} جنيه**\n"
            f"👥 إحالاتك: **{user.get('referral_count', 0)}** مستخدم\n\n"
            f"استخدم القائمة أدناه 👇"
        )

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


@router.message(F.text, lambda msg, state: state is not None)
async def handle_captcha_answer(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != "waiting_captcha":
        return

    answer = message.text.strip()
    user_id = message.from_user.id

    correct = await verify_captcha(user_id, answer)

    if correct:
        data = await state.get_data()
        referred_by = data.get('referred_by')
        await state.clear()

        # Process referral reward if new user
        if referred_by:
            is_suspicious, reason = await detect_suspicious_referral(referred_by, user_id)
            if not is_suspicious:
                reward = await get_referral_reward()
                settings = await get_all_settings()

                # Get referrer's multiplier
                from database import fetchval as db_fetchval
                multiplier = await db_fetchval(
                    "SELECT rank_multiplier FROM users WHERE user_id = $1", referred_by
                ) or 1.0

                final_reward = Decimal(str(reward)) * Decimal(str(multiplier))

                # Insert referral record
                await execute("""
                    INSERT INTO referrals (referrer_id, referred_id, reward_amount, reward_paid)
                    VALUES ($1, $2, $3, TRUE)
                    ON CONFLICT (referred_id) DO NOTHING
                """, referred_by, user_id, final_reward)

                # Update referrer
                await execute("""
                    UPDATE users SET referral_count = referral_count + 1 WHERE user_id = $1
                """, referred_by)

                # Add reward to referrer
                await add_balance(
                    referred_by, final_reward, 'referral_reward',
                    f'مكافأة دعوة مستخدم جديد: {message.from_user.full_name}',
                    str(user_id)
                )

                # Update rank
                new_referral_count = await fetchval(
                    "SELECT referral_count FROM users WHERE user_id = $1", referred_by
                )
                new_rank = await update_rank(referred_by, new_referral_count, settings)

                # Notify referrer
                try:
                    notif_text = (
                        f"🎉 **مبروك! إحالة جديدة!**\n\n"
                        f"👤 انضم {message.from_user.full_name} عبر رابطك!\n"
                        f"💰 حصلت على: **{float(final_reward):.2f} جنيه**"
                    )
                    if new_rank:
                        rank_label = format_rank(new_rank)
                        notif_text += f"\n🏆 ترقيت إلى رتبة: **{rank_label}**!"

                    await message.bot.send_message(referred_by, notif_text, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Could not notify referrer {referred_by}: {e}")

        user = await get_user(user_id)
        await message.answer("✅ **تم التحقق بنجاح!**", parse_mode="Markdown")
        await send_welcome(message, user, True)
    else:
        user = await get_user(user_id)
        attempts = user.get('captcha_attempts', 0)
        remaining = 5 - attempts

        if remaining <= 0:
            await state.clear()
            await message.answer(
                "⛔️ تجاوزت عدد المحاولات المسموحة. يرجى إعادة تشغيل البوت.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"❌ إجابة خاطئة! المحاولات المتبقية: **{remaining}**\n"
                f"حاول مرة أخرى.",
                parse_mode="Markdown"
            )


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    bot = callback.bot
    user_id = callback.from_user.id

    subscribed, unjoined = await check_user_subscriptions(bot, user_id)

    if not subscribed:
        await callback.answer("❌ لم تشترك في جميع القنوات بعد!", show_alert=True)
        return

    user = await get_user(user_id)
    if not user:
        await callback.message.delete()
        await callback.message.answer("/start")
        return

    if not user.get('captcha_verified'):
        await callback.message.delete()
        await send_captcha(callback.message, state)
        return

    await callback.message.delete()
    await send_welcome(callback.message, user, False)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("تم الإلغاء")
