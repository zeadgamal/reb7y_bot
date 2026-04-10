"""
Anti-Spam & Security Service
"""
import hashlib
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from database import fetchrow, fetch, execute, fetchval
import redis.asyncio as aioredis
from config import config

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD or None,
            decode_responses=True
        )
    return _redis


def hash_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


async def check_rate_limit(user_id: int, action: str, limit: int = 5, window: int = 60) -> bool:
    """Returns True if within limit, False if rate limited."""
    redis = await get_redis()
    key = f"rate:{user_id}:{action}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    return count <= limit


async def log_activity(user_id: int, action: str, details: dict = None):
    await execute("""
        INSERT INTO user_activity (user_id, action, details)
        VALUES ($1, $2, $3)
    """, user_id, action, json.dumps(details) if details else None)


async def detect_suspicious_referral(referrer_id: int, referred_id: int) -> tuple[bool, str]:
    """Detect fake referral patterns. Returns (is_suspicious, reason)."""
    # Check if same user (self-referral guard)
    if referrer_id == referred_id:
        return True, "محاولة دعوة ذاتية"

    # Check if referrer was recently added (potential bot farm)
    referrer = await fetchrow("SELECT join_date, referral_count FROM users WHERE user_id = $1", referrer_id)
    if referrer:
        hours_since_join = (datetime.now() - referrer['join_date']).total_seconds() / 3600
        if referrer['referral_count'] > 10 and hours_since_join < 1:
            return True, "معدل إحالة مشبوه جداً"

    # Check referral speed (too many referrals in short time)
    recent_referrals = await fetchval("""
        SELECT COUNT(*) FROM referrals
        WHERE referrer_id = $1 AND created_at > NOW() - INTERVAL '1 hour'
    """, referrer_id)
    if recent_referrals and recent_referrals > 15:
        return True, "سرعة إحالة مشبوهة"

    return False, ""


async def issue_warning(user_id: int, reason: str) -> int:
    """Issue a warning. Returns total warning count."""
    await execute("""
        UPDATE users SET warning_count = warning_count + 1, last_activity = NOW()
        WHERE user_id = $1
    """, user_id)
    count = await fetchval("SELECT warning_count FROM users WHERE user_id = $1", user_id)
    await log_activity(user_id, 'warning', {'reason': reason})

    if count >= 3:
        await execute("""
            UPDATE users SET is_flagged = TRUE, flag_reason = $2 WHERE user_id = $1
        """, user_id, reason)

    return count


async def is_user_banned(user_id: int) -> tuple[bool, str]:
    row = await fetchrow("SELECT is_banned, ban_reason, ban_expires_at FROM users WHERE user_id = $1", user_id)
    if not row or not row['is_banned']:
        return False, ""
    if row['ban_expires_at'] and row['ban_expires_at'] < datetime.now():
        await execute("UPDATE users SET is_banned = FALSE WHERE user_id = $1", user_id)
        return False, ""
    return True, row['ban_reason'] or "محظور"


# =============================================
# CAPTCHA Service
# =============================================

async def generate_math_captcha(user_id: int) -> tuple[str, str]:
    """Generate a math captcha. Returns (question, answer)."""
    import random
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(['+', '-', '*'])
    if op == '+':
        answer = str(a + b)
        question = f"{a} + {b} = ؟"
    elif op == '-':
        a, b = max(a, b), min(a, b)
        answer = str(a - b)
        question = f"{a} - {b} = ؟"
    else:
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        answer = str(a * b)
        question = f"{a} × {b} = ؟"

    await execute("""
        UPDATE users SET captcha_code = $2, captcha_attempts = 0 WHERE user_id = $1
    """, user_id, answer)
    return question, answer


async def verify_captcha(user_id: int, answer: str) -> bool:
    row = await fetchrow("SELECT captcha_code, captcha_attempts FROM users WHERE user_id = $1", user_id)
    if not row:
        return False

    if row['captcha_attempts'] >= 5:
        return False

    await execute("UPDATE users SET captcha_attempts = captcha_attempts + 1 WHERE user_id = $1", user_id)

    if row['captcha_code'] and row['captcha_code'].strip() == answer.strip():
        await execute("""
            UPDATE users SET captcha_verified = TRUE, captcha_code = NULL, captcha_attempts = 0
            WHERE user_id = $1
        """, user_id)
        return True
    return False
