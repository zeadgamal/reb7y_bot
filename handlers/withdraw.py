"""
Withdrawal Handler
"""
import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.user_service import get_user
from services.withdrawal_service import (
    create_withdrawal, get_user_withdrawals,
    get_user_withdrawal_count, get_payment_methods
)
from services.settings_service import get_first_withdraw_min, get_next_withdraw_min
from keyboards.keyboards import (
    payment_methods_keyboard, withdrawal_confirm_keyboard,
    back_keyboard, cancel_keyboard
)
from utils.utils import format_balance
from config import config

logger = logging.getLogger(__name__)
router = Router()


class WithdrawState(StatesGroup):
    waiting_amount = State()
    waiting_payment_method = State()
    waiting_account_details = State()
    waiting_confirm = State()


@router.message(F.text == "💸 سحب الأرباح")
async def withdraw_menu_handler(message: Message):
    await show_withdraw_menu(message)


@router.callback_query(F.data == "withdraw_menu")
async def withdraw_menu_callback(callback: CallbackQuery):
    await show_withdraw_menu(callback.message)
    await callback.answer()


async def show_withdraw_menu(message: Message):
    from services.withdrawal_service import get_user_withdrawals
    user = await get_user(message.from_user.id if hasattr(message, 'from_user') else message.chat.id)
    if not user:
        await message.answer("يرجى استخدام /start أولاً")
        return

    user_id = user['user_id']
    balance = float(user.get('balance', 0))
    approved_count = await get_user_withdrawal_count(user_id)
    first_min = await get_first_withdraw_min()
    next_min = await get_next_withdraw_min()
    min_amount = first_min if approved_count == 0 else next_min

    recent_wds = await get_user_withdrawals(user_id)
    pending = [w for w in recent_wds if w['status'] == 'pending']

    text = (
        f"💸 **سحب الأرباح**\n\n"
        f"💰 رصيدك المتاح: **{format_balance(balance)}**\n"
        f"📊 الحد الأدنى للسحب: **{format_balance(min_amount)}**\n\n"
    )

    if pending:
        text += f"⏳ لديك **{len(pending)}** طلب سحب معلق\n\n"

    if recent_wds:
        text += "📋 **آخر طلبات السحب:**\n"
        for wd in recent_wds[:3]:
            status_emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}.get(wd['status'], '❓')
            text += f"{status_emoji} {wd['order_id']} — {format_balance(wd['amount'])}\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    if balance >= min_amount:
        builder.row(InlineKeyboardButton(text="💸 طلب سحب جديد", callback_data="start_withdraw"))
    builder.row(InlineKeyboardButton(text="📜 جميع طلباتي", callback_data="my_withdrawals"))

    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@router.callback_query(F.data == "start_withdraw")
async def start_withdraw(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)
    approved_count = await get_user_withdrawal_count(callback.from_user.id)
    first_min = await get_first_withdraw_min()
    next_min = await get_next_withdraw_min()
    min_amount = first_min if approved_count == 0 else next_min
    balance = float(user.get('balance', 0))

    await state.set_state(WithdrawState.waiting_amount)
    await state.update_data(min_amount=min_amount, balance=balance)

    await callback.message.edit_text(
        f"💸 **طلب سحب جديد**\n\n"
        f"💰 رصيدك: **{format_balance(balance)}**\n"
        f"📊 الحد الأدنى: **{format_balance(min_amount)}**\n\n"
        f"أدخل المبلغ الذي تريد سحبه:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(WithdrawState.waiting_amount)
async def handle_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(',', '.'))
    except ValueError:
        await message.answer("❌ أدخل رقماً صحيحاً")
        return

    data = await state.get_data()
    min_amount = data['min_amount']
    balance = data['balance']

    if amount < min_amount:
        await message.answer(
            f"❌ المبلغ أقل من الحد الأدنى ({format_balance(min_amount)})",
            reply_markup=cancel_keyboard()
        )
        return

    if amount > balance:
        await message.answer(
            f"❌ رصيدك غير كافٍ ({format_balance(balance)})",
            reply_markup=cancel_keyboard()
        )
        return

    await state.update_data(amount=amount)
    await state.set_state(WithdrawState.waiting_payment_method)

    methods = await get_payment_methods()
    if not methods:
        await message.answer("❌ لا توجد طرق دفع متاحة حالياً. تواصل مع الإدارة.")
        await state.clear()
        return

    await message.answer(
        f"✅ المبلغ: **{format_balance(amount)}**\n\n"
        f"اختر طريقة الدفع:",
        parse_mode="Markdown",
        reply_markup=payment_methods_keyboard(methods)
    )


