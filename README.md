# 🤖 @Reb7yBot — بوت الإحالات الاحترافي

## المتطلبات
- Python 3.11+
- PostgreSQL 14+
- Redis (اختياري، للأداء الأفضل)

---

## خطوات التثبيت

### 1. استنساخ المشروع وإعداد البيئة
```bash
cd reb7y_bot
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. إعداد ملف البيئة
```bash
cp .env.example .env
nano .env
```
عدّل القيم التالية في `.env`:
```
BOT_TOKEN=توكن_البوت_من_بوت_فاذر
DB_PASSWORD=كلمة_مرور_قاعدة_البيانات
SECRET_KEY=مفتاح_عشوائي_طويل
```

### 3. إنشاء قاعدة البيانات
```bash
# سجّل دخول PostgreSQL
psql -U postgres

# أنشئ قاعدة البيانات
CREATE DATABASE reb7y_bot;
\q
```
الـ Schema سيُنفَّذ تلقائياً عند أول تشغيل للبوت.

### 4. تشغيل البوت
```bash
python main.py
```

---

## 🛠️ أوامر لوحة الإدارة

أرسل `/admin` للمشرف للوصول إلى:

| الميزة | الوصف |
|--------|-------|
| ⚙️ الإعدادات | تعديل كل قيم البوت ديناميكياً |
| 📊 الإحصائيات | إجماليات المستخدمين، الأرباح، السحوبات |
| 👥 المستخدمون | حظر، رفع حظر، إضافة رصيد |
| 💸 السحوبات | قبول/رفض الطلبات مع إشعار المستخدم |
| 📢 البث | إرسال رسالة لجميع المستخدمين |
| 📣 القنوات | إضافة/حذف قنوات الاشتراك الإجباري |
| 🎟️ الأكواد | إنشاء وإدارة الأكواد الترويجية |
| 📰 الإعلانات | إنشاء وإدارة الإعلانات |
| 🚀 البوست | تفعيل مضاعفة المكافآت |
| 🚩 المبلغ عنهم | مراجعة المستخدمين المشبوهين |
| 📤 التصدير | تصدير بيانات المستخدمين CSV |

---

## 🏗️ هيكل المشروع

```
reb7y_bot/
├── main.py                  # نقطة الدخول الرئيسية
├── config.py                # إعدادات البيئة
├── schema.sql               # قاعدة البيانات
├── requirements.txt
├── .env.example
├── database/
│   └── db.py                # اتصال PostgreSQL
├── services/
│   ├── user_service.py      # منطق المستخدمين
│   ├── settings_service.py  # إعدادات ديناميكية
│   ├── withdrawal_service.py# السحوبات
│   ├── promo_service.py     # الأكواد والقنوات والإعلانات
│   └── security_service.py  # الكابتشا والحماية
├── handlers/
│   ├── start.py             # التسجيل والإحالة والكابتشا
│   ├── balance.py           # الرصيد والإحصائيات والمتصدرين
│   ├── daily.py             # المكافأة اليومية والأكواد
│   ├── withdraw.py          # السحوبات (FSM كامل)
│   ├── games.py             # الألعاب (عجلة + تخمين)
│   └── admin.py             # لوحة الإدارة الكاملة
├── keyboards/
│   └── keyboards.py         # جميع لوحات المفاتيح
├── middlewares/
│   └── middlewares.py       # حماية، rate limit، تتبع
└── utils/
    └── utils.py             # مساعدات التنسيق
```

---

## 🔧 نشر على السيرفر (Systemd)

```bash
sudo nano /etc/systemd/system/reb7y.service
```

```ini
[Unit]
Description=Reb7y Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/reb7y_bot
ExecStart=/home/ubuntu/reb7y_bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable reb7y
sudo systemctl start reb7y
sudo systemctl status reb7y
```

---

## 🐳 نشر بـ Docker (اختياري)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t reb7y-bot .
docker run -d --env-file .env --name reb7y reb7y-bot
```

---

## 🔐 الأمان

- ✅ كابتشا رياضية لكل مستخدم جديد
- ✅ Rate limiting على جميع الأحداث
- ✅ كشف الإحالات الوهمية والمشبوهة
- ✅ نظام تحذيرات تلقائية
- ✅ حظر مؤقت/دائم
- ✅ تسجيل كامل للنشاط
- ✅ جميع أوامر الإدارة محمية بـ ADMIN_ID

---

## 📞 الدعم

المشرف: @MN_BF
