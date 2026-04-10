"""
Promo Codes Service
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List
from database import fetchrow, fetch, execute, fetchval
import logging

logger = logging.getLogger(__name__)


async def get_promo_code(code: str) -> Optional[Dict]:
    row = await fetchrow("SELECT * FROM promo_codes WHERE code = UPPER($1) AND is_active = TRUE", code.upper())
    return dict(row) if row else None


async def validate_promo_code(code: str, user_id: int) -> tuple[bool, str, Optional[Decimal]]:
    """Returns (valid, reason, reward_amount)"""
    promo = await get_promo_code(code)
    if not promo:
        return False, "الكود غير موجود أو منتهي", None

    # Check expiry
    if promo['expires_at'] and promo['expires_at'] < datetime.now():
        return False, "انتهت صلاحية هذا الكود", None

    # Check global usage limit
    if promo['usage_limit'] and promo['used_count'] >= promo['usage_limit']:
        return False, "تم استنفاد هذا الكود بالكامل", None

    # Check per-user usage
    user_usage = await fetchval("""
        SELECT COUNT(*) FROM promo_usage WHERE code_id = $1 AND user_id = $2
    """, promo['id'], user_id)
    if user_usage >= promo['usage_per_user']:
        return False, "لقد استخدمت هذا الكود مسبقاً", None

    return True, "valid", Decimal(str(promo['reward']))


async def redeem_promo_code(code: str, user_id: int) -> tuple[bool, str, Optional[Decimal]]:
    valid, reason, reward = await validate_promo_code(code, user_id)
    if not valid:
        return False, reason, None

    promo = await get_promo_code(code)
    await execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE id = $1", promo['id'])
    await execute("INSERT INTO promo_usage (code_id, user_id) VALUES ($1, $2)", promo['id'], user_id)
    return True, "تم استرداد الكود بنجاح", reward


async def create_promo_code(code: str, reward: Decimal, usage_limit: int, usage_per_user: int,
                             expires_at: Optional[datetime], created_by: int):
    await execute("""
        INSERT INTO promo_codes (code, reward, usage_limit, usage_per_user, expires_at, created_by)
        VALUES (UPPER($1), $2, $3, $4, $5, $6)
    """, code, reward, usage_limit, usage_per_user, expires_at, created_by)


async def get_all_promo_codes() -> List[Dict]:
    rows = await fetch("SELECT * FROM promo_codes ORDER BY created_at DESC")
    return [dict(r) for r in rows]


async def deactivate_promo_code(code_id: int):
    await execute("UPDATE promo_codes SET is_active = FALSE WHERE id = $1", code_id)


# =============================================
# Channels Service
# =============================================

async def get_active_channels() -> List[Dict]:
    rows = await fetch("SELECT * FROM channels WHERE is_active = TRUE")
    return [dict(r) for r in rows]


async def add_channel(channel_id: str, channel_name: str, channel_link: str):
    await execute("""
        INSERT INTO channels (channel_id, channel_name, channel_link)
        VALUES ($1, $2, $3)
        ON CONFLICT (channel_id) DO UPDATE SET channel_name = $2, channel_link = $3, is_active = TRUE
    """, channel_id, channel_name, channel_link)


async def remove_channel(channel_id: str):
    await execute("UPDATE channels SET is_active = FALSE WHERE channel_id = $1", channel_id)


async def get_all_channels() -> List[Dict]:
    rows = await fetch("SELECT * FROM channels ORDER BY added_at DESC")
    return [dict(r) for r in rows]


# =============================================
# Ads Service
# =============================================

async def get_active_ads(trigger_event: str = None) -> List[Dict]:
    if trigger_event:
        rows = await fetch("""
            SELECT * FROM ads WHERE is_active = TRUE AND (trigger_event = $1 OR trigger_event IS NULL)
            ORDER BY RANDOM() LIMIT 1
        """, trigger_event)
    else:
        rows = await fetch("SELECT * FROM ads WHERE is_active = TRUE LIMIT 1")
    return [dict(r) for r in rows]


async def create_ad(title: str, content: str, ad_type: str, link_url: str, button_text: str,
                    reward: Decimal, trigger_event: str):
    await execute("""
        INSERT INTO ads (title, content, ad_type, link_url, button_text, reward_for_view, trigger_event)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, title, content, ad_type, link_url, button_text, reward, trigger_event)


async def record_ad_view(ad_id: int, user_id: int) -> bool:
    """Record ad view. Returns True if first view (reward eligible)."""
    existing = await fetchval("""
        SELECT id FROM ad_views WHERE ad_id = $1 AND user_id = $2
        AND viewed_at > NOW() - INTERVAL '24 hours'
    """, ad_id, user_id)
    if existing:
        return False
    await execute("INSERT INTO ad_views (ad_id, user_id) VALUES ($1, $2)", ad_id, user_id)
    await execute("UPDATE ads SET view_count = view_count + 1 WHERE id = $1", ad_id)
    return True


async def record_ad_click(ad_id: int):
    await execute("UPDATE ads SET click_count = click_count + 1 WHERE id = $1", ad_id)


async def get_all_ads() -> List[Dict]:
    rows = await fetch("SELECT * FROM ads ORDER BY created_at DESC")
    return [dict(r) for r in rows]