@router.callback_query(F.data.startswith("pay_method:"), WithdrawState.waiting_payment_method)
async def handle_payment_method(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    method_id = parts[1]
    method_name = parts[2]

    await state.update_data(payment_method=method_name)
    await state.set_state(WithdrawState.waiting_account_details)

    await callback.message.edit_text(
        f"💳 طريقة الدفع: **{method_name}**\n\n"
        f"أدخل تفاصيل حسابك (رقم الهاتف / المعرف):",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(WithdrawState.waiting_account_details)
async def handle_account_details(message: Message, state: FSMContext):
    account = message.text.strip()
    if len(account) < 5:
        await message.answer("❌ تفاصيل الحساب قصيرة جداً", reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    await state.update_data(account_details=account)
    await state.set_state(WithdrawState.waiting_confirm)

    text = (
        f"📋 **تأكيد طلب السحب**\n\n"
        f"{'━' * 25}\n"
        f"💰 المبلغ: **{format_balance(data['amount'])}**\n"
        f"💳 طريقة الدفع: {data['payment_method']}\n"
        f"📋 الحساب: `{account}`\n"
        f"{'━' * 25}\n\n"
        f"⚠️ بعد التأكيد سيتم خصم المبلغ من رصيدك فوراً وإرساله للمراجعة.\n\n"
        f"هل تأكد؟"
    )

    await message.answer(
        text, parse_mode="Markdown",
        reply_markup=withdrawal_confirm_keyboard(data['amount'], data['payment_method'], account)
    )


@router.callback_query(F.data == "confirm_withdraw", WithdrawState.waiting_confirm)
async def confirm_withdraw(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    user_id = callback.from_user.id
    amount = Decimal(str(data['amount']))
    method = data['payment_method']
    account = data['account_details']

    order_id = await create_withdrawal(user_id, amount, method, account)

    if not order_id:
        await callback.message.edit_text(
            "❌ **فشل طلب السحب**\n\nرصيدك غير كافٍ.",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    # Notify admin
    user = await get_user(user_id)
    from database import fetchrow
    wd_row = await fetchrow("SELECT * FROM withdrawals WHERE order_id = $1", order_id)
    wd = dict(wd_row)

    from utils.utils import format_withdrawal_request
    from keyboards.keyboards import withdrawal_action_keyboard
    try:
        admin_text = format_withdrawal_request(wd, user)
        await callback.bot.send_message(
            config.ADMIN_ID, admin_text,
            parse_mode="Markdown",
            reply_markup=withdrawal_action_keyboard(wd['id'])
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

    await callback.message.edit_text(
        f"✅ **تم إرسال طلب السحب بنجاح!**\n\n"
        f"🔖 رقم الطلب: `{order_id}`\n"
        f"💰 المبلغ: **{format_balance(amount)}**\n"
        f"💳 عبر: {method}\n\n"
        f"⏳ سيتم مراجعة طلبك وإعلامك بالنتيجة.",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "my_withdrawals")
async def my_withdrawals_callback(callback: CallbackQuery):
    wds = await get_user_withdrawals(callback.from_user.id)
    if not wds:
        await callback.answer("لا توجد طلبات سحب بعد", show_alert=True)
        return

    lines = ["📋 **طلبات السحب:**\n"]
    for wd in wds[:10]:
        status_map = {'pending': '⏳ معلق', 'approved': '✅ مقبول', 'rejected': '❌ مرفوض'}
        status = status_map.get(wd['status'], wd['status'])
        date = wd['created_at'].strftime('%m/%d')
        lines.append(
            f"• `{wd['order_id']}` — {format_balance(wd['amount'])} — {status} — {date}"
        )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=back_keyboard("withdraw_menu")
    )
    await callback.answer()
