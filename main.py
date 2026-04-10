"""
@Reb7yBot - Main Entry Point
Admin: @MN_BF (7512702966)
"""
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from database.db import get_pool, close_pool
from middlewares.middlewares import BanCheckMiddleware, RateLimitMiddleware, ActivityTrackingMiddleware
from handlers import start, balance, daily, withdraw, games, admin

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("🚀 Starting @Reb7yBot...")
    await get_pool()
    logger.info("✅ Database connected")

    # Init schema if needed
    import asyncpg
    pool = await get_pool()
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    async with pool.acquire() as conn:
        await conn.execute(schema)
    logger.info("✅ Schema initialized")

    me = await bot.get_me()
    logger.info(f"✅ Bot started: @{me.username}")

    # Notify admin
    try:
        await bot.send_message(
            config.ADMIN_ID,
            f"✅ **@{me.username} تم تشغيل البوت بنجاح!**\n\n"
            f"🕒 {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not notify admin: {e}")


async def on_shutdown(bot: Bot):
    logger.info("🛑 Shutting down...")
    await close_pool()
    logger.info("✅ Database pool closed")


async def main():
    if not config.BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env")

    # Setup storage
    try:
        storage = RedisStorage.from_url(
            f"redis://{':' + config.REDIS_PASSWORD + '@' if config.REDIS_PASSWORD else ''}"
            f"{config.REDIS_HOST}:{config.REDIS_PORT}"
        )
        logger.info("Using Redis storage")
    except Exception as e:
        logger.warning(f"Redis unavailable, using MemoryStorage: {e}")
        storage = MemoryStorage()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    dp = Dispatcher(storage=storage)

    # Register middlewares (order matters)
    dp.message.middleware(BanCheckMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(ActivityTrackingMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(balance.router)
    dp.include_router(daily.router)
    dp.include_router(withdraw.router)
    dp.include_router(games.router)
    dp.include_router(admin.router)

    # Lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("🤖 Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
