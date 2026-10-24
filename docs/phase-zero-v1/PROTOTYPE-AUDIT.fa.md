# ارزیابی خواندنی نمونه قبلی

شناسه: BN-AUDIT-001 | تاریخ: ۲۴ اکتبر ۲۰۲۶ | روش: بررسی source و اسناد، بدون اجرای برنامه/تست/سرویس

سه نوع شاهد جداست: «مشاهده کد این فاز»، «گزارش آزمون قبلی در docs/verification.md» و «آزموده‌نشده». snapshot پیش از بررسی ۶۷ فایل source/config در SOURCE-SNAPSHOT.json ثبت شده است؛ secret، دیتابیس و پوشه‌های build/dependency در آن نیستند. یکسان‌بودن hash همین دامنه در پایان بررسی می‌شود؛ این دامنه، همه فایل‌های workspace یا امنیت کل برنامه را اثبات نمی‌کند.

## ۱. نتیجه استفاده مجدد

| بخش | شاهد کد | تصمیم پیشنهادی و کار باقی‌مانده |
| --- | --- | --- |
| Next.js و فارسی RTL | frontend/package.json و ساختار فعلی | حفظ چارچوب/فونت/اجزای مناسب؛ تطبیق جریان quote و معیارهای موبایل کامل |
| manifest | frontend/public/manifest.webmanifest:1؛ یک icon.svg در خط ۱۲ | تکمیل اساسی: id پایدار، PNG192/512، maskable و iOS؛ manifest تنها کافی نیست |
| Service Worker و آفلاین | جست‌وجوی source برای serviceWorker/sw.js/install/offline؛ worker/ثبت آن پیدا نشد | **مفقود در دامنه بررسی**؛ طراحی و پیاده‌سازی در فاز مجاز، تست دستگاه/نسخه/cache لازم |
| OTP و session/CSRF | backend/core/views.py:68 و :89؛ backend/core/services.py:25 | پایه قابل استفاده؛ بازبینی proxy/rate، بودجه، provider واقعی و سیاست جدید لازم |
| قالب و moderation | backend/core/moderation.py:23 و :87 | کاتالوگ و انتخاب template_id قابل استفاده؛ بازنویسی آزاد نیست؛ فیلتر regex پوشش معنایی کامل نیست |
| quote قیمت ثابت | backend/core/models.py:27؛ backend/core/views.py:142 | snapshot پایه حفظ؛ تغییر قرارداد به گیرنده/URL/تعداد بخش نهایی قبل خرید، با نسخه متن |
| سفارش و قفل PG | backend/core/services.py:90 | idempotency و قفل‌ها پایه خوب؛ جفت ۳۰روزه، reservation مستقل و فرایند quote جدید لازم |
| cooldown | backend/core/services.py:157 | last_sent_at اکنون هنگام پرداخت demo ثبت می‌شود؛ در طرح هدف رزرو و پذیرش provider جدا شوند |
| demo payment | backend/core/services.py:138 | حفظ adapter آزمایشی آشکار؛ provider/paymentattempt/ledger/refund/verify مستقل وجود ندارند |
| مدل وضعیت | backend/core/models.py:46 | وضعیت محدود awaiting_payment/queued/delivered_demo/cancelled/failed؛ برای چرخه واقعی کافی نیست |
| outbox/worker | backend/core/services.py:159؛ backend/core/tasks.py:16 | حفظ الگو و reconcile؛ worker فعلی فقط demo است؛ تماس بیرونی آینده نباید داخل قفل بلند دیتابیس قرار گیرد |
| ارسال واقعی | backend/core/tasks.py:35 | فقط console/demo، بدون provider delivery receipt؛ delivered_demo هیچ مدرک ارسال واقعی نیست |
| تنظیم ترجیح | backend/core/views.py:190 | ترجیح شماره خود با نشست OTP پایه قابل استفاده؛ لینک stop/report بی‌حساب، grant و abuse case در مدل فعلی نیست |
| مدیریت | backend/core/admin.py:6 | چند مدل readonly و ویرایش blocked؛ پایه مفید، ولی پنل رسیدگی/refund، نقش تفکیک‌شده و ممیزی دامنه کامل نیست |
| حذف داده | backend/core/management/commands/prune_private_data.py:13 | OTP/quote رهاشده/audit و حذف ciphertext بعضی orderها؛ تمام retention جدید، حساب/متن/backup/financial پوشش داده نشده |
| امنیت مرورگر | frontend/next.config.ts:29 | چند header پایه؛ سیاست امن SW/cache و آزمون logout/Back روی PWA هنوز اثبات نشده |
| CI/Compose/docs | .github، compose.yaml، docs/verification.md | حفظ به‌عنوان مبنا؛ تکرار محیط پاک و نسخه‌های واقعی قبل G1 لازم |

