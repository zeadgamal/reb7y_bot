#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت ربحي - نظام ربح متكامل مع مهمات التطبيقات
جميع الأسعار بالجنيه المصري
"""

import random
import re
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== الإعدادات والتكوين ====================
class Config:
    """كل إعدادات البوت في مكان واحد"""
    BOT_TOKEN = "8610034437:AAG2b40vkDvhnnw4mJm_5WkDFitNZUZx91w"
    ADMIN_IDS = [7512702966]
    BOT_USERNAME = "Reb7y_Bot"
    
    REFERRAL_BONUS_EGP = 5
    FIRST_WITHDRAWAL_EGP = 1
    SECOND_WITHDRAWAL_EGP = 100
    DAILY_BONUS_EGP = 1
    
    MIN_WHEEL_REWARD = 1
    MAX_WHEEL_REWARD = 3
    MIN_GAME_REWARD = 1
    MAX_GAME_REWARD = 3
    
    USD_TO_EGP = 52.0
    
    LANGUAGE = "ar"
    
    FORCE_SUB_ENABLED = True
    
    CANCEL_WITHDRAWAL_MINUTES = 1


# ==================== دوال مساعدة للعملات ====================

class CurrencyHelper:
    """تحويل العملات"""
    
    @staticmethod
    def egp_to_usd(egp_amount: float) -> float:
        return egp_amount / Config.USD_TO_EGP
    
    @staticmethod
    def usd_to_egp(usd_amount: float) -> float:
        return usd_amount * Config.USD_TO_EGP
    
    @staticmethod
    def format_amount(egp_amount: float, user_currency: str = "EGP") -> str:
        if user_currency == "USD":
            usd_amount = CurrencyHelper.egp_to_usd(egp_amount)
            return f"${usd_amount:.2f}"
        return f"{egp_amount:.2f} جنيه"
    
    @staticmethod
    def format_amount_admin(egp_amount: float) -> str:
        return f"{egp_amount:.2f} جنيه"


currency = CurrencyHelper()

# ==================== تهيئة قاعدة البيانات ====================

db = Database("Reb7y.db")

def load_config_from_db():
    """تحميل الإعدادات من قاعدة البيانات"""
    settings = db.get_all_settings()
    
    Config.REFERRAL_BONUS_EGP = float(settings.get('referral_bonus_egp', 5))
    Config.FIRST_WITHDRAWAL_EGP = float(settings.get('first_withdrawal_egp', 1))
    Config.SECOND_WITHDRAWAL_EGP = float(settings.get('second_withdrawal_egp', 100))
    Config.DAILY_BONUS_EGP = float(settings.get('daily_bonus_egp', 1))
    Config.MIN_WHEEL_REWARD = int(settings.get('min_wheel_reward', 1))
    Config.MAX_WHEEL_REWARD = int(settings.get('max_wheel_reward', 3))
    Config.MIN_GAME_REWARD = int(settings.get('min_game_reward', 1))
    Config.MAX_GAME_REWARD = int(settings.get('max_game_reward', 3))
    Config.USD_TO_EGP = float(settings.get('usd_to_egp', 52.0))
    Config.FORCE_SUB_ENABLED = settings.get('force_sub_enabled', '1') == '1'
    Config.LANGUAGE = settings.get('language', 'ar')
    Config.CANCEL_WITHDRAWAL_MINUTES = int(settings.get('cancel_withdrawal_minutes', '1'))

load_config_from_db()


# ==================== دوال مساعدة ====================

class Helpers:
    """الدوال المساعدة"""
    
    @staticmethod
    def format_time_remaining(last_claim: Optional[str]) -> Optional[str]:
        if not last_claim:
            return None
        try:
            last_time = datetime.fromisoformat(last_claim)
            next_time = last_time + timedelta(hours=24)
            now = datetime.now()
            if now >= next_time:
                return None
            remaining = next_time - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            return f"{hours} ساعة و {minutes} دقيقة"
        except:
            return None
    
    @staticmethod
    def can_cancel_withdrawal(created_at: str) -> bool:
        try:
            created_time = datetime.fromisoformat(created_at)
            now = datetime.now()
            diff_minutes = (now - created_time).total_seconds() / 60
            return diff_minutes < Config.CANCEL_WITHDRAWAL_MINUTES
        except:
            return False
    
    @staticmethod
    def get_remaining_cancel_time(created_at: str) -> str:
        try:
            created_time = datetime.fromisoformat(created_at)
            cancel_deadline = created_time + timedelta(minutes=Config.CANCEL_WITHDRAWAL_MINUTES)
            now = datetime.now()
            if now >= cancel_deadline:
                return "0"
            remaining = cancel_deadline - now
            seconds = remaining.seconds
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}:{seconds:02d}"
        except:
            return "0"
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        return bool(re.match(r'^01[0-9]{9}$', phone))
    
    @staticmethod
    def validate_binance_id(binance_id: str) -> bool:
        return len(binance_id.strip()) >= 5
    
    @staticmethod
    def validate_usdt_address(address: str) -> bool:
        address = address.strip()
        return len(address) == 34 and address.startswith('T')
    
    @staticmethod
    def get_min_withdrawal_egp(withdrawal_count: int) -> int:
        return Config.FIRST_WITHDRAWAL_EGP if withdrawal_count == 0 else Config.SECOND_WITHDRAWAL_EGP
    
    @staticmethod
    async def check_force_sub(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, List[Dict]]:
        if not Config.FORCE_SUB_ENABLED:
            return True, []
        
        channels = db.get_channels()
        if not channels:
            return True, []
        
        not_subscribed = []
        for channel in channels:
            try:
                chat_member = await context.bot.get_chat_member(chat_id=channel['id'], user_id=user_id)
                if chat_member.status in ['left', 'kicked']:
                    not_subscribed.append(channel)
            except:
                not_subscribed.append(channel)
        
        return len(not_subscribed) == 0, not_subscribed
    
    @staticmethod
    def create_force_sub_keyboard(not_subscribed_channels: List[Dict]) -> InlineKeyboardMarkup:
        keyboard = []
        for channel in not_subscribed_channels:
            keyboard.append([InlineKeyboardButton(f"📢 اشترك في {channel['name']}", url=channel['link'])])
        keyboard.append([InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")])
        return InlineKeyboardMarkup(keyboard)


helpers = Helpers()


# ==================== نظام التحقق ====================

class VerificationSystem:
    """نظام تحقق مميز"""
    
    QUESTIONS = [
        {"question": "كم عدد أصابع اليد الواحدة؟", "answer": "5"},
        {"question": "ما هو لون السماء في يوم صافٍ؟", "answer": "ازرق"},
        {"question": "كم عدد أرجل القطة؟", "answer": "4"},
        {"question": "ما هو عكس كلمة 'كبير'؟", "answer": "صغير"},
        {"question": "كم عدد أيام الأسبوع؟", "answer": "7"},
        {"question": "ما هو الشهر الأول في السنة؟", "answer": "يناير"},
        {"question": "كم عدد حروف الأبجدية العربية؟", "answer": "28"},
        {"question": "ما هو لون التفاح الأحمر؟", "answer": "احمر"},
        {"question": "كم عدد أرجل الإنسان؟", "answer": "2"},
        {"question": "ما هو عكس كلمة 'ساخن'؟", "answer": "بارد"},
    ]
    
    @staticmethod
    def generate_math_question() -> Dict[str, str]:
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        operations = ['+', '-', '×']
        op = random.choice(operations)
        
        if op == '+':
            answer = str(num1 + num2)
            question = f"{num1} + {num2}"
        elif op == '-':
            if num1 < num2:
                num1, num2 = num2, num1
            answer = str(num1 - num2)
            question = f"{num1} - {num2}"
        else:
            answer = str(num1 * num2)
            question = f"{num1} × {num2}"
        
        return {'question': question, 'answer': answer}
    
    @staticmethod
    def generate_captcha() -> Dict[str, str]:
        if random.random() < 0.7:
            return VerificationSystem.generate_math_question()
        else:
            return random.choice(VerificationSystem.QUESTIONS)
    
    @staticmethod
    def get_verification_message() -> str:
        return """🔐 مطلوب التحقق من أنك إنسان

🤖 لماذا التحقق؟
للتأكد من أنك إنسان حقيقي وحماية البوت من البوتات والسبام.

✅ كيف تتحقق؟
فقط أجب على السؤال أدناه بشكل صحيح.

⚠️ مهم:
• لديك 3 محاولات
• بعد 3 إجابات خاطئة، ستحتاج لإعادة المحاولة"""
    
    @staticmethod
    def get_wrong_answer_message(attempts_left: int) -> str:
        return f"""❌ إجابة خاطئة

لديك {attempts_left} محاولة{'ات' if attempts_left > 1 else ''} متبقية.

