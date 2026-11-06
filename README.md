# رادار الفيوتشر | Futures Radar

نظام إشارات احترافي لعقود بينانس الآجلة (USDⓈ-M Perpetual)

- **فريمات**: 15 دقيقة + 1 ساعة
- **فلترة عالية** + ترتيب من الأقوى للأضعف
- **واجهة عربية كاملة** Dark Theme
- **مجاني 100%** (يعمل على Render Free Tier)

---

## المميزات

- مسح أكثر من 250 زوج حسب السيولة
- تحليل متعدد الفريمات (اتجاه + زخم + حجم + ATR)
- حساب تلقائي لـ Entry / Stop / 3 Targets
- Score من 1 إلى 10
- زر نسخ الخطة
- تحديث تلقائي كل 3 دقائق

---

## التشغيل المحلي

```bash
# 1. إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. تثبيت المتطلبات
pip install -r requirements.txt

# 3. تشغيل السيرفر
uvicorn main:app --host 0.0.0.0 --port 8000
```

ثم افتح: http://localhost:8000

---

## الرفع على Render.com (مجاني)

1. أنشئ حساب على [render.com](https://render.com)
2. New → **Web Service**
3. اربط مستودع GitHub (ارفع هذا المشروع أولاً)
4. الإعدادات:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. اختر **Free** plan
6. Deploy

بعد دقائق سيعطيك رابط مثل: `https://futures-radar-xxxx.onrender.com`

> ملاحظة: النسخة المجانية تنام بعد 15 دقيقة من عدم الاستخدام. أول طلب بعد النوم يأخذ 30-50 ثانية.

---

## هيكل المشروع

```
futures-radar/
├── main.py              # FastAPI + Scheduler
├── scanner.py           # منطق المسح وجلب البيانات
├── indicators.py        # المؤشرات الفنية + توليد الإشارات
├── requirements.txt
├── templates/
│   └── index.html       # الواجهة العربية
└── README.md
```

---

## تحذير مهم

هذا النظام **أداة مساعدة فقط** وليس نصيحة مالية.  
الأسواق متقلبة ولا يوجد نظام يعطي نتائج مضمونة 100%.  
استخدم إدارة مخاطر صارمة (لا تخاطر بأكثر من 1% من رأس المال في الصفقة الواحدة).

---

صُنع بحب للعرب المتداولين ❤️
