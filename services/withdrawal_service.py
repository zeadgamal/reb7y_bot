"""
Withdrawal Service
"""
import random
import string
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict
from database import fetchrow, fetch, execute, fetchval
from services.user_service import deduct_balance

logger = logging.getLogger(__name__)


def generate_order_id() -> str:
    prefix = "RB"
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}{timestamp}{suffix}"


async def create_withdrawal(user_id: int, amount: Decimal, payment_method: str, account_details: str) -> Optional[str]:
    """Create withdrawal request. Returns order_id or None if failed."""
    success = await deduct_balance(user_id, amount, 'withdrawal', f'طلب سحب - {payment_method}')
    if not success:
        return None

    order_id = generate_order_id()
    await execute("""
        INSERT INTO withdrawals (order_id, user_id, amount, payment_method, account_details)
        VALUES ($1, $2, $3, $4, $5)
    """, order_id, user_id, amount, payment_method, account_details)
    return order_id


async def get_withdrawal(order_id: str) -> Optional[Dict]:
    row = await fetchrow("SELECT * FROM withdrawals WHERE order_id = $1", order_id)
    return dict(row) if row else None


async def get_withdrawal_by_id(withdrawal_id: int) -> Optional[Dict]:
    row = await fetchrow("SELECT * FROM withdrawals WHERE id = $1", withdrawal_id)
    return dict(row) if row else None


async def get_pending_withdrawals() -> List[Dict]:
    rows = await fetch("""
        SELECT w.*, u.username, u.full_name
        FROM withdrawals w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.status = 'pending'
        ORDER BY w.created_at ASC
    """)
    return [dict(r) for r in rows]


async def approve_withdrawal(withdrawal_id: int, admin_note: str = None) -> bool:
    result = await execute("""
        UPDATE withdrawals SET status = 'approved', admin_note = $2, processed_at = NOW()
        WHERE id = $1 AND status = 'pending'
    """, withdrawal_id, admin_note)
    return result != "UPDATE 0"


async def reject_withdrawal(withdrawal_id: int, admin_note: str, user_id: int, amount: Decimal) -> bool:
    result = await execute("""
        UPDATE withdrawals SET status = 'rejected', admin_note = $2, processed_at = NOW()
        WHERE id = $1 AND status = 'pending'
    """, withdrawal_id, admin_note)
    if result == "UPDATE 0":
        return False
    # Refund user
    await execute("""
        UPDATE users SET balance = balance + $2, total_withdrawn = total_withdrawn - $2
        WHERE user_id = $1
    """, user_id, amount)
    await execute("""
        INSERT INTO transactions (user_id, type, amount, description)
        VALUES ($1, 'refund', $2, 'استرداد مبلغ سحب مرفوض')
    """, user_id, amount)
    return True


async def get_user_withdrawals(user_id: int) -> List[Dict]:
    rows = await fetch("""
        SELECT * FROM withdrawals WHERE user_id = $1 ORDER BY created_at DESC LIMIT 20
    """, user_id)
    return [dict(r) for r in rows]


async def get_user_withdrawal_count(user_id: int) -> int:
    return await fetchval("SELECT COUNT(*) FROM withdrawals WHERE user_id = $1 AND status = 'approved'", user_id)


async def get_payment_methods() -> List[Dict]:
    rows = await fetch("SELECT * FROM payment_methods WHERE is_active = TRUE ORDER BY id")
    return [dict(r) for r in rows]