🔐 حاول مرة أخرى بالإجابة الصحيحة."""


verification = VerificationSystem()


# ==================== ديكوراتور التحقق ====================

def require_force_sub(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        user_data = db.get_user(user_id)
        if user_data and not user_data.get('verified', False):
            await UserHandlers.start_verification(update, context)
            return None
        
        is_subscribed, not_subscribed = await helpers.check_force_sub(user_id, context)
        
        if is_subscribed:
            return await func(update, context, *args, **kwargs)
        else:
            message = "⚠️ عذراً! يجب الاشتراك في القنوات التالية:\n\n"
            for channel in not_subscribed:
                message += f"• {channel['name']}\n"
            message += "\n✅ بعد الاشتراك، اضغط على زر التحقق"
            
            keyboard = helpers.create_force_sub_keyboard(not_subscribed)
            
            if update.callback_query:
                await update.callback_query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
                await update.callback_query.answer()
            else:
                await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
            return None
    return wrapper


# ==================== أوامر المستخدمين ====================

class UserHandlers:
    """معالجات المستخدمين"""
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بداية البوت مع معالجة رابط الدعوة"""
        user = update.effective_user
        user_id = user.id
        user_name = user.first_name
        username = user.username
        
        Config.USD_TO_EGP = await ExchangeRateService.get_usd_to_egp()
        db.set_setting('usd_to_egp', str(Config.USD_TO_EGP))
        
        referred_by = None
        if context.args and len(context.args) > 0:
            ref_param = context.args[0]
            if ref_param.startswith('ref_'):
                try:
                    referred_by = int(ref_param.split('_')[1])
                    if referred_by == user_id:
                        referred_by = None
                except:
                    pass
            elif ref_param.isdigit():
                referred_by = int(ref_param)
                if referred_by == user_id:
                    referred_by = None
        
        user_data = db.get_user(user_id)
        
        if not user_data:
            captcha = verification.generate_captcha()
            db.create_user(user_id, username, user_name, referred_by)
            
            db.set_temp_data(user_id, {
                'captcha': captcha,
                'awaiting_verification': True,
                'verification_attempts': 0,
                'verification_message_id': None
            })
            
            await UserHandlers.start_verification(update, context)
            return
        
        if not user_data.get('verified', False):
            await UserHandlers.start_verification(update, context)
            return
        
        await UserHandlers.show_menu(update, context)
    
    @staticmethod
    async def start_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء عملية التحقق"""
        user_id = update.effective_user.id
        
        temp_data = db.get_temp_data(user_id)
        
        if not temp_data:
            captcha = verification.generate_captcha()
            temp_data = {
                'captcha': captcha,
                'awaiting_verification': True,
                'verification_attempts': 0,
                'verification_message_id': None
            }
            db.set_temp_data(user_id, temp_data)
        
        captcha = temp_data['captcha']
        
        verification_msg = verification.get_verification_message()
        question_msg = f"**🔐 سؤال التحقق:**\n\n❓ {captcha['question']} = ?\n\n📝 أرسل إجابتك كرسالة نصية."
        full_msg = f"{verification_msg}\n\n{question_msg}"
        
        keyboard = [
            [InlineKeyboardButton("❓ مساعدة", callback_data="verification_help")],
            [InlineKeyboardButton("🔄 سؤال جديد", callback_data="new_question")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.edit_text(full_msg, reply_markup=reply_markup, parse_mode='Markdown')
            await update.callback_query.answer()
        else:
            sent_msg = await update.message.reply_text(full_msg, reply_markup=reply_markup, parse_mode='Markdown')
            temp_data['verification_message_id'] = sent_msg.message_id
            db.set_temp_data(user_id, temp_data)
    
    @staticmethod
    async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
        """التحقق من المستخدم ومعالجة الدعوة"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        username = update.effective_user.username
        
        temp_data = db.get_temp_data(user_id)
        
        if not temp_data or not temp_data.get('awaiting_verification'):
            return
        
        captcha = temp_data['captcha']
        answer_clean = answer.strip().lower()
        correct_answer = captcha['answer'].lower()
        
        if answer_clean == correct_answer:
            db.update_user(user_id, verified=1)
            
            user_data = db.get_user(user_id)
            
            if user_data:
                referred_by = user_data.get('referred_by')
                
                if referred_by and referred_by != 0 and referred_by != user_id:
                    existing_refs = db.get_referral_exists(referred_by, user_id)
                    
                    if not existing_refs:
                        db.add_balance(referred_by, Config.REFERRAL_BONUS_EGP, True)
                        db.add_referral(referred_by, user_id, user_name, Config.REFERRAL_BONUS_EGP)
                        
                        try:
                            ref_user = db.get_user(referred_by)
                            if ref_user:
                                ref_currency = ref_user.get('display_currency', 'EGP')
                                ref_bonus_formatted = currency.format_amount(Config.REFERRAL_BONUS_EGP, ref_currency)
                                ref_msg = f"🎉 مبروك! قام {user_name} بالتسجيل عبر رابطك\n💰 تم إضافة {ref_bonus_formatted} إلى رصيدك"
                                await context.bot.send_message(referred_by, ref_msg)
                                logger.info(f"✅ تم إضافة دعوة: {referred_by} -> {user_id}")
                        except Exception as e:
                            logger.error(f"خطأ في إرسال رسالة الدعوة: {e}")
            
            if temp_data.get('verification_message_id'):
                try:
                    await context.bot.delete_message(chat_id=user_id, message_id=temp_data['verification_message_id'])
                except:
                    pass
            
            db.delete_temp_data(user_id)
            await UserHandlers.show_menu(update, context)
            
        else:
            attempts = temp_data.get('verification_attempts', 0) + 1
            temp_data['verification_attempts'] = attempts
            max_attempts = 3
            
            if attempts >= max_attempts:
                msg = f"❌ **لقد تجاوزت الحد الأقصى للمحاولات ({max_attempts})!** ❌\n\n🔄 استخدم /start للمحاولة مرة أخرى."
                await update.message.reply_text(msg, parse_mode='Markdown')
                db.delete_temp_data(user_id)
                return
            
            new_captcha = verification.generate_captcha()
            temp_data['captcha'] = new_captcha
            db.set_temp_data(user_id, temp_data)
            
            wrong_msg = verification.get_wrong_answer_message(max_attempts - attempts)
            question_msg = f"**🔐 سؤال تحقق جديد:**\n\n❓ {new_captcha['question']} = ?"
            
            await update.message.reply_text(f"{wrong_msg}\n\n{question_msg}", parse_mode='Markdown')
    
    @staticmethod
    async def verification_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        help_msg = """**📖 مساعدة التحقق**

**كيف تجيب:**
• للأسئلة الحسابية: اكتب الرقم فقط (مثال: "8")
• للأسئلة الكتابية: اكتب الإجابة بالعربية

**أمثلة:**
• سؤال: "5 + 3 = ?" → الإجابة: "8"
• سؤال: "ما هو لون السماء؟" → الإجابة: "ازرق"

**نصائح:**
• الإجابات غير حساسة لحالة الأحرف
• يمكنك الحصول على سؤال جديد إذا أردت
• لديك 3 محاولات إجمالاً"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_verification")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(help_msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def new_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        temp_data = db.get_temp_data(user_id)
        if not temp_data:
            await UserHandlers.start_verification(update, context)
            return
        
        new_captcha = verification.generate_captcha()
        temp_data['captcha'] = new_captcha
        db.set_temp_data(user_id, temp_data)
        
        msg = f"🔄 **سؤال تحقق جديد:**\n\n❓ {new_captcha['question']} = ?\n\n📝 أرسل إجابتك."
        
        keyboard = [
            [InlineKeyboardButton("❓ مساعدة", callback_data="verification_help")],
            [InlineKeyboardButton("🔄 سؤال جديد", callback_data="new_question")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def back_to_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await UserHandlers.start_verification(update, context)
    
    @staticmethod
    @require_force_sub
    async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض القائمة الرئيسية"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        user_data = db.get_user(user_id)
        if not user_data:
            await UserHandlers.start(update, context)
            return
        
        if not user_data.get('verified', False):
            await UserHandlers.start_verification(update, context)
            return
        
        balance_egp = user_data.get('balance_egp', 0)
        user_currency = user_data.get('display_currency', 'EGP')
        formatted_balance = currency.format_amount(balance_egp, user_currency)
        
        pending_withdrawal = db.get_pending_withdrawal(user_id)
        cancel_button = []
        
        if pending_withdrawal and helpers.can_cancel_withdrawal(pending_withdrawal['created_at']):
            cancel_button = [[InlineKeyboardButton("❌ إلغاء طلب السحب", callback_data="cancel_withdrawal")]]
        
        msg = f"""🌟 مرحباً بك، {user_name}!

📌 بوت ربحي - مكانك المضمون لزيادة أرباحك

💰 اكسب بسهولة:
• عجلة الحظ
• لعبة العب واربح
• الهدية اليومية
• دعوة الأصدقاء
• مهمات التطبيقات

💵 رصيدك الحالي: {formatted_balance}"""
        
        keyboard = [
            [InlineKeyboardButton("💰 سحب الأرباح", callback_data="withdraw")],
            [
                InlineKeyboardButton("🎯 المهام اليومية", callback_data="daily_tasks"),
                InlineKeyboardButton("👥 الدعوة", callback_data="referral")
            ],
            [
                InlineKeyboardButton("📜 شروط البوت", callback_data="bot_terms"),
                InlineKeyboardButton("ℹ️ معلومات البوت", callback_data="bot_info")
            ],
            [InlineKeyboardButton("📊 الحساب", callback_data="account")],
            [InlineKeyboardButton("⚙️ الاعدادات", callback_data="settings_menu")],
        ]
        
        if cancel_button:
            keyboard.extend(cancel_button)
        
        if user_id in Config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🔧 لوحة الأدمن", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=reply_markup)
            await update.callback_query.answer()
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
    
    @staticmethod
    @require_force_sub
    async def daily_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة المهام اليومية - كل المهام ظاهرة"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        last_wheel = user_data.get('last_wheel_date')
        last_game = user_data.get('last_game_date')
        last_daily = user_data.get('last_daily_claim')
        
        wheel_available = helpers.format_time_remaining(last_wheel) is None
        game_available = helpers.format_time_remaining(last_game) is None
        daily_available = helpers.format_time_remaining(last_daily) is None
        
        msg = """🎯 **المهام اليومية**

🎡 **عجلة الحظ** - اربح من 1-3 جنيه يومياً
🎮 **العب واربح** - اختار مربع واكسب جائزتك
🎁 **الهدية اليومية** - هدية مجانية يومياً
📱 **مهمات التطبيقات** - نفذ مهام التطبيقات واكسب


✅ **الحالة:**"""
        
        if wheel_available:
            msg += "\n🎡 عجلة الحظ: ✅ متاحة"
        else:
            time_left = helpers.format_time_remaining(last_wheel)
            msg += f"\n🎡 عجلة الحظ: ⏰ متبقي {time_left}"
        
        if game_available:
            msg += "\n🎮 العب واربح: ✅ متاحة"
        else:
            time_left = helpers.format_time_remaining(last_game)
            msg += f"\n🎮 العب واربح: ⏰ متبقي {time_left}"
        
        if daily_available:
            msg += "\n🎁 الهدية اليومية: ✅ متاحة"
        else:
            time_left = helpers.format_time_remaining(last_daily)
            msg += f"\n🎁 الهدية اليومية: ⏰ متبقي {time_left}"
        
        keyboard = [
            [InlineKeyboardButton("🎡 عجلة الحظ", callback_data="wheel_of_fortune")],
            [InlineKeyboardButton("🎮 العب واربح", callback_data="play_and_win")],
            [InlineKeyboardButton("🎁 الهدية اليومية", callback_data="daily")],
            [InlineKeyboardButton("📱 مهمات التطبيقات", callback_data="app_tasks_menu")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    @require_force_sub
    async def wheel_of_fortune(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عجلة الحظ"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        last_wheel = user_data.get('last_wheel_date')
        time_left = helpers.format_time_remaining(last_wheel)
        
        if time_left is not None:
            await query.answer(f"⏰ تعال بعد 24 ساعة! متبقي: {time_left}", show_alert=True)
            return
        
        reward = random.randint(Config.MIN_WHEEL_REWARD, Config.MAX_WHEEL_REWARD)
        db.add_balance(user_id, reward, True)
        db.update_user(user_id, last_wheel_date=datetime.now().isoformat())
        
        formatted_reward = currency.format_amount(reward, user_currency)
        new_balance = user_data['balance_egp'] + reward
        formatted_balance = currency.format_amount(new_balance, user_currency)
        
        msg = f"""🎡 **مبروك!**

💰 لقد ربحت {formatted_reward} من عجلة الحظ!
📊 رصيدك الآن: {formatted_balance}

🎁 عُد غداً للعب مرة أخرى!"""
        
        await query.message.reply_text(msg, parse_mode='Markdown')
        await query.answer("🎉 تم الربح!")
        await UserHandlers.daily_tasks_menu(update, context)
    
    @staticmethod
    @require_force_sub
    async def play_and_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لعبة العب واربح"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        last_game = user_data.get('last_game_date')
        time_left = helpers.format_time_remaining(last_game)
        
        if time_left is not None:
            await query.answer(f"⏰ تعال بعد 24 ساعة! متبقي: {time_left}", show_alert=True)
            return
        
        rewards = {}
        for i in range(1, 11):
            rewards[str(i)] = random.randint(Config.MIN_GAME_REWARD, Config.MAX_GAME_REWARD)
        
        db.set_temp_data(user_id, {'game_rewards': rewards, 'game_played': False})
        
        keyboard = []
        row1 = []
        for i in range(1, 6):
            row1.append(InlineKeyboardButton("🟥", callback_data=f"game_box_{i}"))
        keyboard.append(row1)
        
        row2 = []
        for i in range(6, 11):
            row2.append(InlineKeyboardButton("🟥", callback_data=f"game_box_{i}"))
        keyboard.append(row2)
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="daily_tasks")])
        
        msg = f"""🎮 **العب واربح**

اختر أحد المربعات الحمراء لتربح جائزة!

🟥 **المربعات الحمراء** - كل مربع يحتوي على جائزة مختلفة!

