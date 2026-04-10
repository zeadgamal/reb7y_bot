"""
Settings Service - Dynamic bot configuration
"""
from typing import Optional, Dict
from database import fetchrow, fetch, execute, fetchval
import logging

logger = logging.getLogger(__name__)

_cache: Dict[str, str] = {}


async def get_setting(key: str, default=None) -> Optional[str]:
    if key in _cache:
        return _cache[key]
    val = await fetchval("SELECT value FROM settings WHERE key = $1", key)
    if val is not None:
        _cache[key] = val
    return val if val is not None else default


async def set_setting(key: str, value: str):
    await execute("""
        INSERT INTO settings (key, value) VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
    """, key, value)
    _cache[key] = value


async def get_all_settings() -> Dict[str, str]:
    rows = await fetch("SELECT key, value FROM settings")
    result = {r['key']: r['value'] for r in rows}
    _cache.update(result)
    return result


async def get_referral_reward() -> float:
    val = await get_setting('referral_reward', '5.00')
    return float(val)


async def get_first_withdraw_min() -> float:
    val = await get_setting('first_withdraw_min', '50.00')
    return float(val)


async def get_next_withdraw_min() -> float:
    val = await get_setting('next_withdraw_min', '20.00')
    return float(val)


async def get_daily_reward() -> float:
    val = await get_setting('daily_reward', '2.00')
    return float(val)


async def is_ads_enabled() -> bool:
    val = await get_setting('ads_enabled', 'true')
    return val.lower() == 'true'


async def is_maintenance() -> bool:
    val = await get_setting('maintenance_mode', 'false')
    return val.lower() == 'true'


async def get_boost_info() -> Dict:
    active = (await get_setting('boost_active', 'false')).lower() == 'true'
    multiplier = float(await get_setting('boost_multiplier', '2.0'))
    ends_at = await get_setting('boost_ends_at', None)
    return {'active': active, 'multiplier': multiplier, 'ends_at': ends_at}


def invalidate_cache():
    _cache.clear()
