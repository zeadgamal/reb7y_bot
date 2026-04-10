"""
Keyboards Module - All Telegram keyboards
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import config


# =============================================
# Main Menu
# =============================================

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💰 رصيدي"),
        KeyboardButton(text="🔗 رابط الدعوة")
    )
    builder.row(
        KeyboardButton(text="🎁 مكافأة يومية"),
        KeyboardButton(text="🎮 ألعاب")
    )
    builder.row(
        KeyboardButton(text="💸 سحب الأرباح"),
        KeyboardButton(text="📊 إحصائياتي")
    )
    builder.row(
        KeyboardButton(text="🏆 المتصدرون"),
        KeyboardButton(text="🎟️ كود ترويجي")
    )
    return builder.as_markup(resize_keyboard=True)


# =============================================
# Balance & Wallet
# =============================================

def balance_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📜 سجل المعاملات", callback_data="tx_history"),
        InlineKeyboardButton(text="💸 سحب", callback_data="withdraw_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 دعوة الأصدقاء", callback_data="referral_link")
    )
    return builder.as_markup()


# =============================================
# Withdrawal
# =============================================

def payment_methods_keyboard(methods: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for method in methods:
        builder.row(InlineKeyboardButton(
            text=method['name'],
            callback_data=f"pay_method:{method['id']}:{method['name']}"
        ))
    builder.row(InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel"))
    return builder.as_markup()


def withdrawal_confirm_keyboard(amount: float, method: str, account: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تأكيد السحب", callback_data="confirm_withdraw"),
        InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel")
    )
    return builder.as_markup()


# =============================================
# Admin Panel
# =============================================

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="admin:settings"),
        InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin:stats")
    )
    builder.row(
        InlineKeyboardButton(text="👥 المستخدمون", callback_data="admin:users"),
        InlineKeyboardButton(text="💸 السحوبات", callback_data="admin:withdrawals")
    )
    builder.row(
        InlineKeyboardButton(text="📢 بث رسالة", callback_data="admin:broadcast"),
        InlineKeyboardButton(text="📣 القنوات", callback_data="admin:channels")
    )
    builder.row(
        InlineKeyboardButton(text="🎟️ أكواد ترويجية", callback_data="admin:promos"),
        InlineKeyboardButton(text="📰 الإعلانات", callback_data="admin:ads")
    )
    builder.row(
        InlineKeyboardButton(text="🚩 المستخدمون المبلغ عنهم", callback_data="admin:flagged"),
        InlineKeyboardButton(text="💳 طرق الدفع", callback_data="admin:payment_methods")
    )
    builder.row(
        InlineKeyboardButton(text="🚀 تفعيل بوست", callback_data="admin:boost"),
        InlineKeyboardButton(text="📤 تصدير البيانات", callback_data="admin:export")
    )
    return builder.as_markup()


def admin_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    settings = [
        ("💰 مكافأة الإحالة", "admin:set:referral_reward"),
        ("📊 حد السحب الأول", "admin:set:first_withdraw_min"),
        ("📊 حد السحب التالي", "admin:set:next_withdraw_min"),
        ("🎁 المكافأة اليومية", "admin:set:daily_reward"),
        ("🥉 حد البرونزي", "admin:set:bronze_threshold"),
        ("🥈 حد الفضي", "admin:set:silver_threshold"),
        ("🥇 حد الذهبي", "admin:set:gold_threshold"),
        ("🔧 وضع الصيانة", "admin:toggle:maintenance_mode"),
    ]
    for text, cb in settings:
        builder.row(InlineKeyboardButton(text=text, callback_data=cb))
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))
    return builder.as_markup()


def withdrawal_action_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ قبول", callback_data=f"wd:approve:{withdrawal_id}"),
        InlineKeyboardButton(text="❌ رفض", callback_data=f"wd:reject:{withdrawal_id}")
    )
    return builder.as_markup()


def admin_withdrawals_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏳ الطلبات المعلقة", callback_data="admin:wd:pending"),
        InlineKeyboardButton(text="✅ المقبولة", callback_data="admin:wd:approved"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ المرفوضة", callback_data="admin:wd:rejected"),
        InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel")
    )
    return builder.as_markup()


# =============================================
# Games
# =============================================

def games_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎰 عجلة الحظ", callback_data="game:spin"),
        InlineKeyboardButton(text="🔢 خمّن الرقم", callback_data="game:guess")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع للقائمة", callback_data="main_menu"))
    return builder.as_markup()


def spin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎰 الدوران!", callback_data="game:spin:do"))
    return builder.as_markup()


def guess_keyboard(options: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row = [InlineKeyboardButton(text=str(n), callback_data=f"game:guess:{n}") for n in options]
    builder.row(*row)
    return builder.as_markup()


# =============================================
# Subscription Check
# =============================================

def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        if ch.get('channel_link'):
            builder.row(InlineKeyboardButton(
                text=f"📢 {ch['channel_name']}",
                url=ch['channel_link']
            ))
    builder.row(InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data="check_subscription"))
    return builder.as_markup()


# =============================================
# Leaderboard
# =============================================

def leaderboard_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 تحديث", callback_data="leaderboard_refresh"))
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel"))
    return builder.as_markup()


def back_keyboard(callback: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data=callback))
    return builder.as_markup()


def ad_keyboard(ad: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if ad.get('ad_type') == 'link' and ad.get('link_url'):
        builder.row(InlineKeyboardButton(
            text=ad.get('button_text') or "🔗 اضغط هنا",
            url=ad['link_url']
        ))
    if ad.get('reward_for_view', 0) > 0:
        builder.row(InlineKeyboardButton(
            text="✅ حصلت على مكافأتي",
            callback_data=f"ad:claim:{ad['id']}"
        ))
    return builder.as_markup()
