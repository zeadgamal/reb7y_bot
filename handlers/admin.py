"""
Admin Panel Handler - Full control
"""
import csv
import io
import logging
from decimal import Decimal
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.user_service import (
    get_user, get_all_users, get_user_count, get_total_stats,
    ban_user, unban_user, add_balance, get_flagged_users
)
from services.settings_service import get_all_settings, set_setting, invalidate_cache
from services.withdrawal_service import (
    get_pending_withdrawals, approve_withdrawal,
    reject_withdrawal, get_withdrawal_by_id
)
from services.promo_service import (
    create_promo_code, get_all_promo_codes, deactivate_promo_code,
    add_channel, remove_channel, get_all_channels,
    create_ad, get_all_ads
)
from keyboards.keyboards import (
    admin_panel_keyboard, admin_settings_keyboard,
    withdrawal_action_keyboard, admin_withdrawals_keyboard,
    back_keyboard
)
from utils.utils import format_balance, format_stats, format_withdrawal_request
from config import config
from database import execute, fetchrow

logger = logging.getLogger(__name__)
router = Router()

# Admin-only filter
def is_admin(message_or_callback):
    user_id = (
        message_or_callback.from_user.id
        if hasattr(message_or_callback, 'from_user')
        else None
    )
    return user_id == config.ADMIN_ID


class AdminState(StatesGroup):
    # Settings
    setting_key = State()
    setting_value = State()
    # Broadcast
    broadcast_msg = State()
    # Channel management
    add_channel_id = State()
    add_channel_name = State()
    add_channel_link = State()
    remove_channel_id = State()
    # Promo codes
    promo_code = State()
    promo_reward = State()
    promo_limit = State()
    promo_per_user = State()
    promo_expiry = State()
    # User management
    ban_user_id = State()
    ban_reason = State()
    ban_duration = State()
    add_balance_uid = State()
    add_balance_amount = State()
    # Withdrawal reject
    reject_reason = State()
    # Boost
    boost_duration = State()
    # Ad creation
    ad_title = State()
    ad_content = State()
    ad_type = State()
    ad_link = State()
    ad_reward = State()
    ad_trigger = State()
    # Payment method
    pm_name = State()
    pm_description = State()
    pm_placeholder = State()


# =============================================
# Admin Panel Entry
# =============================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message):
        return
    await message.answer(
        "🛠️ **لوحة تحكم المشرف**\n\nمرحباً @MN_BF 👋",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )


@router.callback_query(F.data == "admin:panel")
async def admin_panel_cb(callback: CallbackQuery):
    if not is_admin(callback):
        await callback.answer("⛔ غير مصرح", show_alert=True)
        return
    await callback.message.edit_text(
        "🛠️ **لوحة تحكم المشرف**",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )
    await callback.answer()


# =============================================
# Statistics
# =============================================

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback):
        return
    stats = await get_total_stats()
    text = format_stats(stats)
    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=back_keyboard("admin:panel")
    )
    await callback.answer()


# =============================================
# Settings
# =============================================

@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback):
        return
    settings = await get_all_settings()
    text = (
        f"⚙️ **الإعدادات الحالية**\n\n"
        f"💰 مكافأة الإحالة: **{settings.get('referral_reward')} جنيه**\n"
        f"📊 حد السحب الأول: **{settings.get('first_withdraw_min')} جنيه**\n"
        f"📊 حد السحب التالي: **{settings.get('next_withdraw_min')} جنيه**\n"
        f"🎁 مكافأة يومية: **{settings.get('daily_reward')} جنيه**\n"
        f"🥉 حد برونزي: **{settings.get('bronze_threshold')} إحالة**\n"
        f"🥈 حد فضي: **{settings.get('silver_threshold')} إحالة**\n"
        f"🥇 حد ذهبي: **{settings.get('gold_threshold')} إحالة**\n"
        f"🔧 وضع الصيانة: **{'مفعّل' if settings.get('maintenance_mode') == 'true' else 'معطّل'}**\n"
        f"📰 الإعلانات: **{'مفعّلة' if settings.get('ads_enabled') == 'true' else 'معطّلة'}**"
    )
    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=admin_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set:"))