⚠️ يمكنك اللعب مرة كل 24 ساعة"""
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def game_box_selected(update: Update, context: ContextTypes.DEFAULT_TYPE, box_num: int):
        """اختيار مربع في اللعبة"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        temp_data = db.get_temp_data(user_id)
        
        if not temp_data or not temp_data.get('game_rewards'):
            await query.answer("اللعبة منتهية! ابدأ من جديد", show_alert=True)
            await UserHandlers.daily_tasks_menu(update, context)
            return
        
        if temp_data.get('game_played'):
            await query.answer("⏰ لقد لعبت بالفعل! تعال بعد 24 ساعة", show_alert=True)
            return
        
        rewards = temp_data['game_rewards']
        reward = rewards.get(str(box_num), random.randint(Config.MIN_GAME_REWARD, Config.MAX_GAME_REWARD))
        
        db.add_balance(user_id, reward, True)
        db.update_user(user_id, last_game_date=datetime.now().isoformat())
        
        temp_data['game_played'] = True
        db.set_temp_data(user_id, temp_data)
        
        formatted_reward = currency.format_amount(reward, user_currency)
        new_balance = user_data['balance_egp'] + reward
        formatted_balance = currency.format_amount(new_balance, user_currency)
        
        msg = f"""🎮 **نتيجة اللعبة**

✅ لقد ربحت: {formatted_reward}

📊 رصيدك الآن: {formatted_balance}

🎁 عُد غداً للعب مرة أخرى!"""
        
        await query.message.reply_text(msg, parse_mode='Markdown')
        await query.answer("🎉 تم الربح!")
        await UserHandlers.daily_tasks_menu(update, context)
    
    @staticmethod
    @require_force_sub
    async def account_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة الحساب"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        referral_count = db.get_referral_count(user_id)
        next_withdraw_egp = helpers.get_min_withdrawal_egp(user_data.get('withdrawal_count', 0))
        
        formatted_balance = currency.format_amount(user_data.get('balance_egp', 0), user_currency)
        formatted_total = currency.format_amount(user_data.get('total_earnings_egp', 0), user_currency)
        formatted_next = currency.format_amount(next_withdraw_egp, user_currency)
        
        msg = f"""📊 **حسابي**

💰 الرصيد الحالي: {formatted_balance}
🏆 إجمالي الأرباح: {formatted_total}
👥 عدد المدعوين: {referral_count}
💸 عدد السحوبات: {user_data.get('withdrawal_count', 0)}
💵 الحد الأدنى للسحب القادم: {formatted_next}"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    @require_force_sub
    async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نظام الدعوة"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        referral_count = db.get_referral_count(user_id)
        formatted_bonus = currency.format_amount(Config.REFERRAL_BONUS_EGP, user_currency)
        
        msg = f"""👥 **نظام دعوة الأصدقاء**

💰 ربح الدعوة: {formatted_bonus} لكل مدعو
👥 عدد المدعوين: {referral_count}

🔗 رابط الدعوة الخاص بك:
`{link}`

📤 شارك هذا الرابط مع أصدقائك واكسب فلوس مقابل كل تسجيل!