شماره خط‌ها مربوط به snapshot همین تحویل‌اند و پس از توسعه می‌توانند عوض شوند. هیچ مورد مفقود در این فاز تکمیل نشده است.

## ۲. شواهد تاریخی، بدون اجرای مجدد

گزارش قبلی docs/verification.md از ۳۲ تست بک‌اند روی PostgreSQL17/Redis، هفت تست فرانت، typecheck/build و smoke با worker مستقل و بررسی مرورگر خبر می‌دهد. این‌ها **نتیجه گزارش‌شده قبلی** هستند؛ صحت اجرای اکنون یا پذیرش MF/PW برنامه جدید از آن‌ها نتیجه نمی‌شود.

محدودیت‌های همان گزارش: cryptography در requirements نسخه 46.0.7 ولی اجرای قبلی با نصب 44.0.2 بوده؛ build کامل Docker با مشکل شبکه/CDN تکمیل نشده؛ تست صف با image موجود RabbitMQ4.2.9 بوده و فایل اصلی4.4 را مشخص کرده؛ CI روی GitHub اجرا نشده؛ کیفیت مدل واقعی، SMS/درگاه زنده و بار هدف اندازه‌گیری نشده‌اند. نسخه‌های وابستگی موجود صرفاً گزارش snapshot‌اند، نه تجویز نصب تازه.

## ۳. اولویت اصلاح پس از مجوز

۱. **پیش از G1/G2:** تثبیت نسخه/محیط، جداسازی مدل مالی/ارسال، قرارداد quote، عدم نشت، قیود/سهمیه‌ها و بنیاد PWA.

۲. **پیش از G2:** manifest کامل، SW، نصب واقعی Android/iOS، آفلاین امن، update پایه و مسیر کامل demo روی موبایل. مشاهده UI در اندازه 375 یا پاسخ 200 manifest جای این شواهد را نمی‌گیرد.

۳. **پیش از G3:** provider منتخب/مجاز، verify، refund، idempotency بیرونی، unknown/reconcile، قیمت و بخش نهایی، بدون retry کور.

۴. **پیش از G4/G5:** stop/report بدون حساب، retention کامل، کنترل مدیر، emergency stop، backup/restore و سخت‌سازی cache/update؛ مسئول و بودجه پایلوت.

بخش آماده کنارگذاشتن/محدودکردن: `delivered_demo` و pay-demo فقط محیط آزمایشی؛ مدل تک‌محوری status مبنای نهایی live نباشد؛ filter کلمات معیار قطعی ایمنی تلقی نشود؛ manifest ناقص به‌عنوان PWA تحویل‌شده عرضه نشود. این‌ها توصیه audit هستند، نه تغییر اعمال‌شده.

## ۴. مرز صحت‌سنجی این فاز

در این فاز فقط hash منابع و بسته اسناد، پوشش شناسه نیازمندی‌ها و پیوندهای داخلی بررسی می‌شود. همه تست‌های پذیرش برنامه جدید NOT TESTED باقی می‌مانند. مجوز فقط مستندات فاز صفر بوده؛ هیچ dependency نصب، migration، build، تست برنامه، اجرای CI، پیامک یا پرداخت تازه‌ای انجام نشده است.
