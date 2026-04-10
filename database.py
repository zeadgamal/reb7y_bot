#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
قاعدة بيانات البوت - SQLite
نسخة متوافقة مع القاعدة القديمة - تقوم بتحديث الجداول فقط دون حذف البيانات
"""

import sqlite3
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """إدارة قاعدة البيانات SQLite - متوافقة مع القواعد القديمة"""
    
    def __init__(self, db_file: str = "Reb7y.db"):
        self.db_file = db_file
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_file, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _table_exists(self, conn, table_name: str) -> bool:
        """التحقق من وجود جدول"""
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    
    def _column_exists(self, conn, table_name: str, column_name: str) -> bool:
        """التحقق من وجود عمود في جدول"""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns
    
    def _init_database(self):
        """إنشاء أو تحديث الجداول - يحافظ على البيانات الموجودة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ==================== جدول users ====================
            if not self._table_exists(conn, 'users'):
                cursor.execute('''
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        phone TEXT,
                        balance_egp REAL DEFAULT 0,
                        total_earnings_egp REAL DEFAULT 0,
                        withdrawal_count INTEGER DEFAULT 0,
                        last_daily_claim TEXT,
                        last_wheel_date TEXT,
                        last_game_date TEXT,
                        referred_by INTEGER,
                        verified INTEGER DEFAULT 0,
                        display_currency TEXT DEFAULT 'EGP',
                        verification_attempts INTEGER DEFAULT 0,
                        banned INTEGER DEFAULT 0,
                        ban_reason TEXT,
                        banned_at TEXT,
                        joined_at TEXT,
                        updated_at TEXT,
                        last_daily_task_time TEXT,
                        daily_task_completed INTEGER DEFAULT 0,
                        daily_tasks_data TEXT
                    )
                ''')
                logger.info("Users table created")
            else:
                columns_to_add = [
                    ('phone', 'TEXT'),
                    ('banned', 'INTEGER DEFAULT 0'),
                    ('ban_reason', 'TEXT'),
                    ('banned_at', 'TEXT'),
                    ('last_wheel_date', 'TEXT'),
                    ('last_game_date', 'TEXT'),
                    ('last_daily_task_time', 'TEXT'),
                    ('daily_task_completed', 'INTEGER DEFAULT 0'),
                    ('daily_tasks_data', 'TEXT'),
                    ('display_currency', 'TEXT DEFAULT "EGP"'),
                    ('verification_attempts', 'INTEGER DEFAULT 0'),
                    ('total_earnings_egp', 'REAL DEFAULT 0'),
                    ('withdrawal_count', 'INTEGER DEFAULT 0'),
                ]
                
                for col_name, col_type in columns_to_add:
                    if not self._column_exists(conn, 'users', col_name):
                        try:
                            cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                            logger.info(f"Column {col_name} added to users")
                        except Exception as e:
                            logger.warning(f"Could not add {col_name}: {e}")
                
                try:
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_banned ON users(banned)')
                except:
                    pass
                
                logger.info("Users table updated")
            
            # ==================== جدول user_daily_tasks ====================
            if not self._table_exists(conn, 'user_daily_tasks'):
                cursor.execute('''
                    CREATE TABLE user_daily_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        task_id TEXT NOT NULL,
                        task_name TEXT NOT NULL,
                        task_description TEXT,
                        reward_egp REAL DEFAULT 0,
                        last_completed TEXT,
                        completed_today INTEGER DEFAULT 0,
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, task_id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_daily_tasks_user_id ON user_daily_tasks(user_id)')
                logger.info("User daily tasks table created")
            
            # ==================== جدول withdrawals ====================
            if not self._table_exists(conn, 'withdrawals'):
                cursor.execute('''
                    CREATE TABLE withdrawals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        amount_egp REAL,
                        method TEXT,
                        status TEXT DEFAULT 'pending',
                        phone TEXT,
                        binance_id TEXT,
                        usdt_address TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_user_id ON withdrawals(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals(status)')
                logger.info("Withdrawals table created")
            
            # ==================== جدول referrals ====================
            if not self._table_exists(conn, 'referrals'):
                cursor.execute('''
                    CREATE TABLE referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER,
                        referred_id INTEGER,
                        referred_name TEXT,
                        bonus_egp REAL,
                        created_at TEXT,
                        processed INTEGER DEFAULT 0,
                        processed_at TEXT,
                        FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                        FOREIGN KEY (referred_id) REFERENCES users (user_id),
                        UNIQUE(referrer_id, referred_id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON referrals(referred_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_processed ON referrals(processed)')
                logger.info("Referrals table created")
            else:
                if not self._column_exists(conn, 'referrals', 'processed'):
                    try:
                        cursor.execute('ALTER TABLE referrals ADD COLUMN processed INTEGER DEFAULT 0')
                        cursor.execute('ALTER TABLE referrals ADD COLUMN processed_at TEXT')
                        logger.info("Added processed column to referrals")
                    except:
                        pass
                
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='referrals'")
                table_sql = cursor.fetchone()[0]
                if 'UNIQUE' not in table_sql:
                    cursor.execute('SELECT * FROM referrals')
                    old_data = cursor.fetchall()
                    
                    cursor.execute('DROP TABLE referrals')
                    cursor.execute('''
                        CREATE TABLE referrals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            referrer_id INTEGER,
                            referred_id INTEGER,
                            referred_name TEXT,
                            bonus_egp REAL,
                            created_at TEXT,
                            processed INTEGER DEFAULT 0,
                            processed_at TEXT,
                            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                            FOREIGN KEY (referred_id) REFERENCES users (user_id),
                            UNIQUE(referrer_id, referred_id)
                        )
                    ''')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON referrals(referred_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_processed ON referrals(processed)')
                    
                    seen = set()
                    for row in old_data:
                        key = (row[1], row[2])
                        if key not in seen:
                            seen.add(key)
                            try:
                                cursor.execute('''
                                    INSERT INTO referrals (id, referrer_id, referred_id, referred_name, bonus_egp, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', row)
                            except:
                                pass
                    
                    logger.info("Referrals table updated with UNIQUE constraint")
                else:
                    logger.info("Referrals table exists and updated")
            
            # ==================== جدول channels ====================
            if not self._table_exists(conn, 'channels'):
                cursor.execute('''
                    CREATE TABLE channels (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        link TEXT,
                        added_at TEXT
                    )
                ''')
                logger.info("Channels table created")
            
            # ==================== جدول settings ====================
            if not self._table_exists(conn, 'settings'):
                cursor.execute('''
                    CREATE TABLE settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                ''')
                logger.info("Settings table created")
            
            # ==================== جدول temp_data ====================
            if not self._table_exists(conn, 'temp_data'):
                cursor.execute('''
                    CREATE TABLE temp_data (
                        user_id INTEGER PRIMARY KEY,
                        data TEXT,
                        created_at TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                logger.info("Temp data table created")
            
            # ==================== جدول banned_phones ====================
            if not self._table_exists(conn, 'banned_phones'):
                cursor.execute('''
                    CREATE TABLE banned_phones (
                        phone TEXT PRIMARY KEY,
                        banned_at TEXT,
                        reason TEXT
                    )
                ''')
                logger.info("Banned phones table created")
            
            # ==================== جداول مهمات التطبيقات ====================
            
            if not self._table_exists(conn, 'app_tasks'):
                cursor.execute('''
                    CREATE TABLE app_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        image_url TEXT,
                        app_link TEXT,
                        reward_egp REAL DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT,
                        created_by INTEGER,
                        FOREIGN KEY (created_by) REFERENCES users (user_id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_app_tasks_active ON app_tasks(is_active)')
                logger.info("App tasks table created")
            else:
                columns_to_add = [
                    ('image_url', 'TEXT'),
                    ('app_link', 'TEXT'),
                    ('is_active', 'INTEGER DEFAULT 1'),
                    ('created_by', 'INTEGER'),
                ]
                
                for col_name, col_type in columns_to_add:
                    if not self._column_exists(conn, 'app_tasks', col_name):
                        try:
                            cursor.execute(f'ALTER TABLE app_tasks ADD COLUMN {col_name} {col_type}')
                            logger.info(f"Column {col_name} added to app_tasks")
                        except Exception as e:
                            logger.warning(f"Could not add {col_name} to app_tasks: {e}")
                
                logger.info("App tasks table updated")
            
            if not self._table_exists(conn, 'user_task_completions'):
                cursor.execute('''
                    CREATE TABLE user_task_completions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        task_id INTEGER NOT NULL,
                        screenshot_file_id TEXT,
                        status TEXT DEFAULT 'pending',
                        submitted_at TEXT,
                        processed_at TEXT,
                        reward_egp REAL DEFAULT 0,
                        admin_note TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (task_id) REFERENCES app_tasks (id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_completions_user ON user_task_completions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_completions_task ON user_task_completions(task_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_completions_status ON user_task_completions(status)')
                logger.info("User task completions table created")
            else:
                columns_to_add = [
                    ('reward_egp', 'REAL DEFAULT 0'),
                    ('admin_note', 'TEXT'),
                ]
                
                for col_name, col_type in columns_to_add:
                    if not self._column_exists(conn, 'user_task_completions', col_name):
                        try:
                            cursor.execute(f'ALTER TABLE user_task_completions ADD COLUMN {col_name} {col_type}')
                            logger.info(f"Column {col_name} added to user_task_completions")
                        except Exception as e:
                            logger.warning(f"Could not add {col_name} to user_task_completions: {e}")
                
                logger.info("User task completions table updated")
            
            if not self._table_exists(conn, 'user_task_history'):
                cursor.execute('''
                    CREATE TABLE user_task_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        task_id INTEGER NOT NULL,
                        completed_at TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        FOREIGN KEY (task_id) REFERENCES app_tasks (id),
                        UNIQUE(user_id, task_id)
                    )
                ''')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON user_task_history(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_task ON user_task_history(task_id)')
                logger.info("User task history table created")
            
            cursor.execute('SELECT key, value FROM settings')
            existing_settings = {row[0]: row[1] for row in cursor.fetchall()}
            
            self._init_default_settings(conn, existing_settings)
            self._init_default_daily_tasks(conn, existing_settings)
            
            cursor.execute('SELECT key, value FROM settings')
            settings = {row[0]: row[1] for row in cursor.fetchall()}
            
            self._migrate_existing_users_tasks(conn, settings)
            
            logger.info("Database initialized successfully")
    
    def _migrate_existing_users_tasks(self, conn, settings: Dict):
        """إضافة مهام يومية للمستخدمين القدامى - معالجة على دفعات"""
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        batch_size = 50
        migrated_count = 0
        
        for offset in range(0, total_users, batch_size):
            cursor.execute('SELECT user_id FROM users LIMIT ? OFFSET ?', (batch_size, offset))
            users = cursor.fetchall()
            
            for user in users:
                user_id = user['user_id']
                cursor.execute('SELECT COUNT(*) FROM user_daily_tasks WHERE user_id = ?', (user_id,))
                count = cursor.fetchone()[0]
                
                if count == 0:
                    self._create_user_daily_tasks(conn, user_id, settings)
                    migrated_count += 1
            
            if offset + batch_size < total_users:
                time.sleep(0.3)
        
        if migrated_count > 0:
            logger.info(f"Added daily tasks for {migrated_count} existing users")
    
    def _init_default_settings(self, conn, existing_settings: Dict):
        """إعداد الإعدادات الافتراضية"""
        cursor = conn.cursor()
        
        default_settings = {
            'referral_bonus_egp': '5',
            'first_withdrawal_egp': '1',
            'second_withdrawal_egp': '100',
            'daily_bonus_egp': '1',
            'min_wheel_reward': '1',
            'max_wheel_reward': '3',
            'min_game_reward': '1',
            'max_game_reward': '3',
            'usd_to_egp': '52.0',
            'force_sub_enabled': '1',
            'language': 'ar',
            'cancel_withdrawal_minutes': '1'
        }
        
        for key, value in default_settings.items():
            if key not in existing_settings:
                cursor.execute('''
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, value, datetime.now().isoformat()))
    
    def _init_default_daily_tasks(self, conn, existing_settings: Dict):
        """إضافة المهام اليومية الافتراضية"""
        cursor = conn.cursor()
        
        default_tasks = [
            ('wheel_of_fortune', 'عجلة الحظ', 'أدير عجلة الحظ واربح من 1-3 جنيه', 0),
            ('play_and_win', 'العب واربح', 'اختر مربع واربح من 1-3 جنيه', 0),
            ('daily_gift', 'الهدية اليومية', 'احصل على هديتك اليومية مجاناً', 0),
        ]
        
        for task_id, task_name, task_desc, reward in default_tasks:
            key_name = f'task_{task_id}_name'
            key_desc = f'task_{task_id}_desc'
            key_reward = f'task_{task_id}_reward'
            
            if key_name not in existing_settings:
                cursor.execute('INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                             (key_name, task_name, datetime.now().isoformat()))
            if key_desc not in existing_settings:
                cursor.execute('INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                             (key_desc, task_desc, datetime.now().isoformat()))
            if key_reward not in existing_settings:
                cursor.execute('INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                             (key_reward, str(reward), datetime.now().isoformat()))
    
    def _create_user_daily_tasks(self, conn, user_id: int, settings: Dict):
        """إنشاء المهام اليومية لمستخدم معين"""
        cursor = conn.cursor()
        
        tasks_data = [
            ('wheel_of_fortune', settings.get('task_wheel_of_fortune_name', 'عجلة الحظ'),
             settings.get('task_wheel_of_fortune_desc', 'أدير عجلة الحظ واربح'), 0),
            ('play_and_win', settings.get('task_play_and_win_name', 'العب واربح'),
             settings.get('task_play_and_win_desc', 'اختر مربع واربح'), 0),
            ('daily_gift', settings.get('task_daily_gift_name', 'الهدية اليومية'),
             settings.get('task_daily_gift_desc', 'احصل على هديتك اليومية'), 0),
        ]
        
        now = datetime.now().isoformat()
        
        for task_id, task_name, task_desc, reward in tasks_data:
            cursor.execute('''
                INSERT OR IGNORE INTO user_daily_tasks 
                (user_id, task_id, task_name, task_description, reward_egp, created_at, updated_at, completed_today, last_completed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, task_id, task_name, task_desc, reward, now, now, 0, None))
    
    # ==================== دوال المهام اليومية ====================
    
    def get_daily_tasks(self, user_id: int) -> List[Dict]:
        """الحصول على جميع المهام اليومية للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM user_daily_tasks 
                WHERE user_id = ?
            ''', (user_id,))
            
            tasks = [dict(row) for row in cursor.fetchall()]
            
            if not tasks:
                cursor.execute('SELECT key, value FROM settings')
                settings = {row[0]: row[1] for row in cursor.fetchall()}
                self._create_user_daily_tasks(conn, user_id, settings)
                
                cursor.execute('''
                    SELECT * FROM user_daily_tasks 
                    WHERE user_id = ?
                ''', (user_id,))
                tasks = [dict(row) for row in cursor.fetchall()]
            
            today = datetime.now().date().isoformat()
            for task in tasks:
                last_completed = task.get('last_completed')
                if last_completed:
                    last_date = last_completed[:10]
                    task['can_complete'] = last_date != today
                    task['time_remaining'] = None if task['can_complete'] else self._get_time_remaining(last_completed)
                else:
                    task['can_complete'] = True
                    task['time_remaining'] = None
            
            return tasks
    
    def _get_time_remaining(self, last_completed: str) -> Optional[str]:
        """حساب الوقت المتبقي"""
        if not last_completed:
            return None
        
        try:
            last_time = datetime.fromisoformat(last_completed)
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
    
    def complete_daily_task(self, user_id: int, task_id: str) -> bool:
        """تسجيل إكمال مهمة يومية"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT last_completed FROM user_daily_tasks 
                WHERE user_id = ? AND task_id = ?
            ''', (user_id, task_id))
            
            row = cursor.fetchone()
            if row:
                last_completed = row['last_completed']
                if last_completed:
                    last_date = datetime.fromisoformat(last_completed)
                    if datetime.now() - last_date < timedelta(hours=24):
                        return False
            
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE user_daily_tasks 
                SET last_completed = ?, completed_today = 1, updated_at = ?
                WHERE user_id = ? AND task_id = ?
            ''', (now, now, user_id, task_id))
            
            return cursor.rowcount > 0
    
    def get_task_reward(self, task_id: str) -> float:
        """الحصول على مكافأة المهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (f'task_{task_id}_reward',))
            row = cursor.fetchone()
            if row:
                return float(row[0])
            return 0
    
    def can_complete_task(self, user_id: int, task_id: str) -> tuple:
        """التحقق من إمكانية إكمال المهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT last_completed FROM user_daily_tasks 
                WHERE user_id = ? AND task_id = ?
            ''', (user_id, task_id))
            
            row = cursor.fetchone()
            if not row or not row['last_completed']:
                return True, None
            
            last_completed = row['last_completed']
            time_remaining = self._get_time_remaining(last_completed)
            
            return time_remaining is None, time_remaining
    
    # ==================== دوال المستخدمين ====================
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات المستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_phone(self, phone: str) -> Optional[Dict]:
        """الحصول على مستخدم برقم الهاتف"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT * FROM users WHERE phone = ?', (phone,))
                row = cursor.fetchone()
                return dict(row) if row else None
            except sqlite3.OperationalError:
                return None
    
    def update_user_phone(self, user_id: int, phone: str):
        """تحديث رقم هاتف المستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE users SET phone = ?, updated_at = ? WHERE user_id = ?
                ''', (phone, datetime.now().isoformat(), user_id))
            except sqlite3.OperationalError:
                pass
    
    def create_user(self, user_id: int, username: str, first_name: str, referred_by: int = None) -> Dict:
        """إنشاء مستخدم جديد"""
        now = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by, verified, joined_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, referred_by, 0, now, now))
            
            cursor.execute('SELECT key, value FROM settings')
            settings = {row[0]: row[1] for row in cursor.fetchall()}
            self._create_user_daily_tasks(conn, user_id, settings)
            
            return self.get_user(user_id)
    
    def update_user(self, user_id: int, **kwargs):
        """تحديث بيانات المستخدم"""
        if not kwargs:
            return
        
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if not fields:
            return
        
        values.append(datetime.now().isoformat())
        values.append(user_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f'''
                    UPDATE users SET {', '.join(fields)}, updated_at = ? WHERE user_id = ?
                ''', values)
            except sqlite3.OperationalError as e:
                logger.error(f"Error updating user: {e}")
    
    def add_balance(self, user_id: int, amount_egp: float, add_to_total: bool = True):
        """إضافة رصيد للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if add_to_total:
                cursor.execute('''
                    UPDATE users 
                    SET balance_egp = COALESCE(balance_egp, 0) + ?,
                        total_earnings_egp = COALESCE(total_earnings_egp, 0) + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (amount_egp, amount_egp, datetime.now().isoformat(), user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET balance_egp = COALESCE(balance_egp, 0) + ?,
                        updated_at = ?
                    WHERE user_id = ?
                ''', (amount_egp, datetime.now().isoformat(), user_id))
    
    def subtract_balance(self, user_id: int, amount_egp: float) -> bool:
        """خصم رصيد وزيادة عدد السحوبات"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance_egp = COALESCE(balance_egp, 0) - ?,
                    withdrawal_count = COALESCE(withdrawal_count, 0) + 1,
                    updated_at = ?
                WHERE user_id = ? AND COALESCE(balance_egp, 0) >= ?
            ''', (amount_egp, datetime.now().isoformat(), user_id, amount_egp))
            
            return cursor.rowcount > 0
    
    def refund_balance(self, user_id: int, amount_egp: float):
        """إعادة رصيد وتقليل عدد السحوبات"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance_egp = COALESCE(balance_egp, 0) + ?,
                    withdrawal_count = COALESCE(withdrawal_count, 0) - 1,
                    updated_at = ?
                WHERE user_id = ?
            ''', (amount_egp, datetime.now().isoformat(), user_id))
    
    def get_all_users(self) -> List[Dict]:
        """الحصول على جميع المستخدمين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY user_id')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_users_count(self) -> int:
        """عدد المستخدمين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            return cursor.fetchone()[0]
    
    def get_verified_users_count(self) -> int:
        """عدد المستخدمين المتحققين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users WHERE verified = 1')
            return cursor.fetchone()[0]
    
    # ==================== دوال الحظر ====================
    
    def ban_user(self, user_id: int, reason: str = None):
        """حظر مستخدم"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE users 
                    SET banned = 1, ban_reason = ?, banned_at = ?, updated_at = ?
                    WHERE user_id = ?
                ''', (reason, now, now, user_id))
            except sqlite3.OperationalError:
                pass
    
    def is_user_banned(self, user_id: int) -> bool:
        """التحقق من حظر المستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT banned FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                return row and row['banned'] == 1
            except sqlite3.OperationalError:
                return False
    
    def get_banned_users(self) -> List[Dict]:
        """الحصول على المستخدمين المحظورين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    SELECT user_id, username, first_name, phone, ban_reason, banned_at 
                    FROM users WHERE banned = 1 ORDER BY banned_at DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                return []
    
    def get_banned_users_count(self) -> int:
        """عدد المستخدمين المحظورين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
                return cursor.fetchone()[0]
            except sqlite3.OperationalError:
                return 0
    
    def ban_phone(self, phone: str, reason: str = None):
        """حظر رقم هاتف"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO banned_phones (phone, banned_at, reason)
                VALUES (?, ?, ?)
            ''', (phone, datetime.now().isoformat(), reason))
    
    def is_phone_banned(self, phone: str) -> bool:
        """التحقق من حظر رقم الهاتف"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM banned_phones WHERE phone = ?', (phone,))
            return cursor.fetchone() is not None
    
    # ==================== دوال السحب ====================
    
    def create_withdrawal(self, user_id: int, amount_egp: float, method: str, 
                          phone: str = None, binance_id: str = None, 
                          usdt_address: str = None) -> int:
        """إنشاء طلب سحب جديد"""
        now = datetime.now().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO withdrawals (user_id, amount_egp, method, phone, binance_id, usdt_address, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, amount_egp, method, phone, binance_id, usdt_address, now, now))
            
            return cursor.lastrowid
    
    def get_withdrawal(self, w_id: int) -> Optional[Dict]:
        """الحصول على طلب سحب"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM withdrawals WHERE id = ?', (w_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_pending_withdrawal(self, user_id: int) -> Optional[Dict]:
        """الحصول على طلب سحب معلق للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM withdrawals 
                WHERE user_id = ? AND status = 'pending'
                ORDER BY id DESC LIMIT 1
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_withdrawals(self, status: str = None) -> List[Dict]:
        """الحصول على طلبات السحب"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('SELECT * FROM withdrawals WHERE status = ? ORDER BY id ASC', (status,))
            else:
                cursor.execute('SELECT * FROM withdrawals ORDER BY id ASC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_withdrawals_by_amount(self, amount_egp: float, status: str = 'pending') -> List[Dict]:
        """الحصول على طلبات السحب بمبلغ معين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM withdrawals 
                WHERE status = ? AND amount_egp = ? 
                ORDER BY id ASC
            ''', (status, amount_egp))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_withdrawal_status(self, w_id: int, status: str) -> bool:
        """تحديث حالة طلب السحب"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE withdrawals 
                SET status = ?, updated_at = ?
                WHERE id = ?
            ''', (status, datetime.now().isoformat(), w_id))
            return cursor.rowcount > 0
    
    def get_pending_withdrawals_count(self) -> int:
        """عدد طلبات السحب المعلقة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE status = "pending"')
            return cursor.fetchone()[0]
    
    def get_total_withdrawn(self) -> float:
        """إجمالي المبالغ المسحوبة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(amount_egp) FROM withdrawals WHERE status = "approved"')
            result = cursor.fetchone()[0]
            return result if result else 0
    
    # ==================== دوال الدعوات ====================
    
    def add_referral(self, referrer_id: int, referred_id: int, referred_name: str, bonus_egp: float) -> bool:
        """إضافة دعوة جديدة مع منع التكرار"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, referred_name, bonus_egp, created_at, processed)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (referrer_id, referred_id, referred_name, bonus_egp, datetime.now().isoformat(), 0))
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Duplicate referral: {referrer_id} -> {referred_id}")
                return False
    
    def get_referral_count(self, user_id: int) -> int:
        """عدد الدعوات الناجحة للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
            return cursor.fetchone()[0]
    
    def get_referral_exists(self, referrer_id: int, referred_id: int) -> bool:
        """التحقق من وجود دعوة مسبقة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM referrals WHERE referrer_id = ? AND referred_id = ?
            ''', (referrer_id, referred_id))
            return cursor.fetchone() is not None
    
    def get_referrals_by_referred(self, referred_id: int) -> List[Dict]:
        """الحصول على الدعوات التي تمت بواسطة مستخدم معين (كمدعو)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM referrals WHERE referred_id = ?', (referred_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_referrals(self) -> List[Dict]:
        """الحصول على جميع الدعوات"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM referrals ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== دوال معالجة الدفعات ====================
    
    def get_referrals_batch(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """جلب الدعوات على دفعات صغيرة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM referrals 
                ORDER BY id ASC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_referrals_count_batch(self) -> int:
        """الحصول على إجمالي عدد الدعوات"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM referrals')
            return cursor.fetchone()[0]
    
    def get_users_batch(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """جلب المستخدمين على دفعات صغيرة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, balance_egp, referred_by, verified
                FROM users 
                ORDER BY user_id ASC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_unprocessed_referrals_batch(self, limit: int = 50) -> List[Dict]:
        """جلب الدعوات التي لم تتم معالجتها بعد"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM referrals 
                WHERE processed = 0 OR processed IS NULL
                ORDER BY id ASC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_referral_processed(self, referral_id: int):
        """تحديد دعوة كمعالجة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE referrals SET processed = 1, processed_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), referral_id))
    
    # ==================== دوال القنوات ====================
    
    def add_channel(self, channel_id: str, channel_name: str, channel_link: str = None) -> bool:
        """إضافة قناة جديدة"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO channels (id, name, link, added_at)
                    VALUES (?, ?, ?, ?)
                ''', (channel_id, channel_name, channel_link, datetime.now().isoformat()))
                return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_channel(self, channel_id: str) -> bool:
        """حذف قناة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM channels WHERE id = ?', (channel_id,))
            return cursor.rowcount > 0
    
    def get_channels(self) -> List[Dict]:
        """الحصول على جميع قنوات الاشتراك الإجباري"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM channels ORDER BY added_at')
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== دوال الإعدادات ====================
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """الحصول على إعداد"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default
    
    def set_setting(self, key: str, value: str):
        """تحديث إعداد"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now().isoformat()))
    
    def get_all_settings(self) -> Dict:
        """الحصول على جميع الإعدادات"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM settings')
            return {row[0]: row[1] for row in cursor.fetchall()}
    
    # ==================== دوال البيانات المؤقتة ====================
    
    def set_temp_data(self, user_id: int, data: Dict):
        """تخزين بيانات مؤقتة للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO temp_data (user_id, data, created_at)
                VALUES (?, ?, ?)
            ''', (user_id, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()))
    
    def get_temp_data(self, user_id: int) -> Optional[Dict]:
        """الحصول على البيانات المؤقتة للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT data FROM temp_data WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def delete_temp_data(self, user_id: int):
        """حذف البيانات المؤقتة للمستخدم"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM temp_data WHERE user_id = ?', (user_id,))
    
    def clear_old_temp_data(self, hours: int = 24):
        """حذف البيانات المؤقتة القديمة"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM temp_data WHERE created_at < ?', (cutoff,))
    
    # ==================== دوال مهمات التطبيقات ====================
    
    def add_app_task(self, title: str, description: str, image_url: str = None, 
                     app_link: str = None, reward_egp: float = 0, created_by: int = None) -> int:
        """إضافة مهمة تطبيق جديدة"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO app_tasks (title, description, image_url, app_link, reward_egp, created_at, created_by, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ''', (title, description, image_url, app_link, reward_egp, now, created_by))
            return cursor.lastrowid
    
    def get_app_task(self, task_id: int) -> Optional[Dict]:
        """الحصول على مهمة تطبيق"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM app_tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_active_app_tasks(self) -> List[Dict]:
        """الحصول على المهام النشطة فقط"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM app_tasks WHERE is_active = 1 ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_app_tasks(self) -> List[Dict]:
        """الحصول على جميع المهام"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM app_tasks ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def toggle_task_status(self, task_id: int, is_active: int):
        """تفعيل/تعطيل مهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE app_tasks SET is_active = ? WHERE id = ?', (is_active, task_id))
    
    def delete_app_task(self, task_id: int) -> bool:
        """حذف مهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM app_tasks WHERE id = ?', (task_id,))
            return cursor.rowcount > 0
    
    def update_app_task(self, task_id: int, **kwargs):
        """تحديث بيانات مهمة"""
        if not kwargs:
            return
        
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if not fields:
            return
        
        values.append(task_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE app_tasks SET {", ".join(fields)} WHERE id = ?', values)
    
    # ==================== دوال تنفيذ المهام ====================
    
    def submit_task_completion(self, user_id: int, task_id: int, screenshot_file_id: str) -> int:
        """تسجيل طلب إكمال مهمة"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_task_completions (user_id, task_id, screenshot_file_id, submitted_at, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (user_id, task_id, screenshot_file_id, now))
            return cursor.lastrowid
    
    def get_task_completion(self, completion_id: int) -> Optional[Dict]:
        """الحصول على طلب إكمال مهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_task_completions WHERE id = ?', (completion_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_pending_task_completions(self) -> List[Dict]:
        """الحصول على طلبات إكمال المهام المعلقة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM user_task_completions 
                WHERE status = 'pending' 
                ORDER BY submitted_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def complete_task_completion(self, completion_id: int, reward_egp: float):
        """قبول طلب إكمال مهمة"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_task_completions 
                SET status = 'approved', processed_at = ?, reward_egp = ?
                WHERE id = ?
            ''', (now, reward_egp, completion_id))
    
    def reject_task_completion(self, completion_id: int, admin_note: str = None):
        """رفض طلب إكمال مهمة"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_task_completions 
                SET status = 'rejected', processed_at = ?, admin_note = ?
                WHERE id = ?
            ''', (now, admin_note, completion_id))
    
    def get_pending_tasks_count(self) -> int:
        """عدد طلبات المهام المعلقة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_task_completions WHERE status = "pending"')
            return cursor.fetchone()[0]
    
    def get_total_tasks_completed(self) -> int:
        """عدد المهام المكتملة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM user_task_completions WHERE status = "approved"')
            return cursor.fetchone()[0]
    
    def get_total_task_earnings(self) -> float:
        """إجمالي أرباح المهام"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(reward_egp) FROM user_task_completions WHERE status = "approved"')
            result = cursor.fetchone()[0]
            return result if result else 0
    
    def get_user_task_completions(self, user_id: int, status: str = None) -> List[Dict]:
        """الحصول على طلبات إكمال المهام لمستخدم معين"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT * FROM user_task_completions 
                    WHERE user_id = ? AND status = ? 
                    ORDER BY submitted_at DESC
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT * FROM user_task_completions 
                    WHERE user_id = ? 
                    ORDER BY submitted_at DESC
                ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== دوال الـ 24 ساعة للمهام ====================
    
    def can_complete_app_task(self, user_id: int, task_id: int) -> bool:
        """التحقق إذا كان المستخدم يمكنه إكمال المهمة (مرت 24 ساعة من آخر مرة)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT completed_at FROM user_task_history 
                WHERE user_id = ? AND task_id = ? 
                ORDER BY completed_at DESC LIMIT 1
            ''', (user_id, task_id))
            row = cursor.fetchone()
            
            if not row:
                return True
            
            last_completed = datetime.fromisoformat(row['completed_at'])
            now = datetime.now()
            diff = now - last_completed
            return diff.total_seconds() >= 86400  # 24 ساعة
    
    def get_last_task_completion(self, user_id: int, task_id: int) -> Optional[str]:
        """جلب آخر مرة أكمل فيها المستخدم المهمة"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT completed_at FROM user_task_history 
                WHERE user_id = ? AND task_id = ? 
                ORDER BY completed_at DESC LIMIT 1
            ''', (user_id, task_id))
            row = cursor.fetchone()
            return row['completed_at'] if row else None
    
    def update_user_task_completion(self, user_id: int, task_id: int):
        """تحديث وقت آخر إكمال للمهمة"""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_task_history (user_id, task_id, completed_at)
                VALUES (?, ?, ?)
            ''', (user_id, task_id, now))