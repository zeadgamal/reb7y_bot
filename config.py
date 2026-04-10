"""
Configuration Module - Loads environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "7512702966"))
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "MN_BF")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "Reb7yBot")

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "reb7y_bot")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_this_secret_key")

    # Defaults
    DEFAULT_REFERRAL_REWARD: float = float(os.getenv("DEFAULT_REFERRAL_REWARD", "5.00"))
    DEFAULT_FIRST_WITHDRAW_MIN: float = float(os.getenv("DEFAULT_FIRST_WITHDRAW_MIN", "50.00"))
    DEFAULT_NEXT_WITHDRAW_MIN: float = float(os.getenv("DEFAULT_NEXT_WITHDRAW_MIN", "20.00"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")


config = Config()
