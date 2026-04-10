"""
User Service - Database operations for users
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
from database import fetchrow, fetch, execute, fetchval

logger = logging.getLogger(__name__)


async def get_user(user_id: int) -> Optional[Dict]:
    row = await fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(row) if row else None


async def create_user(user_id: int, username: str, full_name: str, referred_by: Optional[int] = None) -> Dict:
    row = await fetchrow("""
        INSERT INTO users (user_id, username, full_name, referred_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            full_name = EXCLUDED.full_name,
            last_activity = NOW()
        RETURNING *
    """, user_id, username, full_name, referred_by)
    return dict(row)


async def update_user(user_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clauses = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(fields.keys())])
    values = list(fields.values())
    await execute(f"UPDATE users SET {set_clauses}, last_activity = NOW() WHERE user_id = $1", user_id, *values)
    return True


async def get_user_balance(user_id: int) -> Decimal:
    val = await fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
    return Decimal(str(val or 0))


async def add_balance(user_id: int, amount: Decimal, tx_type: str, description: str, ref_id: str = None):
    await execute("""
        UPDATE users SET balance = balance + $2, total_earned = total_earned + $2, last_activity = NOW()
        WHERE user_id = $1
    """, user_id, amount)
    await execute("""
        INSERT INTO transactions (user_id, type, amount, description, reference_id)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, tx_type, amount, description, ref_id)


async def deduct_balance(user_id: int, amount: Decimal, tx_type: str, description: str, ref_id: str = None) -> bool:
    result = await execute("""
        UPDATE users SET balance = balance - $2, total_withdrawn = total_withdrawn + $2, last_activity = NOW()
        WHERE user_id = $1 AND balance >= $2
    """, user_id, amount)
    if result == "UPDATE 0":
        return False
    await execute("""
        INSERT INTO transactions (user_id, type, amount, description, reference_id)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, tx_type, -amount, description, ref_id)
    return True


async def get_all_users(limit: int = None, offset: int = 0) -> List[Dict]:
    query = "SELECT * FROM users ORDER BY created_at DESC"
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    rows = await fetch(query)
    return [dict(r) for r in rows]


async def get_user_count() -> int:
    return await fetchval("SELECT COUNT(*) FROM users")


async def get_active_users_count(days: int = 7) -> int:
    cutoff = datetime.now() - timedelta(days=days)
    return await fetchval("SELECT COUNT(*) FROM users WHERE last_activity >= $1", cutoff)


async def get_top_referrers(limit: int = 10) -> List[Dict]:
    rows = await fetch("""
        SELECT user_id, username, full_name, referral_count, balance, rank
        FROM users
        WHERE is_banned = FALSE
        ORDER BY referral_count DESC
        LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


async def update_rank(user_id: int, referral_count: int, settings: Dict) -> Optional[str]:
    """Update user rank based on referral count. Returns new rank if changed."""
    gold_threshold = int(settings.get('gold_threshold', 50))
    silver_threshold = int(settings.get('silver_threshold', 20))
    bronze_threshold = int(settings.get('bronze_threshold', 5))
    gold_mult = float(settings.get('gold_multiplier', 1.5))
    silver_mult = float(settings.get('silver_multiplier', 1.2))
    bronze_mult = float(settings.get('bronze_multiplier', 1.0))

    if referral_count >= gold_threshold:
        new_rank, new_mult = 'gold', gold_mult
    elif referral_count >= silver_threshold:
        new_rank, new_mult = 'silver', silver_mult
    elif referral_count >= bronze_threshold:
        new_rank, new_mult = 'bronze', bronze_mult
    else:
        new_rank, new_mult = 'bronze', 1.0

    old_rank = await fetchval("SELECT rank FROM users WHERE user_id = $1", user_id)
    if old_rank != new_rank:
        await execute("""
            UPDATE users SET rank = $2, rank_multiplier = $3 WHERE user_id = $1
        """, user_id, new_rank, new_mult)
        return new_rank
    return None


async def get_transaction_history(user_id: int, limit: int = 10) -> List[Dict]:
    rows = await fetch("""
        SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2
    """, user_id, limit)
    return [dict(r) for r in rows]


async def get_flagged_users() -> List[Dict]:
    rows = await fetch("SELECT * FROM users WHERE is_flagged = TRUE ORDER BY created_at DESC")
    return [dict(r) for r in rows]


async def ban_user(user_id: int, reason: str, duration_hours: int = None):
    ban_expires = datetime.now() + timedelta(hours=duration_hours) if duration_hours else None
    await execute("""
        UPDATE users SET is_banned = TRUE, ban_reason = $2, ban_expires_at = $3
        WHERE user_id = $1
    """, user_id, reason, ban_expires)


async def unban_user(user_id: int):
    await execute("""
        UPDATE users SET is_banned = FALSE, ban_reason = NULL, ban_expires_at = NULL
        WHERE user_id = $1
    """, user_id)


async def increment_message_count(user_id: int):
    await execute("UPDATE users SET total_messages = total_messages + 1 WHERE user_id = $1", user_id)


async def get_total_stats() -> Dict:
    stats = {}
    stats['total_users'] = await fetchval("SELECT COUNT(*) FROM users")
    stats['active_users'] = await get_active_users_count(7)
    stats['banned_users'] = await fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
    stats['total_earned'] = await fetchval("SELECT COALESCE(SUM(total_earned), 0) FROM users") or 0
    stats['total_withdrawn'] = await fetchval("SELECT COALESCE(SUM(total_withdrawn), 0) FROM users") or 0
    stats['pending_withdrawals'] = await fetchval("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
    stats['total_referrals'] = await fetchval("SELECT COUNT(*) FROM referrals")
    return stats