async def admin_set_setting(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    key = callback.data.replace("admin:set:", "")
    labels = {
        'referral_reward': 'مكافأة الإحالة (جنيه)',
        'first_withdraw_min': 'الحد الأدنى للسحب الأول',
        'next_withdraw_min': 'الحد الأدنى للسحوبات التالية',
        'daily_reward': 'المكافأة اليومية',
        'bronze_threshold': 'حد الرتبة البرونزية (عدد الإحالات)',
        'silver_threshold': 'حد الرتبة الفضية',
        'gold_threshold': 'حد الرتبة الذهبية',
    }
    await state.set_state(AdminState.setting_value)
    await state.update_data(setting_key=key)
    await callback.message.edit_text(
        f"⚙️ تعديل: **{labels.get(key, key)}**\n\nأدخل القيمة الجديدة:",
        parse_mode="Markdown",
        reply_markup=back_keyboard("admin:settings")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:toggle:"))
async def admin_toggle_setting(callback: CallbackQuery):
    if not is_admin(callback):
        return
    key = callback.data.replace("admin:toggle:", "")
    from services.settings_service import get_setting
    current = await get_setting(key, 'false')
    new_val = 'false' if current == 'true' else 'true'
    await set_setting(key, new_val)
    invalidate_cache()
    status = 'مفعّل ✅' if new_val == 'true' else 'معطّل ❌'
    await callback.answer(f"تم تغيير {key} إلى {status}", show_alert=True)
    await admin_settings(callback)


@router.message(AdminState.setting_value)
async def handle_setting_value(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    data = await state.get_data()
    key = data['setting_key']
    value = message.text.strip()

    try:
        float(value)
    except ValueError:
        await message.answer("❌ أدخل قيمة رقمية صحيحة")
        return

    await set_setting(key, value)
    invalidate_cache()
    await state.clear()
    await message.answer(
        f"✅ تم تحديث **{key}** إلى **{value}**",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )


# =============================================
# Users Management
# =============================================

@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback):
        return
    count = await get_user_count()
    from services.user_service import get_active_users_count
    active = await get_active_users_count(7)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 بحث عن مستخدم", callback_data="admin:user:search"),
        InlineKeyboardButton(text="⛔ حظر مستخدم", callback_data="admin:user:ban"),
    )
    builder.row(
        InlineKeyboardButton(text="✅ رفع الحظر", callback_data="admin:user:unban"),
        InlineKeyboardButton(text="💰 إضافة رصيد", callback_data="admin:user:addbal"),
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await callback.message.edit_text(
        f"👥 **إدارة المستخدمين**\n\n"
        f"📊 الإجمالي: **{count:,}** مستخدم\n"
        f"🟢 النشطون (7 أيام): **{active:,}**",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:user:ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.ban_user_id)
    await callback.message.edit_text(
        "⛔ أدخل معرف المستخدم (User ID) لحظره:",
        reply_markup=back_keyboard("admin:users")
    )
    await callback.answer()


@router.message(AdminState.ban_user_id)
async def handle_ban_user_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        uid = int(message.text.strip())
        await state.update_data(ban_uid=uid)
        await state.set_state(AdminState.ban_reason)
        await message.answer(f"أدخل سبب الحظر للمستخدم `{uid}`:", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ معرف غير صحيح")


@router.message(AdminState.ban_reason)
async def handle_ban_reason(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    data = await state.get_data()
    uid = data['ban_uid']
    reason = message.text.strip()
    await ban_user(uid, reason)
    await state.clear()
    await message.answer(f"✅ تم حظر المستخدم `{uid}`\nالسبب: {reason}", parse_mode="Markdown")
    try:
        await message.bot.send_message(uid, f"⛔ تم حظرك من استخدام البوت.\nالسبب: {reason}")
    except:
        pass


@router.callback_query(F.data == "admin:user:unban")
async def admin_unban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.ban_user_id)
    await state.update_data(action='unban')
    await callback.message.edit_text("✅ أدخل معرف المستخدم لرفع الحظر عنه:")
    await callback.answer()


@router.callback_query(F.data == "admin:user:addbal")
async def admin_addbal_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.add_balance_uid)
    await callback.message.edit_text("💰 أدخل معرف المستخدم لإضافة رصيد له:")
    await callback.answer()


@router.message(AdminState.add_balance_uid)
async def handle_addbal_uid(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        uid = int(message.text.strip())
        await state.update_data(addbal_uid=uid)
        await state.set_state(AdminState.add_balance_amount)
        await message.answer(f"أدخل المبلغ للإضافة لـ `{uid}`:", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ معرف غير صحيح")


@router.message(AdminState.add_balance_amount)
async def handle_addbal_amount(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        amount = Decimal(message.text.strip())
        data = await state.get_data()
        uid = data['addbal_uid']
        await add_balance(uid, amount, 'admin_add', 'إضافة يدوية من المشرف')
        await state.clear()
        await message.answer(f"✅ تمت إضافة {format_balance(amount)} للمستخدم `{uid}`", parse_mode="Markdown")
        try:
            await message.bot.send_message(
                uid,
                f"💰 تمت إضافة **{format_balance(amount)}** لرصيدك من قِبل الإدارة!",
                parse_mode="Markdown"
            )
        except:
            pass
    except:
        await message.answer("❌ مبلغ غير صحيح")


# =============================================
# Withdrawals Management
# =============================================

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if not is_admin(callback):
        return
    pending = await get_pending_withdrawals()
    count = len(pending)
    await callback.message.edit_text(
        f"💸 **إدارة السحوبات**\n\n⏳ طلبات معلقة: **{count}**",
        parse_mode="Markdown",
        reply_markup=admin_withdrawals_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:wd:pending")
async def admin_pending_withdrawals(callback: CallbackQuery):
    if not is_admin(callback):
        return
    pending = await get_pending_withdrawals()
    if not pending:
        await callback.answer("✅ لا توجد طلبات معلقة", show_alert=True)
        return

    for wd in pending[:5]:
        user = await get_user(wd['user_id'])
        text = format_withdrawal_request(wd, user)
        await callback.message.answer(
            text, parse_mode="Markdown",
            reply_markup=withdrawal_action_keyboard(wd['id'])
        )
    await callback.answer()


@router.callback_query(F.data.startswith("wd:approve:"))
async def approve_wd_callback(callback: CallbackQuery):
    if not is_admin(callback):
        return
    wd_id = int(callback.data.split(":")[2])
    wd = await get_withdrawal_by_id(wd_id)
    if not wd:
        await callback.answer("❌ الطلب غير موجود", show_alert=True)
        return

    success = await approve_withdrawal(wd_id, "تمت الموافقة من المشرف")
    if success:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(f"✅ تمت الموافقة على طلب `{wd['order_id']}`", parse_mode="Markdown")
        try:
            await callback.bot.send_message(
                wd['user_id'],
                f"✅ **تمت الموافقة على طلب السحب!**\n\n"
                f"🔖 رقم الطلب: `{wd['order_id']}`\n"
                f"💰 المبلغ: **{format_balance(wd['amount'])}**\n\n"
                f"سيصلك المبلغ قريباً 🎉",
                parse_mode="Markdown"
            )
        except:
            pass
    await callback.answer()


@router.callback_query(F.data.startswith("wd:reject:"))
async def reject_wd_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    wd_id = int(callback.data.split(":")[2])
    await state.set_state(AdminState.reject_reason)
    await state.update_data(reject_wd_id=wd_id)
    await callback.message.reply("❌ أدخل سبب الرفض:")
    await callback.answer()


@router.message(AdminState.reject_reason)
async def handle_reject_reason(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    data = await state.get_data()
    wd_id = data['reject_wd_id']
    reason = message.text.strip()
    wd = await get_withdrawal_by_id(wd_id)
    if not wd:
        await message.answer("❌ الطلب غير موجود")
        await state.clear()
        return

    success = await reject_withdrawal(wd_id, reason, wd['user_id'], wd['amount'])
    await state.clear()
    if success:
        await message.answer(f"✅ تم رفض الطلب `{wd['order_id']}` وتم استرداد المبلغ للمستخدم", parse_mode="Markdown")
        try:
            await message.bot.send_message(
                wd['user_id'],
                f"❌ **تم رفض طلب السحب**\n\n"
                f"🔖 رقم الطلب: `{wd['order_id']}`\n"
                f"💰 المبلغ: **{format_balance(wd['amount'])}** (تم الاسترداد)\n"
                f"📋 السبب: {reason}",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ فشل رفض الطلب")


# =============================================
# Broadcast
# =============================================

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.broadcast_msg)
    await callback.message.edit_text(
        "📢 **بث رسالة**\n\nأرسل الرسالة التي تريد بثها لجميع المستخدمين:",
        parse_mode="Markdown",
        reply_markup=back_keyboard("admin:panel")
    )
    await callback.answer()


@router.message(AdminState.broadcast_msg)
async def handle_broadcast(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    text = message.text or message.caption or ""
    await state.clear()

    users = await get_all_users()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 جاري الإرسال لـ {len(users)} مستخدم...")

    for user in users:
        try:
            await message.bot.send_message(user['user_id'], text, parse_mode="Markdown")
            sent += 1
        except:
            failed += 1

    await execute("""
        INSERT INTO broadcasts (message, sent_count, failed_count, sent_by)
        VALUES ($1, $2, $3, $4)
    """, text, sent, failed, message.from_user.id)

    await status_msg.edit_text(
        f"✅ **اكتمل البث**\n\n"
        f"📤 تم الإرسال: **{sent}**\n"
        f"❌ فشل: **{failed}**",
        parse_mode="Markdown"
    )


# =============================================
# Channels Management
# =============================================

@router.callback_query(F.data == "admin:channels")
async def admin_channels(callback: CallbackQuery):
    if not is_admin(callback):
        return
    channels = await get_all_channels()
    lines = ["📣 **القنوات المطلوبة للاشتراك:**\n"]
    for ch in channels:
        status = "✅" if ch['is_active'] else "❌"
        lines.append(f"{status} {ch['channel_name']} — `{ch['channel_id']}`")
    if not channels:
        lines.append("لا توجد قنوات مضافة")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ إضافة قناة", callback_data="admin:ch:add"),
        InlineKeyboardButton(text="➖ حذف قناة", callback_data="admin:ch:remove"),
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:ch:add")
async def admin_ch_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.add_channel_id)
    await callback.message.edit_text(
        "أدخل معرف القناة (مثال: @mychannel أو -1001234567890):\n\n"
        "⚠️ تأكد أن البوت مشرف في القناة أولاً"
    )
    await callback.answer()


@router.message(AdminState.add_channel_id)
async def handle_ch_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.update_data(ch_id=message.text.strip())
    await state.set_state(AdminState.add_channel_name)
    await message.answer("أدخل اسم القناة (للعرض):")


@router.message(AdminState.add_channel_name)
async def handle_ch_name(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.update_data(ch_name=message.text.strip())
    await state.set_state(AdminState.add_channel_link)
    await message.answer("أدخل رابط القناة (مثال: https://t.me/mychannel):")


@router.message(AdminState.add_channel_link)
async def handle_ch_link(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    data = await state.get_data()
    await add_channel(data['ch_id'], data['ch_name'], message.text.strip())
    await state.clear()
    await message.answer(f"✅ تمت إضافة قناة **{data['ch_name']}**", parse_mode="Markdown")


@router.callback_query(F.data == "admin:ch:remove")
async def admin_ch_remove(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.remove_channel_id)
    await callback.message.edit_text("أدخل معرف القناة لحذفها:")
    await callback.answer()


@router.message(AdminState.remove_channel_id)
async def handle_ch_remove(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    ch_id = message.text.strip()
    await remove_channel(ch_id)
    await state.clear()
    await message.answer(f"✅ تم حذف القناة `{ch_id}`", parse_mode="Markdown")


# =============================================
# Promo Codes
# =============================================

@router.callback_query(F.data == "admin:promos")
async def admin_promos(callback: CallbackQuery):
    if not is_admin(callback):
        return
    codes = await get_all_promo_codes()
    lines = ["🎟️ **الأكواد الترويجية:**\n"]
    for c in codes[:10]:
        status = "✅" if c['is_active'] else "❌"
        exp = c['expires_at'].strftime('%Y-%m-%d') if c['expires_at'] else "لا يوجد"
        lines.append(
            f"{status} `{c['code']}` — {format_balance(c['reward'])} — "
            f"مستخدم {c['used_count']}/{c['usage_limit'] or '∞'} — ينتهي: {exp}"
        )
    if not codes:
        lines.append("لا توجد أكواد")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ إنشاء كود", callback_data="admin:promo:create"))
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo:create")
async def admin_promo_create(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.promo_code)
    await callback.message.edit_text("أدخل الكود الترويجي (بالإنجليزية):")
    await callback.answer()


@router.message(AdminState.promo_code)
async def handle_promo_code_name(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.update_data(pcode=message.text.strip().upper())
    await state.set_state(AdminState.promo_reward)
    await message.answer("أدخل قيمة المكافأة (جنيه):")


@router.message(AdminState.promo_reward)
async def handle_promo_reward(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        reward = Decimal(message.text.strip())
        await state.update_data(preward=reward)
        await state.set_state(AdminState.promo_limit)
        await message.answer("أدخل الحد الأقصى للاستخدام الكلي (0 = غير محدود):")
    except:
        await message.answer("❌ أدخل رقماً صحيحاً")


@router.message(AdminState.promo_limit)
async def handle_promo_limit(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        limit = int(message.text.strip())
        await state.update_data(plimit=limit if limit > 0 else None)
        await state.set_state(AdminState.promo_per_user)
        await message.answer("أدخل الحد الأقصى للاستخدام لكل مستخدم (عادة 1):")
    except:
        await message.answer("❌ أدخل رقماً صحيحاً")


@router.message(AdminState.promo_per_user)
async def handle_promo_per_user(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        per_user = int(message.text.strip())
        await state.update_data(pper_user=per_user)
        await state.set_state(AdminState.promo_expiry)
        await message.answer(
            "أدخل تاريخ الانتهاء (مثال: 2025-12-31) أو أرسل 0 لعدم التحديد:"
        )
    except:
        await message.answer("❌ أدخل رقماً صحيحاً")


@router.message(AdminState.promo_expiry)
async def handle_promo_expiry(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    text = message.text.strip()
    expires_at = None
    if text != '0':
        try:
            expires_at = datetime.strptime(text, '%Y-%m-%d')
        except:
            await message.answer("❌ صيغة تاريخ غير صحيحة. استخدم: YYYY-MM-DD")
            return

    data = await state.get_data()
    await create_promo_code(
        data['pcode'], data['preward'], data['plimit'],
        data['pper_user'], expires_at, message.from_user.id
    )
    await state.clear()
    await message.answer(
        f"✅ تم إنشاء كود **{data['pcode']}**\n"
        f"💰 المكافأة: {format_balance(data['preward'])}\n"
        f"📊 الحد: {data['plimit'] or 'غير محدود'}\n"
        f"⏰ ينتهي: {expires_at.strftime('%Y-%m-%d') if expires_at else 'لا يوجد'}",
        parse_mode="Markdown"
    )


# =============================================
# Boost System
# =============================================

@router.callback_query(F.data == "admin:boost")
async def admin_boost(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    settings = await get_all_settings()
    is_active = settings.get('boost_active', 'false') == 'true'
    ends_at = settings.get('boost_ends_at')
    mult = settings.get('boost_multiplier', '2.0')

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.row(InlineKeyboardButton(text="⛔ إيقاف البوست", callback_data="admin:boost:stop"))
    else:
        builder.row(InlineKeyboardButton(text="🚀 تفعيل بوست ×2", callback_data="admin:boost:start"))
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    status_text = f"✅ نشط حتى {ends_at}" if is_active else "❌ غير نشط"
    await callback.message.edit_text(
        f"🚀 **نظام البوست**\n\n"
        f"الحالة: {status_text}\n"
        f"المضاعف: ×{mult}",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:boost:start")
async def admin_boost_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.boost_duration)
    await callback.message.edit_text("أدخل مدة البوست بالساعات:")
    await callback.answer()


@router.message(AdminState.boost_duration)
async def handle_boost_duration(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        hours = int(message.text.strip())
        from datetime import timedelta
        ends_at = (datetime.now() + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M')
        await set_setting('boost_active', 'true')
        await set_setting('boost_ends_at', ends_at)
        invalidate_cache()
        await state.clear()
        await message.answer(
            f"🚀 **تم تفعيل البوست!**\n\n"
            f"⏰ ينتهي في: {ends_at}\n"
            f"جميع المكافآت مضاعفة الآن! ×2",
            parse_mode="Markdown"
        )
        # Broadcast to all users
        users = await get_all_users()
        for u in users:
            try:
                await message.bot.send_message(
                    u['user_id'],
                    f"🚀 **بوست نشط الآن!**\n\n"
                    f"جميع مكافآتك مضاعفة لمدة {hours} ساعة!\n"
                    f"استغل الفرصة الآن! ⚡",
                    parse_mode="Markdown"
                )
            except:
                pass
    except:
        await message.answer("❌ أدخل رقماً صحيحاً")


@router.callback_query(F.data == "admin:boost:stop")
async def admin_boost_stop(callback: CallbackQuery):
    if not is_admin(callback):
        return
    await set_setting('boost_active', 'false')
    invalidate_cache()
    await callback.answer("✅ تم إيقاف البوست", show_alert=True)
    await admin_boost(callback)


# =============================================
# Flagged Users
# =============================================

@router.callback_query(F.data == "admin:flagged")
async def admin_flagged(callback: CallbackQuery):
    if not is_admin(callback):
        return
    flagged = await get_flagged_users()
    if not flagged:
        await callback.answer("✅ لا يوجد مستخدمون مبلغ عنهم", show_alert=True)
        return

    lines = ["🚩 **المستخدمون المبلغ عنهم:**\n"]
    for u in flagged[:10]:
        name = u.get('username') and f"@{u['username']}" or u.get('full_name')
        lines.append(
            f"• {name} (`{u['user_id']}`)\n"
            f"  📋 السبب: {u.get('flag_reason', 'غير محدد')}\n"
            f"  ⚠️ تحذيرات: {u.get('warning_count', 0)}"
        )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=back_keyboard("admin:panel")
    )
    await callback.answer()


# =============================================
# Export Data
# =============================================

@router.callback_query(F.data == "admin:export")
async def admin_export(callback: CallbackQuery):
    if not is_admin(callback):
        return
    await callback.answer("⏳ جاري تصدير البيانات...")

    users = await get_all_users()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'user_id', 'username', 'full_name', 'balance',
        'total_earned', 'total_withdrawn', 'referral_count',
        'rank', 'is_banned', 'join_date', 'last_activity'
    ])
    for u in users:
        writer.writerow([
            u['user_id'], u.get('username'), u.get('full_name'),
            float(u.get('balance', 0)), float(u.get('total_earned', 0)),
            float(u.get('total_withdrawn', 0)), u.get('referral_count', 0),
            u.get('rank'), u.get('is_banned'),
            u.get('created_at'), u.get('last_activity')
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📤 تصدير بيانات المستخدمين\n📊 إجمالي: {len(users)} مستخدم"
    )


# =============================================
# Ads Management
# =============================================

@router.callback_query(F.data == "admin:ads")
async def admin_ads(callback: CallbackQuery):
    if not is_admin(callback):
        return
    ads = await get_all_ads()
    lines = ["📰 **الإعلانات:**\n"]
    for ad in ads[:5]:
        status = "✅" if ad['is_active'] else "❌"
        lines.append(
            f"{status} #{ad['id']} — {ad['title']}\n"
            f"   👁 مشاهدات: {ad['view_count']} | نقرات: {ad['click_count']}"
        )
    if not ads:
        lines.append("لا توجد إعلانات")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ إنشاء إعلان", callback_data="admin:ad:create"))
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:ad:create")
async def admin_ad_create(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback):
        return
    await state.set_state(AdminState.ad_title)
    await callback.message.edit_text("أدخل عنوان الإعلان:")
    await callback.answer()


@router.message(AdminState.ad_title)
async def handle_ad_title(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.update_data(ad_title=message.text.strip())
    await state.set_state(AdminState.ad_content)
    await message.answer("أدخل محتوى الإعلان:")


@router.message(AdminState.ad_content)
async def handle_ad_content(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.update_data(ad_content=message.text.strip())
    await state.set_state(AdminState.ad_link)
    await message.answer("أدخل رابط الإعلان (أو أرسل 0 لتخطي):")


@router.message(AdminState.ad_link)
async def handle_ad_link(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    link = message.text.strip()
    await state.update_data(ad_link=None if link == '0' else link)
    await state.set_state(AdminState.ad_reward)
    await message.answer("أدخل مكافأة المشاهدة (أو 0 لعدم المكافأة):")


@router.message(AdminState.ad_reward)
async def handle_ad_reward(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        reward = Decimal(message.text.strip())
        await state.update_data(ad_reward=reward)
        await state.set_state(AdminState.ad_trigger)
        await message.answer(
            "متى يظهر الإعلان؟\n"
            "1 - بعد المكافأة اليومية (after_daily)\n"
            "2 - بعد الألعاب (after_game)\n"
            "3 - القائمة الرئيسية (main_menu)\n"
            "أرسل الرقم:"
        )
    except:
        await message.answer("❌ أدخل رقماً صحيحاً")


@router.message(AdminState.ad_trigger)
async def handle_ad_trigger(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    triggers = {'1': 'after_daily', '2': 'after_game', '3': 'main_menu'}
    trigger = triggers.get(message.text.strip(), 'after_daily')
    data = await state.get_data()
    await create_ad(
        data['ad_title'], data['ad_content'],
        'link' if data.get('ad_link') else 'text',
        data.get('ad_link'), "اضغط هنا",
        data['ad_reward'], trigger
    )
    await state.clear()
    await message.answer(f"✅ تم إنشاء الإعلان: **{data['ad_title']}**", parse_mode="Markdown")