💡 نصيحة: كلما زاد عدد المدعوين، زادت أرباحك!"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    @require_force_sub
    async def bot_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """شروط البوت"""
        query = update.callback_query
        
        msg = f"""📜 **شروط البوت**

✅ **شروط السحب:**
• يتم السحب خلال 24-48 ساعة
• يجب إدخال رقم هاتف صحيح أو ID بينانس أو عنوان USDT TRON
• يمكن إلغاء طلب السحب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة من التقديم

🚫 **الممنوعات:**
• حساب واحد لكل شخص
• لا للدعوات الوهمية
• لا لبرامج الغش

⚠️ الغش = حظر فوري وفقدان الأرباح"""
        
        keyboard = [
            [InlineKeyboardButton("🆘 الدعم الفني", url="https://t.me/MN_BF")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    @require_force_sub
    async def bot_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معلومات البوت"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        formatted_daily = currency.format_amount(Config.DAILY_BONUS_EGP, user_currency)
        formatted_referral = currency.format_amount(Config.REFERRAL_BONUS_EGP, user_currency)
        formatted_first = currency.format_amount(Config.FIRST_WITHDRAWAL_EGP, user_currency)
        formatted_second = currency.format_amount(Config.SECOND_WITHDRAWAL_EGP, user_currency)
        
        msg = f"""ℹ️ **معلومات البوت**

💰 **طرق الربح:**
• الهدية اليومية: {formatted_daily} يومياً
• دعوة الأصدقاء: {formatted_referral} لكل مدعو
• مهمات التطبيقات: حسب قيمة كل مهمة

💳 **طرق السحب:**
• فودافون كاش
• اتصالات كاش
• أورنج كاش
• بينانس
• إنستاباي
• USDT (TRC20)

💵 **شروط السحب:**
• أول سحب: {formatted_first}
• السحب الثاني: {formatted_second}
• المدة: 24-48 ساعة
• يمكن إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة من تقديمه"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    @require_force_sub
    async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إعدادات المستخدم"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        current_lang = "العربية"
        current_currency = "جنيه مصري" if user_currency == "EGP" else "دولار أمريكي"
        
        msg = f"""⚙️ **الإعدادات**

🌐 اللغة الحالية: {current_lang}
💵 عملة العرض الحالية: {current_currency}

💡 سعر الصرف: 1 دولار = {Config.USD_TO_EGP:.2f} جنيه
📌 جميع القيم مخزنة بالجنيه ويتم تحويلها للعرض"""
        
        keyboard = [
            [InlineKeyboardButton("🌐 اللغة / Language", callback_data="change_lang")],
            [InlineKeyboardButton("💵 عملة العرض", callback_data="change_currency")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        Config.LANGUAGE = "en" if Config.LANGUAGE == "ar" else "ar"
        db.set_setting('language', Config.LANGUAGE)
        
        await query.answer("تم تغيير اللغة!" if Config.LANGUAGE == "ar" else "Language changed!")
        await UserHandlers.settings_menu(update, context)
    
    @staticmethod
    async def change_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        user_data = db.get_user(user_id)
        if user_data:
            current_currency = user_data.get('display_currency', 'EGP')
            new_currency = "USD" if current_currency == "EGP" else "EGP"
            db.update_user(user_id, display_currency=new_currency)
        
        await query.answer("تم تغيير عملة العرض!")
        await UserHandlers.settings_menu(update, context)
    
    @staticmethod
    @require_force_sub
    async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """الهدية اليومية"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        time_left = helpers.format_time_remaining(user_data.get('last_daily_claim'))
        
        if time_left is None:
            db.add_balance(user_id, Config.DAILY_BONUS_EGP, True)
            db.update_user(user_id, last_daily_claim=datetime.now().isoformat())
            
            formatted_amount = currency.format_amount(Config.DAILY_BONUS_EGP, user_currency)
            new_balance = user_data['balance_egp'] + Config.DAILY_BONUS_EGP
            formatted_balance = currency.format_amount(new_balance, user_currency)
            
            msg = f"✅ تم استلام الهدية اليومية\n\n💰 المبلغ: {formatted_amount}\n📊 رصيدك: {formatted_balance}\n\n🎁 الهدية القادمة بعد 24 ساعة"
            
            await query.message.reply_text(msg)
            await query.answer("🎁 تم الاستلام!")
            await UserHandlers.daily_tasks_menu(update, context)
        else:
            formatted_balance = currency.format_amount(user_data.get('balance_egp', 0), user_currency)
            msg = f"⚠️ لا يمكنك استلام الهدية الآن\n\n🕐 الوقت المتبقي: {time_left}\n💰 رصيدك: {formatted_balance}"
            await query.message.reply_text(msg)
            await query.answer(f"⏰ تعال بعد 24 ساعة! متبقي: {time_left}", show_alert=True)
    
    @staticmethod
    async def update_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تحديث رسالة القائمة"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        user_data = db.get_user(user_id)
        balance_egp = user_data.get('balance_egp', 0)
        user_currency = user_data.get('display_currency', 'EGP')
        formatted_balance = currency.format_amount(balance_egp, user_currency)
        
        pending_withdrawal = db.get_pending_withdrawal(user_id)
        cancel_button = []
        
        if pending_withdrawal and helpers.can_cancel_withdrawal(pending_withdrawal['created_at']):
            cancel_button = [[InlineKeyboardButton("❌ إلغاء طلب السحب", callback_data="cancel_withdrawal")]]
        
        msg = f"""🌟 مرحباً بك، {user_name}!

📌 بوت ربحي - مكانك المضمون لزيادة أرباحك

💰 اكسب بسهولة:
• عجلة الحظ
• لعبة العب واربح
• الهدية اليومية
• دعوة الأصدقاء
• مهمات التطبيقات

💵 رصيدك الحالي: {formatted_balance}"""
        
        keyboard = [
            [InlineKeyboardButton("💰 سحب الأرباح", callback_data="withdraw")],
            [
                InlineKeyboardButton("🎯 المهام اليومية", callback_data="daily_tasks"),
                InlineKeyboardButton("👥 الدعوة", callback_data="referral")
            ],
            [
                InlineKeyboardButton("📜 شروط البوت", callback_data="bot_terms"),
                InlineKeyboardButton("ℹ️ معلومات البوت", callback_data="bot_info")
            ],
            [InlineKeyboardButton("📊 الحساب", callback_data="account")],
            [InlineKeyboardButton("⚙️ الاعدادات", callback_data="settings_menu")],
        ]
        
        if cancel_button:
            keyboard.extend(cancel_button)
        
        if user_id in Config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🔧 لوحة الأدمن", callback_data="admin")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=reply_markup)
    
    @staticmethod
    @require_force_sub
    async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """قائمة السحب"""
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        pending_withdrawal = db.get_pending_withdrawal(user_id)
        
        if pending_withdrawal:
            formatted_amount = currency.format_amount(pending_withdrawal.get('amount_egp', 0), user_currency)
            can_cancel = helpers.can_cancel_withdrawal(pending_withdrawal['created_at'])
            
            msg = f"""⚠️ لا يمكنك تقديم طلب سحب جديد

📌 لديك طلب سحب قيد المعالجة:
🆔 رقم الطلب: {pending_withdrawal['id']}
💰 المبلغ: {formatted_amount}
⏰ تاريخ الطلب: {pending_withdrawal['created_at'][:10]}
⏱️ الوقت المتبقي للإلغاء: {helpers.get_remaining_cancel_time(pending_withdrawal['created_at'])} دقيقة

✅ سيتم مراجعة طلبك قريباً"""
            
            keyboard = []
            if can_cancel:
                keyboard.append([InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"cancel_withdrawal")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            await query.answer()
            return
        
        min_amount_egp = helpers.get_min_withdrawal_egp(user_data.get('withdrawal_count', 0))
        formatted_min = currency.format_amount(min_amount_egp, user_currency)
        formatted_balance = currency.format_amount(user_data.get('balance_egp', 0), user_currency)
        
        if user_data.get('balance_egp', 0) < min_amount_egp:
            msg = f"""❌ رصيدك لا يكفي للسحب

💰 رصيدك: {formatted_balance}
💵 المطلوب: {formatted_min}

💡 زود رصيدك بالمهام اليومية أو دعوة الأصدقاء"""
            
            await query.message.reply_text(msg)
            await UserHandlers.update_menu_message(update, context)
            await query.answer()
            return
        
        msg = f"""💰 **سحب الأرباح**

💵 المبلغ اللي هتسحبه: {formatted_min}

📌 اختر طريقة السحب:
💡 ملاحظة: يمكنك إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة من تقديمه"""
        
        keyboard = [
            [InlineKeyboardButton("💳 فودافون كاش", callback_data="withdraw_vodafone")],
            [InlineKeyboardButton("📱 اتصالات كاش", callback_data="withdraw_etisalat")],
            [InlineKeyboardButton("🟠 أورنج كاش", callback_data="withdraw_orange")],
            [InlineKeyboardButton("🟡 بينانس", callback_data="withdraw_binance")],
            [InlineKeyboardButton("💳 إنستاباي", callback_data="withdraw_instapay")],
            [InlineKeyboardButton("💎 USDT (TRC20)", callback_data="withdraw_usdt")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, method: str):
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        methods = {
            'vodafone': 'فودافون كاش',
            'etisalat': 'اتصالات كاش',
            'orange': 'أورنج كاش',
            'instapay': 'إنستاباي'
        }
        
        method_name = methods.get(method, method)
        min_amount_egp = helpers.get_min_withdrawal_egp(user_data.get('withdrawal_count', 0))
        formatted_amount = currency.format_amount(min_amount_egp, user_currency)
        
        db.set_temp_data(user_id, {
            'withdraw_method': method_name,
            'withdraw_amount_egp': min_amount_egp,
            'waiting_phone': True
        })
        
        await query.message.reply_text(
            f"📱 أدخل رقم {method_name}\n\n📌 مثال: 01012345678\n💰 المبلغ: {formatted_amount}\n\n💡 ملاحظة: يمكنك إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة بعد التقديم\n\n⚠️ تحذير: الرقم مسجل لحساب واحد فقط!"
        )
        await query.answer()
    
    @staticmethod
    async def request_binance_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        min_amount_egp = helpers.get_min_withdrawal_egp(user_data.get('withdrawal_count', 0))
        formatted_amount = currency.format_amount(min_amount_egp, user_currency)
        
        db.set_temp_data(user_id, {
            'withdraw_method': 'بينانس',
            'withdraw_amount_egp': min_amount_egp,
            'waiting_binance_id': True
        })
        
        await query.message.reply_text(
            f"🟡 أدخل ID بينانس أو الإيميل المرتبط\n\n📌 مثال: user123@binance.com أو 12345678\n💰 المبلغ: {formatted_amount}\n\n💡 ملاحظة: يمكنك إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة بعد التقديم"
        )
        await query.answer()
    
    @staticmethod
    async def request_usdt_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        
        min_amount_egp = helpers.get_min_withdrawal_egp(user_data.get('withdrawal_count', 0))
        formatted_amount = currency.format_amount(min_amount_egp, user_currency)
        
        db.set_temp_data(user_id, {
            'withdraw_method': 'USDT (TRC20)',
            'withdraw_amount_egp': min_amount_egp,
            'waiting_usdt_address': True
        })
        
        await query.message.reply_text(
            f"💎 أدخل عنوان محفظة USDT (TRC20)\n\n📌 مثال: T... (34 حرف، يبدأ بحرف T)\n💰 المبلغ: {formatted_amount}\n\n⚠️ يتم قبول عناوين شبكة TRON (TRC20) فقط\n💡 ملاحظة: يمكنك إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة بعد التقديم"
        )
        await query.answer()
    
    @staticmethod
    async def process_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str = None, binance_id: str = None, usdt_address: str = None):
        user_id = update.effective_user.id
        temp_data = db.get_temp_data(user_id)
        
        if not temp_data:
            return
        
        if db.get_pending_withdrawal(user_id):
            await update.message.reply_text("❌ لديك طلب سحب قيد المعالجة بالفعل!")
            db.delete_temp_data(user_id)
            return
        
        if phone:
            if not temp_data.get('waiting_phone'):
                return
            
            if not helpers.validate_phone(phone):
                await update.message.reply_text(
                    f"❌ رقم غير صحيح!\n📌 يجب أن يكون 11 رقم ويبدأ بـ 010 أو 011 أو 012\n🔄 أعد إدخال الرقم:"
                )
                return
            
            existing_user = db.get_user_by_phone(phone)
            if existing_user and existing_user['user_id'] != user_id:
                db.ban_user(user_id, f"محاولة استخدام رقم مستخدم من حساب آخر: {phone}")
                db.ban_user(existing_user['user_id'], f"تم استخدام رقمه من حساب آخر: {phone}")
                
                for admin_id in Config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"🚫 **تم حظر حسابين لتكرار الرقم!**\n\n"
                            f"📱 الرقم: {phone}\n"
                            f"👤 الحساب الأول: {existing_user['user_id']}\n"
                            f"👤 الحساب الثاني: {user_id}\n"
                            f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    except:
                        pass
                
                await update.message.reply_text(
                    "❌ **تم حظر حسابك!**\n\n"
                    "هذا الرقم مسجل بحساب آخر. لا يمكن استخدام نفس الرقم لحسابين مختلفين.\n\n"
                    "للإستفسار، تواصل مع الدعم الفني."
                )
                db.delete_temp_data(user_id)
                return
            
            withdraw_data = {'phone': phone}
            db.update_user_phone(user_id, phone)
        
        elif binance_id:
            if not temp_data.get('waiting_binance_id'):
                return
            
            if not helpers.validate_binance_id(binance_id):
                await update.message.reply_text("❌ ID بينانس غير صحيح!\n🔄 أعد إدخال ID:")
                return
            
            withdraw_data = {'binance_id': binance_id}
        
        elif usdt_address:
            if not temp_data.get('waiting_usdt_address'):
                return
            
            if not helpers.validate_usdt_address(usdt_address):
                await update.message.reply_text(
                    "❌ عنوان USDT (TRC20) غير صحيح!\n📌 العنوان يجب أن يكون 34 حرفاً ويبدأ بحرف T\n🔄 أعد إدخال العنوان:"
                )
                return
            
            withdraw_data = {'usdt_address': usdt_address}
        
        else:
            return
        
        amount_egp = temp_data['withdraw_amount_egp']
        
        if db.subtract_balance(user_id, amount_egp):
            w_id = db.create_withdrawal(
                user_id, amount_egp, temp_data['withdraw_method'],
                **withdraw_data
            )
            
            user_data = db.get_user(user_id)
            user_currency = user_data.get('display_currency', 'EGP')
            formatted_amount = currency.format_amount(amount_egp, user_currency)
            
            msg = f"""✅ تم تقديم طلب السحب

💰 المبلغ: {formatted_amount}
💳 الطريقة: {temp_data['withdraw_method']}
🆔 رقم الطلب: {w_id}

⏰ سيتم التحويل خلال 24-48 ساعة
❌ يمكنك إلغاء الطلب خلال {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة من الآن"""
            
            if phone:
                msg += f"\n📱 {phone}"
            elif binance_id:
                msg += f"\n🆔 {binance_id}"
            elif usdt_address:
                msg += f"\n💎 {usdt_address}"
            
            await update.message.reply_text(msg)
            
            admin_msg = f"💰 طلب سحب جديد #{w_id}\n👤 {update.effective_user.first_name}\n💵 {currency.format_amount_admin(amount_egp)}\n💳 {temp_data['withdraw_method']}"
            if phone:
                admin_msg += f"\n📱 {phone}"
            elif binance_id:
                admin_msg += f"\n🆔 {binance_id}"
            elif usdt_address:
                admin_msg += f"\n💎 {usdt_address}"
            
            for admin_id in Config.ADMIN_IDS:
                try:
                    await context.bot.send_message(admin_id, admin_msg)
                except:
                    pass
        
        db.delete_temp_data(user_id)
        await UserHandlers.update_menu_message(update, context)
    
    @staticmethod
    async def cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        pending_withdrawal = db.get_pending_withdrawal(user_id)
        
        if not pending_withdrawal:
            await query.answer("لا يوجد طلب سحب معلق!", show_alert=True)
            await UserHandlers.update_menu_message(update, context)
            return
        
        if not helpers.can_cancel_withdrawal(pending_withdrawal['created_at']):
            await query.answer("انتهت فترة الإلغاء! لا يمكن إلغاء الطلب.", show_alert=True)
            await UserHandlers.update_menu_message(update, context)
            return
        
        w_id = pending_withdrawal['id']
        amount_egp = pending_withdrawal['amount_egp']
        
        db.update_withdrawal_status(w_id, 'cancelled')
        db.refund_balance(user_id, amount_egp)
        
        user_data = db.get_user(user_id)
        user_currency = user_data.get('display_currency', 'EGP')
        formatted_amount = currency.format_amount(amount_egp, user_currency)
        
        msg = f"""❌ تم إلغاء طلب السحب #{w_id}

💰 تم إعادة المبلغ {formatted_amount} إلى رصيدك

📌 يمكنك تقديم طلب سحب جديد في أي وقت"""
        
        await query.message.reply_text(msg)
        
        for admin_id in Config.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id, 
                    f"❌ تم إلغاء طلب السحب #{w_id}\n👤 {update.effective_user.first_name}\n💵 {currency.format_amount_admin(amount_egp)}"
                )
            except:
                pass
        
        await query.answer("✅ تم إلغاء طلب السحب بنجاح!")
        await UserHandlers.update_menu_message(update, context)
    
    # ==================== نظام مهمات التطبيقات ====================
    
    @staticmethod
    @require_force_sub
    async def app_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة مهمات التطبيقات - تظهر مهمة واحدة فقط في كل مرة"""
        query = update.callback_query
        user_id = query.from_user.id
        
        tasks = db.get_active_app_tasks()
        
        if not tasks:
            msg = "📱 **مهمات التطبيقات**\n\n❌ لا توجد مهام متاحة حالياً.\n\n📢 انتظر إضافة مهام جديدة من الأدمن."
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="daily_tasks")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
            await query.answer()
            return
        
        available_task = None
        for task in tasks:
            if db.can_complete_app_task(user_id, task['id']):
                available_task = task
                break
        
        if not available_task:
            msg = "📱 **مهمات التطبيقات**\n\n✅ لقد أكملت جميع المهام المتاحة حالياً!\n\n📢 انتظر إضافة مهام جديدة."
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="daily_tasks")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
            await query.answer()
            return
        
        await UserHandlers.show_app_task_direct(update, context, available_task)
    
    @staticmethod
    async def show_app_task_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, task: Dict):
        """عرض تفاصيل مهمة التطبيق مباشرة"""
        query = update.callback_query
        user_id = query.from_user.id
        
        db.set_temp_data(user_id, {'current_task_id': task['id'], 'waiting_screenshot': False})
        
        formatted_reward = currency.format_amount(task['reward_egp'], 'EGP')
        
        msg = f"""📱 **{task['title']}**

{task['description']}

💰 **المكافأة:** {formatted_reward}

📌 **طريقة التنفيذ:**
1. اضغط على زر رابط التطبيق
2. حمل التطبيق ونفذ المطلوب
3. خذ سكرين شوت يثبت تنفيذ المهمة
4. أرسل السكرين شوت هنا مباشرة"""
        
        keyboard = []
        
        if task.get('app_link'):
            keyboard.append([InlineKeyboardButton("🔗 رابط التطبيق", url=task['app_link'])])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="daily_tasks")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if task.get('image_url'):
            try:
                await query.message.reply_photo(photo=task['image_url'], caption=msg, reply_markup=reply_markup, parse_mode='Markdown')
                await query.message.delete()
            except:
                await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        
        await query.answer()
    
    @staticmethod
    async def process_task_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة السكرين شوت المرسل من المستخدم"""
        user_id = update.effective_user.id
        temp_data = db.get_temp_data(user_id)
        
        if not temp_data or not temp_data.get('current_task_id'):
            await update.message.reply_text("❌ لا توجد مهمة نشطة حالياً. ابدأ من القائمة الرئيسية.")
            return
        
        task_id = temp_data.get('current_task_id')
        task = db.get_app_task(task_id)
        
        if not task:
            await update.message.reply_text("❌ المهمة غير موجودة!")
            db.delete_temp_data(user_id)
            return
        
        if not db.can_complete_app_task(user_id, task_id):
            await update.message.reply_text("⏰ لا يمكنك إكمال هذه المهمة الآن! انتظر 24 ساعة من آخر مرة.")
            db.delete_temp_data(user_id)
            return
        
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        completion_id = db.submit_task_completion(user_id, task_id, file_id)
        
        user_data = db.get_user(user_id)
        formatted_reward = currency.format_amount(task['reward_egp'], 'EGP')
        
        admin_msg = f"""📱 **طلب إكمال مهمة جديدة**

👤 المستخدم: {user_data.get('first_name', 'Unknown')}
🆔 ID: {user_id}
📱 المهمة: {task['title']}
💰 المكافأة: {formatted_reward}
🆔 رقم الطلب: {completion_id}

📸 الصورة مرفقة"""
        
        for admin_id in Config.ADMIN_IDS:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_msg,
                    parse_mode='Markdown'
                )
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ قبول", callback_data=f"admin_approve_task_{completion_id}"),
                        InlineKeyboardButton("❌ رفض", callback_data=f"admin_reject_task_{completion_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(admin_id, "اختر الإجراء:", reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"خطأ في إرسال إشعار للمشرف: {e}")
        
        db.delete_temp_data(user_id)
        
        await update.message.reply_text("✅ **تم إرسال طلبك بنجاح!**\n\nسيتم مراجعة الطلب من قبل الإدارة، وفي حال قبوله سيتم إضافة المكافأة إلى رصيدك.\n\nشكراً لتعاونك!")
        
        await UserHandlers.show_menu(update, context)


# ==================== خدمة أسعار الصرف ====================

class ExchangeRateService:
    @staticmethod
    async def get_usd_to_egp() -> float:
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.exchangerate-api.com/v4/latest/USD"
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        egp_rate = data.get('rates', {}).get('EGP', 52.0)
                        return egp_rate
        except Exception as e:
            logger.error(f"⚠️ خطأ في جلب سعر الصرف: {e}")
        return Config.USD_TO_EGP


# ==================== أوامر الأدمن ====================

class AdminHandlers:
    @staticmethod
    async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending = db.get_pending_withdrawals_count()
        total_users = db.get_users_count()
        verified_users = db.get_verified_users_count()
        total_withdrawn_egp = db.get_total_withdrawn()
        banned_users = db.get_banned_users_count()
        pending_tasks = db.get_pending_tasks_count()
        
        formatted_withdrawn = currency.format_amount_admin(total_withdrawn_egp)
        
        keyboard = [
            [InlineKeyboardButton("💰 طلبات السحب", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("💵 طلبات بينانس", callback_data="admin_binance_withdrawals")],
            [InlineKeyboardButton("💎 طلبات USDT", callback_data="admin_usdt_withdrawals")],
            [InlineKeyboardButton("🪙 طلبات 1 جنيه", callback_data="admin_one_egp_withdrawals")],
            [InlineKeyboardButton("📱 طلبات مهمات التطبيقات", callback_data="admin_task_requests")],
            [InlineKeyboardButton("➕ إضافة مهمة تطبيق", callback_data="admin_add_task")],
            [InlineKeyboardButton("📋 قائمة المهام", callback_data="admin_list_tasks")],
            [InlineKeyboardButton("🗑️ حذف مهمة", callback_data="admin_delete_task")],
            [InlineKeyboardButton("🚫 المستخدمين المحظورين", callback_data="admin_banned_users")],
            [InlineKeyboardButton("❌ رفض جميع الطلبات", callback_data="reject_all_withdrawals")],
            [InlineKeyboardButton("📢 إشعار للكل", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📢 قنوات الاشتراك", callback_data="admin_channels")],
            [InlineKeyboardButton("⚙️ إعدادات الأسعار", callback_data="admin_prices_settings")],
            [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
        ]
        msg = f"""🔧 **لوحة الأدمن**

👥 المستخدمين: {total_users}
✅ متحققين: {verified_users}
🚫 محظورين: {banned_users}
⏳ طلبات سحب معلقة: {pending}
📱 طلبات مهام معلقة: {pending_tasks}
💰 إجمالي مسحوب: {formatted_withdrawn}
⏱️ مدة الإلغاء: {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة"""
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def admin_task_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض طلبات مهمات التطبيقات المعلقة"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending_completions = db.get_pending_task_completions()
        
        if not pending_completions:
            await query.message.reply_text("📭 لا توجد طلبات مهمات معلقة")
            await query.answer()
            return
        
        for completion in pending_completions:
            user_data = db.get_user(completion['user_id'])
            task = db.get_app_task(completion['task_id'])
            formatted_reward = currency.format_amount(task['reward_egp'], 'EGP') if task else '0'
            
            keyboard = [[
                InlineKeyboardButton("✅ قبول", callback_data=f"admin_approve_task_{completion['id']}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"admin_reject_task_{completion['id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"📱 **طلب مهمة #{completion['id']}**\n"
            msg += f"👤 المستخدم: {user_data.get('first_name', 'Unknown') if user_data else 'Unknown'}\n"
            msg += f"🆔 ID: {completion['user_id']}\n"
            msg += f"📱 المهمة: {task['title'] if task else 'غير معروف'}\n"
            msg += f"💰 المكافأة: {formatted_reward}\n"
            msg += f"⏱️ تم الإرسال: {completion['submitted_at'][:19]}\n"
            msg += f"📸 الصورة مرفقة أعلاه"
            
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=completion['screenshot_file_id'],
                    caption=msg,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                await query.message.reply_text(msg + "\n\n⚠️ تعذر إرسال الصورة", reply_markup=reply_markup, parse_mode='Markdown')
        
        await query.answer()
    
    @staticmethod
    async def admin_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إضافة مهمة تطبيق جديدة"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'adding_task_step': 'title'})
        await query.message.reply_text("📝 **إضافة مهمة تطبيق جديدة**\n\nأرسل **عنوان** المهمة:\n(مثال: تحميل تطبيق XXX)")
        await query.answer()
    
    @staticmethod
    async def admin_list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض قائمة المهام (للأدمن)"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        tasks = db.get_all_app_tasks()
        
        if not tasks:
            await query.message.reply_text("📭 لا توجد مهام حالياً.\n\nاستخدم '➕ إضافة مهمة تطبيق' لإضافة مهمة جديدة.")
            await query.answer()
            return
        
        msg = "📋 **قائمة المهام**\n\n"
        for task in tasks:
            status = "✅ نشطة" if task['is_active'] else "❌ معطلة"
            msg += f"🆔 ID: {task['id']}\n"
            msg += f"📌 العنوان: {task['title']}\n"
            msg += f"💰 المكافأة: {currency.format_amount_admin(task['reward_egp'])}\n"
            msg += f"📊 الحالة: {status}\n"
            msg += "━━━━━━━━━━━━━━━━━\n"
        
        keyboard = [
            [InlineKeyboardButton("🔁 تبديل حالة مهمة", callback_data="admin_toggle_task")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def admin_delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حذف مهمة"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        tasks = db.get_all_app_tasks()
        
        if not tasks:
            await query.message.reply_text("📭 لا توجد مهام لحذفها!")
            await query.answer()
            return
        
        keyboard = []
        for task in tasks:
            keyboard.append([InlineKeyboardButton(f"🗑️ {task['title']}", callback_data=f"admin_delete_task_{task['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text("اختر المهمة للحذف:", reply_markup=reply_markup)
        await query.answer()
    
    @staticmethod
    async def process_delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: int):
        """معالجة حذف المهمة"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        task = db.get_app_task(task_id)
        if task:
            db.delete_app_task(task_id)
            await query.message.reply_text(f"✅ تم حذف المهمة '{task['title']}' بنجاح!")
        else:
            await query.message.reply_text("❌ المهمة غير موجودة!")
        
        await AdminHandlers.admin_panel(update, context)
    
    @staticmethod
    async def admin_toggle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تبديل حالة مهمة (نشطة/معطلة)"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        tasks = db.get_all_app_tasks()
        
        if not tasks:
            await query.message.reply_text("📭 لا توجد مهام لتبديل حالتها!")
            await query.answer()
            return
        
        keyboard = []
        for task in tasks:
            status = "✅ نشطة" if task['is_active'] else "❌ معطلة"
            keyboard.append([InlineKeyboardButton(f"{task['title']} - {status}", callback_data=f"admin_toggle_task_{task['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_list_tasks")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text("اختر المهمة لتبديل حالتها:", reply_markup=reply_markup)
        await query.answer()
    
    @staticmethod
    async def process_toggle_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: int):
        """معالجة تبديل حالة المهمة"""
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        task = db.get_app_task(task_id)
        if task:
            new_status = 0 if task['is_active'] else 1
            db.toggle_task_status(task_id, new_status)
            status_text = "نشطة" if new_status == 1 else "معطلة"
            await query.message.reply_text(f"✅ تم تغيير حالة المهمة '{task['title']}' إلى {status_text}")
        
        await AdminHandlers.admin_list_tasks(update, context)
    
    @staticmethod
    async def process_add_task_step(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """معالجة خطوات إضافة المهمة"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            return
        
        temp_data = db.get_temp_data(user_id)
        step = temp_data.get('adding_task_step') if temp_data else None
        
        if not step:
            return
        
        if step == 'title':
            temp_data['task_title'] = text
            temp_data['adding_task_step'] = 'description'
            db.set_temp_data(user_id, temp_data)
            await update.message.reply_text("📝 أرسل **وصف** المهمة:\n(مثال: قم بتحميل التطبيق وإنشاء حساب)")
        
        elif step == 'description':
            temp_data['task_description'] = text
            temp_data['adding_task_step'] = 'image'
            db.set_temp_data(user_id, temp_data)
            await update.message.reply_text("🖼️ أرسل **صورة** المهمة (كصورة أو اضغط /skip للتخطي):")
        
        elif step == 'image':
            temp_data['task_image'] = text
            temp_data['adding_task_step'] = 'link'
            db.set_temp_data(user_id, temp_data)
            await update.message.reply_text("🔗 أرسل **رابط** التطبيق:\n(مثال: https://t.me/xxx أو رابط تحميل)")
        
        elif step == 'link':
            temp_data['task_link'] = text
            temp_data['adding_task_step'] = 'reward'
            db.set_temp_data(user_id, temp_data)
            await update.message.reply_text("💰 أرسل **قيمة المكافأة** (بالجنيه المصري):\n(مثال: 5)")
        
        elif step == 'reward':
            try:
                reward = float(text)
                if reward <= 0:
                    raise ValueError
                
                task_id = db.add_app_task(
                    title=temp_data['task_title'],
                    description=temp_data['task_description'],
                    image_url=temp_data.get('task_image'),
                    app_link=temp_data.get('task_link'),
                    reward_egp=reward,
                    created_by=user_id
                )
                
                await update.message.reply_text(f"✅ **تم إضافة المهمة بنجاح!**\n\n📌 العنوان: {temp_data['task_title']}\n💰 المكافأة: {currency.format_amount_admin(reward)}\n🆔 رقم المهمة: {task_id}")
                
                db.delete_temp_data(user_id)
                
            except:
                await update.message.reply_text("❌ قيمة غير صالحة! أرسل رقماً موجباً للمكافأة:")
    
    @staticmethod
    async def process_task_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة صورة المهمة المرسلة"""
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            return
        
        temp_data = db.get_temp_data(user_id)
        if not temp_data or temp_data.get('adding_task_step') != 'image':
            return
        
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        temp_data['task_image'] = file_id
        temp_data['adding_task_step'] = 'link'
        db.set_temp_data(user_id, temp_data)
        
        await update.message.reply_text("🔗 أرسل **رابط** التطبيق:\n(مثال: https://t.me/xxx أو رابط تحميل)")
    
    @staticmethod
    async def handle_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة قبول أو رفض طلب مهمة"""
        query = update.callback_query
        data = query.data
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        try:
            parts = data.split('_')
            if len(parts) >= 4:
                action = parts[1]
                completion_id = int(parts[3])
            else:
                await query.answer("خطأ في البيانات")
                return
        except Exception as e:
            logger.error(f"Error parsing task action: {e}")
            await query.answer("خطأ في البيانات")
            return
        
        completion = db.get_task_completion(completion_id)
        if not completion or completion['status'] != 'pending':
            await query.answer("الطلب تم معالجته بالفعل!")
            return
        
        if action == 'approve':
            task = db.get_app_task(completion['task_id'])
            if task:
                db.add_balance(completion['user_id'], task['reward_egp'], True)
                db.complete_task_completion(completion_id, task['reward_egp'])
                db.update_user_task_completion(completion['user_id'], completion['task_id'])
                
                user_currency = 'EGP'
                user_data = db.get_user(completion['user_id'])
                if user_data:
                    user_currency = user_data.get('display_currency', 'EGP')
                
                formatted_reward = currency.format_amount(task['reward_egp'], user_currency)
                new_balance = user_data.get('balance_egp', 0) + task['reward_egp'] if user_data else task['reward_egp']
                formatted_balance = currency.format_amount(new_balance, user_currency)
                
                msg = f"✅ **تم قبول مهمتك!**\n\n📱 المهمة: {task['title']}\n💰 المكافأة: {formatted_reward}\n📊 رصيدك الحالي: {formatted_balance}\n\nشكراً لتعاونك!"
                
                try:
                    await context.bot.send_message(completion['user_id'], msg, parse_mode='Markdown')
                except:
                    pass
                
                await query.message.edit_text(f"✅ تم قبول طلب #{completion_id} وإضافة {currency.format_amount_admin(task['reward_egp'])} للمستخدم")
            else:
                await query.message.edit_text(f"❌ المهمة غير موجودة!")
        
        elif action == 'reject':
            db.reject_task_completion(completion_id, "تم رفض الطلب من قبل الإدارة")
            
            msg = f"❌ **تم رفض مهمتك!**\n\n⚠️ السبب: الصورة غير مطابقة أو غير واضحة.\n\n📌 يمكنك إعادة المحاولة من جديد."
            
            try:
                await context.bot.send_message(completion['user_id'], msg, parse_mode='Markdown')
            except:
                pass
            
            await query.message.edit_text(f"❌ تم رفض طلب #{completion_id}")
        
        await query.answer()
    
    @staticmethod
    async def admin_banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        banned_users = db.get_banned_users()
        
        if not banned_users:
            await query.message.reply_text("📭 لا يوجد مستخدمين محظورين")
            await query.answer()
            return
        
        msg = "🚫 **المستخدمين المحظورين**\n\n"
        for user in banned_users:
            msg += f"👤 ID: {user['user_id']}\n"
            msg += f"📝 الاسم: {user.get('first_name', 'Unknown')}\n"
            msg += f"⚠️ السبب: {user.get('ban_reason', 'غير محدد')}\n"
            msg += f"📅 تاريخ الحظر: {user.get('banned_at', 'غير محدد')[:19]}\n"
            msg += "━━━━━━━━━━━━━━━━━━━━━\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def admin_prices_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        msg = f"""⚙️ **إعدادات الأسعار** (جميع القيم بالجنيه المصري)

🎁 الهدية اليومية: {currency.format_amount_admin(Config.DAILY_BONUS_EGP)}
👥 مكافأة الدعوة: {currency.format_amount_admin(Config.REFERRAL_BONUS_EGP)}
💰 أول سحب: {currency.format_amount_admin(Config.FIRST_WITHDRAWAL_EGP)}
💰 السحب الثاني: {currency.format_amount_admin(Config.SECOND_WITHDRAWAL_EGP)}

🎡 **عجلة الحظ:**
• الحد الأدنى: {Config.MIN_WHEEL_REWARD} جنيه
• الحد الأقصى: {Config.MAX_WHEEL_REWARD} جنيه

🎮 **لعبة العب واربح:**
• الحد الأدنى: {Config.MIN_GAME_REWARD} جنيه
• الحد الأقصى: {Config.MAX_GAME_REWARD} جنيه

⏱️ مدة إلغاء الطلب: {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة
💡 سعر الصرف: 1 دولار = {Config.USD_TO_EGP:.2f} جنيه"""
        
        keyboard = [
            [InlineKeyboardButton("🎁 تغيير الهدية اليومية", callback_data="set_daily")],
            [InlineKeyboardButton("👥 تغيير مكافأة الدعوة", callback_data="set_referral")],
            [InlineKeyboardButton("💰 تغيير حد أول سحب", callback_data="set_first")],
            [InlineKeyboardButton("💰 تغيير حد السحب الثاني", callback_data="set_second")],
            [InlineKeyboardButton("🎡 تغيير عجلة الحظ", callback_data="set_wheel_range")],
            [InlineKeyboardButton("🎮 تغيير لعبة العب واربح", callback_data="set_game_range")],
            [InlineKeyboardButton("⏱️ تغيير مدة الإلغاء", callback_data="set_cancel_time")],
            [InlineKeyboardButton("💵 تحديث سعر الصرف", callback_data="update_exchange")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def admin_one_egp_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending = db.get_withdrawals_by_amount(Config.FIRST_WITHDRAWAL_EGP, 'pending')
        
        if not pending:
            await query.message.reply_text("📭 مفيش طلبات 1 جنيه معلقة")
            await query.answer()
            return
        
        for w in pending:
            user_data = db.get_user(w['user_id'])
            formatted_amount = currency.format_amount_admin(w.get('amount_egp', 0))
            
            keyboard = [[
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{w['id']}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{w['id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"🪙 طلب 1 جنيه #{w['id']}\n👤 {user_data.get('first_name', 'Unknown') if user_data else 'Unknown'}\n💵 {formatted_amount}\n💳 {w['method']}"
            if w.get('phone'):
                msg += f"\n📱 {w['phone']}"
            if w.get('binance_id'):
                msg += f"\n🆔 {w['binance_id']}"
            if w.get('usdt_address'):
                msg += f"\n💎 {w['usdt_address']}"
            msg += f"\n⏱️ تم الإنشاء: {w['created_at'][:19]}"
            
            await query.message.reply_text(msg, reply_markup=reply_markup)
        
        await query.answer()
    
    @staticmethod
    async def reject_all_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending_withdrawals = db.get_all_withdrawals('pending')
        
        if not pending_withdrawals:
            await query.message.reply_text("📭 لا توجد طلبات معلقة لرفضها!")
            await query.answer()
            return
        
        rejected_count = 0
        
        for w in pending_withdrawals:
            w_id = w['id']
            user_id = w['user_id']
            amount_egp = w.get('amount_egp', 0)
            
            db.update_withdrawal_status(w_id, 'rejected')
            db.refund_balance(user_id, amount_egp)
            rejected_count += 1
            
            try:
                user_data = db.get_user(user_id)
                user_currency = user_data.get('display_currency', 'EGP') if user_data else 'EGP'
                user_formatted_amount = currency.format_amount(amount_egp, user_currency)
                msg = f"❌ تم رفض طلب السحب #{w_id} من قبل الإدارة\n💰 تم إعادة المبلغ {user_formatted_amount} إلى رصيدك\n\n📌 يمكنك تقديم طلب سحب جديد"
                await context.bot.send_message(user_id, msg)
            except Exception as e:
                logger.error(f"خطأ في إرسال إشعار الرفض للمستخدم {user_id}: {e}")
        
        await query.message.reply_text(f"✅ تم رفض {rejected_count} طلب سحب وإعادة المبالغ للمستخدمين")
        await query.answer(f"تم رفض {rejected_count} طلب")
        await AdminHandlers.admin_panel(update, context)
    
    @staticmethod
    async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending = [w for w in db.get_all_withdrawals('pending')]
        
        if not pending:
            await query.message.reply_text("📭 مفيش طلبات معلقة")
            await query.answer()
            return
        
        for w in pending:
            user_data = db.get_user(w['user_id'])
            formatted_amount = currency.format_amount_admin(w.get('amount_egp', 0))
            
            keyboard = [[
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{w['id']}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{w['id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"💰 طلب #{w['id']}\n👤 {user_data.get('first_name', 'Unknown') if user_data else 'Unknown'}\n💵 {formatted_amount}\n💳 {w['method']}"
            if w.get('phone'):
                msg += f"\n📱 {w['phone']}"
            if w.get('binance_id'):
                msg += f"\n🆔 {w['binance_id']}"
            if w.get('usdt_address'):
                msg += f"\n💎 {w['usdt_address']}"
            msg += f"\n⏱️ تم الإنشاء: {w['created_at'][:19]}"
            
            await query.message.reply_text(msg, reply_markup=reply_markup)
        
        await query.answer()
    
    @staticmethod
    async def admin_binance_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending = [w for w in db.get_all_withdrawals('pending') if w['method'] == 'بينانس']
        
        if not pending:
            await query.message.reply_text("📭 مفيش طلبات سحب بينانس معلقة")
            await query.answer()
            return
        
        for w in pending:
            user_data = db.get_user(w['user_id'])
            formatted_amount = currency.format_amount_admin(w.get('amount_egp', 0))
            
            keyboard = [[
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{w['id']}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{w['id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"🟡 طلب بينانس #{w['id']}\n👤 {user_data.get('first_name', 'Unknown') if user_data else 'Unknown'}\n💵 {formatted_amount}\n🆔 {w.get('binance_id', 'N/A')}\n⏱️ تم الإنشاء: {w['created_at'][:19]}"
            
            await query.message.reply_text(msg, reply_markup=reply_markup)
        
        await query.answer()
    
    @staticmethod
    async def admin_usdt_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        pending = [w for w in db.get_all_withdrawals('pending') if w['method'] == 'USDT (TRC20)']
        
        if not pending:
            await query.message.reply_text("📭 مفيش طلبات سحب USDT معلقة")
            await query.answer()
            return
        
        for w in pending:
            user_data = db.get_user(w['user_id'])
            formatted_amount = currency.format_amount_admin(w.get('amount_egp', 0))
            
            keyboard = [[
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{w['id']}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{w['id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = f"💎 طلب USDT #{w['id']}\n👤 {user_data.get('first_name', 'Unknown') if user_data else 'Unknown'}\n💵 {formatted_amount}\n💎 {w.get('usdt_address', 'N/A')}\n⏱️ تم الإنشاء: {w['created_at'][:19]}"
            
            await query.message.reply_text(msg, reply_markup=reply_markup)
        
        await query.answer()
    
    @staticmethod
    async def set_cancel_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'cancel_time'})
        await query.message.reply_text("📝 أرسل مدة الإلغاء الجديدة بالدقائق:\n\nمثال: 5 (لـ 5 دقائق)\n\n⚠️ ملاحظة: الحد الأدنى 1 دقيقة، الحد الأقصى 60 دقيقة")
        await query.answer()
    
    @staticmethod
    async def set_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'daily_bonus'})
        await query.message.reply_text("📝 أرسل قيمة الهدية اليومية الجديدة (بالجنيه المصري):\n\nمثال: 5")
        await query.answer()
    
    @staticmethod
    async def set_referral_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'referral_bonus'})
        await query.message.reply_text("📝 أرسل قيمة مكافأة الدعوة الجديدة (بالجنيه المصري):\n\nمثال: 10")
        await query.answer()
    
    @staticmethod
    async def set_first_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'first_withdrawal'})
        await query.message.reply_text("📝 أرسل الحد الأدنى الجديد لأول سحب (بالجنيه المصري):\n\nمثال: 1")
        await query.answer()
    
    @staticmethod
    async def set_second_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'second_withdrawal'})
        await query.message.reply_text("📝 أرسل الحد الأدنى الجديد للسحب الثاني (بالجنيه المصري):\n\nمثال: 100")
        await query.answer()
    
    @staticmethod
    async def set_wheel_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'wheel_range'})
        await query.message.reply_text("📝 أرسل نطاق عجلة الحظ الجديد:\n\nمثال: `1,3` (الحد الأدنى,الحد الأقصى)")
        await query.answer()
    
    @staticmethod
    async def set_game_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        db.set_temp_data(query.from_user.id, {'setting': 'game_range'})
        await query.message.reply_text("📝 أرسل نطاق لعبة العب واربح الجديد:\n\nمثال: `1,3` (الحد الأدنى,الحد الأقصى)")
        await query.answer()
    
    @staticmethod
    async def process_admin_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, value_str: str):
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            return
        
        temp_data = db.get_temp_data(user_id)
        setting = temp_data.get('setting') if temp_data else None
        
        try:
            value = float(value_str)
            if value <= 0:
                raise ValueError
            
            if setting == 'cancel_time':
                value = int(value)
                if value < 1 or value > 60:
                    await update.message.reply_text("❌ مدة الإلغاء يجب أن تكون بين 1 و 60 دقيقة!")
                    return
        except:
            await update.message.reply_text("❌ قيمة غير صالحة! أرسل رقماً موجباً.")
            return
        
        if setting == 'daily_bonus':
            Config.DAILY_BONUS_EGP = value
            db.set_setting('daily_bonus_egp', str(value))
            await update.message.reply_text(f"✅ تم تحديث الهدية اليومية إلى: {currency.format_amount_admin(value)}")
        
        elif setting == 'referral_bonus':
            Config.REFERRAL_BONUS_EGP = value
            db.set_setting('referral_bonus_egp', str(value))
            await update.message.reply_text(f"✅ تم تحديث مكافأة الدعوة إلى: {currency.format_amount_admin(value)}")
        
        elif setting == 'first_withdrawal':
            Config.FIRST_WITHDRAWAL_EGP = value
            db.set_setting('first_withdrawal_egp', str(value))
            await update.message.reply_text(f"✅ تم تحديث حد أول سحب إلى: {currency.format_amount_admin(value)}")
        
        elif setting == 'second_withdrawal':
            Config.SECOND_WITHDRAWAL_EGP = value
            db.set_setting('second_withdrawal_egp', str(value))
            await update.message.reply_text(f"✅ تم تحديث حد السحب الثاني إلى: {currency.format_amount_admin(value)}")
        
        elif setting == 'cancel_time':
            Config.CANCEL_WITHDRAWAL_MINUTES = int(value)
            db.set_setting('cancel_withdrawal_minutes', str(value))
            await update.message.reply_text(f"✅ تم تحديث مدة إلغاء الطلب إلى: {value} دقيقة")
        
        elif setting == 'wheel_range':
            parts = value_str.split(',')
            if len(parts) == 2:
                try:
                    min_val = int(parts[0].strip())
                    max_val = int(parts[1].strip())
                    if min_val > 0 and max_val > min_val:
                        Config.MIN_WHEEL_REWARD = min_val
                        Config.MAX_WHEEL_REWARD = max_val
                        db.set_setting('min_wheel_reward', str(min_val))
                        db.set_setting('max_wheel_reward', str(max_val))
                        await update.message.reply_text(f"✅ تم تحديث عجلة الحظ إلى: {min_val}-{max_val} جنيه")
                    else:
                        await update.message.reply_text("❌ الحد الأقصى يجب أن يكون أكبر من الحد الأدنى!")
                except:
                    await update.message.reply_text("❌ قيم غير صالحة!")
            else:
                await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `الحد_الأدنى,الحد_الأقصى`")
        
        elif setting == 'game_range':
            parts = value_str.split(',')
            if len(parts) == 2:
                try:
                    min_val = int(parts[0].strip())
                    max_val = int(parts[1].strip())
                    if min_val > 0 and max_val > min_val:
                        Config.MIN_GAME_REWARD = min_val
                        Config.MAX_GAME_REWARD = max_val
                        db.set_setting('min_game_reward', str(min_val))
                        db.set_setting('max_game_reward', str(max_val))
                        await update.message.reply_text(f"✅ تم تحديث لعبة العب واربح إلى: {min_val}-{max_val} جنيه")
                    else:
                        await update.message.reply_text("❌ الحد الأقصى يجب أن يكون أكبر من الحد الأدنى!")
                except:
                    await update.message.reply_text("❌ قيم غير صالحة!")
            else:
                await update.message.reply_text("❌ الصيغة غير صحيحة! استخدم: `الحد_الأدنى,الحد_الأقصى`")
        
        db.delete_temp_data(user_id)
    
    @staticmethod
    async def update_exchange_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        await query.message.reply_text("⏳ جاري جلب سعر الصرف...")
        
        new_rate = await ExchangeRateService.get_usd_to_egp()
        Config.USD_TO_EGP = new_rate
        db.set_setting('usd_to_egp', str(new_rate))
        
        await query.message.reply_text(f"✅ تم تحديث سعر الصرف: 1 دولار = {new_rate:.2f} جنيه")
        await query.answer()
        await AdminHandlers.admin_prices_settings(update, context)
    
    @staticmethod
    async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        total_users = db.get_users_count()
        await query.message.reply_text(f"📢 أرسل الرسالة اللي عايز توصلها للكل\n👥 عدد المستخدمين: {total_users}")
        
        db.set_temp_data(query.from_user.id, {'broadcast_mode': True})
        await query.answer()
    
    @staticmethod
    async def admin_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        channels = db.get_channels()
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
            [InlineKeyboardButton("➖ حذف قناة", callback_data="remove_channel")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin")]
        ]
        msg = "📢 **قنوات الاشتراك الإجباري**\n\n"
        if channels:
            msg += "القنوات الحالية:\n"
            for ch in channels:
                msg += f"• {ch['name']} (`{ch['id']}`)\n"
        else:
            msg += "⚠️ لا توجد قنوات حالياً\n"
        msg += f"\n✅ الحالة: {'مفعل' if Config.FORCE_SUB_ENABLED else 'معطل'}"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        await query.message.reply_text(
            "📢 **إضافة قناة جديدة**\n\nأرسل معرف القناة:\n`@channel_username`\n\n📌 يجب أن يكون البوت أدمن في القناة",
            parse_mode='Markdown'
        )
        db.set_temp_data(query.from_user.id, {'adding_channel': True})
        await query.answer()
    
    @staticmethod
    async def process_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_input: str):
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            return
        
        channel_input = channel_input.strip()
        
        if channel_input.startswith('@'):
            channel_id = channel_input
        else:
            channel_id = channel_input
        
        try:
            chat = await context.bot.get_chat(chat_id=channel_id)
            channel_name = chat.title
            channel_link = f"https://t.me/{chat.username}" if chat.username else None
            
            if db.add_channel(channel_id, channel_name, channel_link):
                await update.message.reply_text(f"✅ تم إضافة القناة {channel_name} بنجاح!")
            else:
                await update.message.reply_text("❌ القناة موجودة بالفعل!")
        except Exception as e:
            await update.message.reply_text(
                f"❌ حدث خطأ!\n\nتأكد من:\n• صحة معرف القناة\n• أن البوت أدمن في القناة\n\nالخطأ: {e}"
            )
        
        db.delete_temp_data(user_id)
    
    @staticmethod
    async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        channels = db.get_channels()
        
        if not channels:
            await query.message.reply_text("⚠️ لا توجد قنوات للحذف")
            await query.answer()
            return
        
        keyboard = []
        for ch in channels:
            keyboard.append([InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"remove_ch_{ch['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_channels")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text("اختر القناة للحذف:", reply_markup=reply_markup)
        await query.answer()
    
    @staticmethod
    async def process_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_id: str):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        if db.remove_channel(channel_id):
            await query.message.reply_text("✅ تم حذف القناة بنجاح!")
        else:
            await query.message.reply_text("❌ القناة غير موجودة!")
        
        await AdminHandlers.admin_channels(update, context)
    
    @staticmethod
    async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        total = db.get_users_count()
        verified = db.get_verified_users_count()
        pending = db.get_pending_withdrawals_count()
        all_withdrawals = db.get_all_withdrawals()
        approved = len([w for w in all_withdrawals if w['status'] == 'approved'])
        cancelled = len([w for w in all_withdrawals if w['status'] == 'cancelled'])
        total_withdrawn_egp = db.get_total_withdrawn()
        total_earnings_egp = sum(u.get('total_earnings_egp', 0) for u in db.get_all_users())
        total_refs = len(db.get_all_referrals())
        banned = db.get_banned_users_count()
        total_tasks_completed = db.get_total_tasks_completed()
        total_task_earnings = db.get_total_task_earnings()
        
        formatted_withdrawn = currency.format_amount_admin(total_withdrawn_egp)
        formatted_earnings = currency.format_amount_admin(total_earnings_egp)
        formatted_task_earnings = currency.format_amount_admin(total_task_earnings)
        
        msg = f"""📊 **إحصائيات البوت**

👥 إجمالي المستخدمين: {total}
✅ المستخدمين المتحققين: {verified}
🚫 المستخدمين المحظورين: {banned}
👥 الدعوات: {total_refs}
💰 طلبات السحب: {len(all_withdrawals)}
⏳ معلقة: {pending}
✅ مقبولة: {approved}
❌ ملغية: {cancelled}
💵 إجمالي مسحوب: {formatted_withdrawn}
🏆 إجمالي أرباح: {formatted_earnings}
📱 مهام مكتملة: {total_tasks_completed}
💰 أرباح المهام: {formatted_task_earnings}"""
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
        await query.answer()
    
    @staticmethod
    async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        
        if query.from_user.id not in Config.ADMIN_IDS:
            await query.answer("غير مصرح", show_alert=True)
            return
        
        if data.startswith("approve_") or data.startswith("reject_"):
            try:
                parts = data.split('_')
                if len(parts) == 2 and parts[1].isdigit():
                    action, w_id = parts[0], int(parts[1])
                    
                    w = db.get_withdrawal(w_id)
                    
                    if not w:
                        await query.answer("الطلب مش موجود")
                        return
                    
                    if w['status'] != 'pending':
                        await query.answer(f"الطلب {w['status']} بالفعل!")
                        return
                    
                    formatted_amount = currency.format_amount_admin(w.get('amount_egp', 0))
                    
                    if action == 'approve':
                        db.update_withdrawal_status(w_id, 'approved')
                        await query.message.edit_text(f"✅ تم قبول طلب #{w_id}")
                        
                        try:
                            user_data = db.get_user(w['user_id'])
                            user_currency = user_data.get('display_currency', 'EGP')
                            user_formatted_amount = currency.format_amount(w.get('amount_egp', 0), user_currency)
                            
                            msg = f"✅ تم قبول طلب السحب #{w_id}!\n💰 المبلغ: {user_formatted_amount}\n💳 الطريقة: {w['method']}\n\n📌 تم تحويل المبلغ بنجاح."
                            
                            if w.get('phone'):
                                msg += f"\n📱 {w['phone']}"
                            elif w.get('binance_id'):
                                msg += f"\n🆔 {w['binance_id']}"
                            elif w.get('usdt_address'):
                                msg += f"\n💎 {w['usdt_address']}"
                            
                            await context.bot.send_message(w['user_id'], msg)
                        except Exception as e:
                            logger.error(f"خطأ في إرسال رسالة القبول: {e}")
                    else:
                        db.update_withdrawal_status(w_id, 'rejected')
                        db.refund_balance(w['user_id'], w.get('amount_egp', 0))
                        await query.message.edit_text(f"❌ تم رفض طلب #{w_id}")
                        
                        try:
                            user_data = db.get_user(w['user_id'])
                            user_currency = user_data.get('display_currency', 'EGP')
                            user_formatted_amount = currency.format_amount(w.get('amount_egp', 0), user_currency)
                            msg = f"❌ تم رفض طلب السحب #{w_id}\n💰 تم إعادة المبلغ {user_formatted_amount} إلى رصيدك\n\n📌 يمكنك تقديم طلب سحب جديد"
                            await context.bot.send_message(w['user_id'], msg)
                        except Exception as e:
                            logger.error(f"خطأ في إرسال رسالة الرفض: {e}")
                    
                    await query.answer()
                    return
            except:
                pass
        
        elif data.startswith("admin_toggle_task_"):
            task_id = int(data.replace("admin_toggle_task_", ""))
            await AdminHandlers.process_toggle_task(update, context, task_id)
            return
        
        elif data.startswith("admin_delete_task_"):
            task_id = int(data.replace("admin_delete_task_", ""))
            await AdminHandlers.process_delete_task(update, context, task_id)
            return
        
        elif data.startswith("admin_approve_task_") or data.startswith("admin_reject_task_"):
            await AdminHandlers.handle_task_action(update, context)
            return


# ==================== المعالج الرئيسي ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    data = query.data
    
    if data == "check_sub":
        is_subscribed, not_subscribed = await helpers.check_force_sub(query.from_user.id, context)
        if is_subscribed:
            await query.message.reply_text("✅ تم التحقق بنجاح! يمكنك استخدام البوت الآن.")
            await UserHandlers.show_menu(update, context)
        else:
            message = "⚠️ **لا تزال غير مشترك في القنوات التالية:**\n\n"
            for channel in not_subscribed:
                message += f"• {channel['name']}\n"
            message += "\n✅ بعد الاشتراك، اضغط على زر التحقق"
            keyboard = helpers.create_force_sub_keyboard(not_subscribed)
            await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
        await query.answer()
    
    elif data == "back":
        await UserHandlers.show_menu(update, context)
    elif data == "back_verification":
        await UserHandlers.start_verification(update, context)
    elif data == "daily":
        await UserHandlers.daily_bonus(update, context)
    elif data == "daily_tasks":
        await UserHandlers.daily_tasks_menu(update, context)
    elif data == "wheel_of_fortune":
        await UserHandlers.wheel_of_fortune(update, context)
    elif data == "play_and_win":
        await UserHandlers.play_and_win(update, context)
    elif data == "referral":
        await UserHandlers.referral_system(update, context)
    elif data == "withdraw":
        await UserHandlers.withdraw_menu(update, context)
    elif data == "account":
        await UserHandlers.account_menu(update, context)
    elif data == "bot_terms":
        await UserHandlers.bot_terms(update, context)
    elif data == "bot_info":
        await UserHandlers.bot_info(update, context)
    elif data == "settings_menu":
        await UserHandlers.settings_menu(update, context)
    elif data == "change_lang":
        await UserHandlers.change_language(update, context)
    elif data == "change_currency":
        await UserHandlers.change_currency(update, context)
    elif data == "verification_help":
        await UserHandlers.verification_help(update, context)
    elif data == "new_question":
        await UserHandlers.new_question(update, context)
    elif data == "admin":
        await AdminHandlers.admin_panel(update, context)
    elif data == "admin_withdrawals":
        await AdminHandlers.admin_withdrawals(update, context)
    elif data == "admin_binance_withdrawals":
        await AdminHandlers.admin_binance_withdrawals(update, context)
    elif data == "admin_usdt_withdrawals":
        await AdminHandlers.admin_usdt_withdrawals(update, context)
    elif data == "admin_one_egp_withdrawals":
        await AdminHandlers.admin_one_egp_withdrawals(update, context)
    elif data == "admin_banned_users":
        await AdminHandlers.admin_banned_users(update, context)
    elif data == "reject_all_withdrawals":
        await AdminHandlers.reject_all_withdrawals(update, context)
    elif data == "admin_broadcast":
        await AdminHandlers.admin_broadcast(update, context)
    elif data == "admin_channels":
        await AdminHandlers.admin_channels(update, context)
    elif data == "admin_prices_settings":
        await AdminHandlers.admin_prices_settings(update, context)
    elif data == "admin_stats":
        await AdminHandlers.admin_stats(update, context)
    elif data == "set_daily":
        await AdminHandlers.set_daily_bonus(update, context)
    elif data == "set_referral":
        await AdminHandlers.set_referral_bonus(update, context)
    elif data == "set_first":
        await AdminHandlers.set_first_withdrawal(update, context)
    elif data == "set_second":
        await AdminHandlers.set_second_withdrawal(update, context)
    elif data == "set_wheel_range":
        await AdminHandlers.set_wheel_range(update, context)
    elif data == "set_game_range":
        await AdminHandlers.set_game_range(update, context)
    elif data == "set_cancel_time":
        await AdminHandlers.set_cancel_time(update, context)
    elif data == "update_exchange":
        await AdminHandlers.update_exchange_rate(update, context)
    elif data == "add_channel":
        await AdminHandlers.add_channel(update, context)
    elif data == "remove_channel":
        await AdminHandlers.remove_channel(update, context)
    elif data == "admin_task_requests":
        await AdminHandlers.admin_task_requests(update, context)
    elif data == "admin_add_task":
        await AdminHandlers.admin_add_task(update, context)
    elif data == "admin_list_tasks":
        await AdminHandlers.admin_list_tasks(update, context)
    elif data == "admin_delete_task":
        await AdminHandlers.admin_delete_task(update, context)
    elif data == "admin_toggle_task":
        await AdminHandlers.admin_toggle_task(update, context)
    elif data == "app_tasks_menu":
        await UserHandlers.app_tasks_menu(update, context)
    elif data.startswith("game_box_"):
        box_num = int(data.replace("game_box_", ""))
        await UserHandlers.game_box_selected(update, context, box_num)
    elif data.startswith("withdraw_"):
        method = data.replace("withdraw_", "")
        if method == "binance":
            await UserHandlers.request_binance_id(update, context)
        elif method == "usdt":
            await UserHandlers.request_usdt_address(update, context)
        else:
            await UserHandlers.request_phone(update, context, method)
    elif data == "cancel_withdrawal":
        await UserHandlers.cancel_withdrawal(update, context)
    elif data.startswith("remove_ch_"):
        channel_id = data.replace("remove_ch_", "")
        await AdminHandlers.process_remove_channel(update, context, channel_id)
    else:
        await AdminHandlers.handle_admin_action(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل النصية"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if db.is_user_banned(user_id):
        await update.message.reply_text("🚫 **تم حظر حسابك!**\n\nلقد تم حظرك بسبب مخالفة شروط الاستخدام.\n\nللإستفسار، تواصل مع الدعم الفني.", parse_mode='Markdown')
        return
    
    temp_data = db.get_temp_data(user_id)
    
    if temp_data and temp_data.get('awaiting_verification'):
        await UserHandlers.verify_user(update, context, text)
        return
    
    if temp_data and temp_data.get('waiting_phone'):
        await UserHandlers.process_withdrawal(update, context, phone=text)
        return
    
    if temp_data and temp_data.get('waiting_binance_id'):
        await UserHandlers.process_withdrawal(update, context, binance_id=text)
        return
    
    if temp_data and temp_data.get('waiting_usdt_address'):
        await UserHandlers.process_withdrawal(update, context, usdt_address=text)
        return
    
    if temp_data and temp_data.get('adding_channel') and user_id in Config.ADMIN_IDS:
        await AdminHandlers.process_add_channel(update, context, text)
        return
    
    if temp_data and temp_data.get('setting') and user_id in Config.ADMIN_IDS:
        await AdminHandlers.process_admin_setting(update, context, text)
        return
    
    if temp_data and temp_data.get('broadcast_mode') and user_id in Config.ADMIN_IDS:
        msg = text
        success = 0
        fail = 0
        all_users = db.get_all_users()
        
        await update.message.reply_text(f"⏳ جاري الإرسال لـ {len(all_users)} مستخدم...")
        
        for user in all_users:
            if db.is_user_banned(user['user_id']):
                continue
            try:
                await context.bot.send_message(user['user_id'], f"📢 إشعار من الإدارة\n\n{msg}")
                success += 1
                await asyncio.sleep(0.05)
            except:
                fail += 1
        
        await update.message.reply_text(f"✅ تم الإرسال\n✅ نجح: {success}\n❌ فشل: {fail}")
        db.delete_temp_data(user_id)
        return
    
    if temp_data and temp_data.get('adding_task_step') and user_id in Config.ADMIN_IDS:
        await AdminHandlers.process_add_task_step(update, context, text)
        return
    
    user_data = db.get_user(user_id)
    if user_data and user_data.get('verified', False):
        await update.message.reply_text("❓ من فضلك استخدم الأزرار للتنقل في البوت.")
    else:
        await UserHandlers.start_verification(update, context)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الصور"""
    user_id = update.effective_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data and temp_data.get('adding_task_step') == 'image' and user_id in Config.ADMIN_IDS:
        await AdminHandlers.process_task_image(update, context)
        return
    
    if temp_data and temp_data.get('current_task_id'):
        await UserHandlers.process_task_screenshot(update, context)
        return


# ==================== تشغيل البوت ====================

async def set_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "بدء استخدام البوت"),
        BotCommand("admin", "لوحة التحكم"),
    ])


def main():
    print("=" * 60)
    print("🚀 ربحي بوت - نظام ربح متكامل مع مهمات التطبيقات")
    print("📝 الإصدار: 14.0")
    print("✨ التعديلات الجديدة:")
    print("   • ✅ إصلاح قبول/رفض مهام التطبيقات")
    print("   • ✅ إضافة خاصية حذف المهام")
    print("   • ✅ إزالة خاصية 'غير متاح' من المهام اليومية")
    print("   • ✅ مهمات التطبيقات تظهر مهمة واحدة تختفي بعد التنفيذ")
    print("   • ✅ عجلة الحظ: 1-3 جنيه")
    print("   • ✅ العب واربح: 1-3 جنيه")
    print(f"👑 الأدمن: {Config.ADMIN_IDS[0]}")
    print("=" * 60)
    
    cancel_time = db.get_setting('cancel_withdrawal_minutes', '1')
    Config.CANCEL_WITHDRAWAL_MINUTES = int(cancel_time)
    
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", UserHandlers.start))
    app.add_handler(CommandHandler("admin", AdminHandlers.admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    app.post_init = set_commands
    
    print("✅ البوت يعمل الآن...")
    print(f"📌 قاعدة البيانات: Reb7y.db")
    print(f"⏱️ مدة إلغاء الطلب: {Config.CANCEL_WITHDRAWAL_MINUTES} دقيقة")
    print("📌 جميع التعديلات تمت بنجاح!")
    
    app.run_polling()


if __name__ == '__main__':
    main()
