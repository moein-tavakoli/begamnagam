# پیکربندی ظرفیت۰٫۱۱٫۱ — ۲۸اکتبر۲۰۲۶

تنظیم ظرفیت با مجوز کارفرما روی `/opt/begamnagam/releases/0.11.1-capacity` فعال شد. image فرانت و بک‌اند همان۰٫۱۱٫۰است؛ تغییرات دیگر محیط کار و کاندیدای۰٫۱۲٫۰وارد این انتشار نشدند. این انتشار زیرساخت/اجراست و migration ندارد.

پیش از فعال‌سازی، کارفرما CT115 را پس از تعمیر Storage روشن کرد؛ root بدون `emergency_ro` و نوشتن همراه `fsync` موفق تأیید شد. علت اصلی Storage در این نشست از میزبان Proxmox قابل بازرسی نبود. dump رمز‌شدهٔ تازه و restore روی DB موقت با dispatch متوقف موفق بود؛۱۳۶فیلد رمز‌شده تأیید و archive رمز‌شده به دستگاه اپراتور کپی شد. DB تولید restore نشد.

Traefik با سقف۵۱۲MiB و `GOMEMLIMIT=384MiB`، سه فرانت یکسان روی loopback۳۰۰۰/۳۰۰۱/۳۰۰۲ با سقف هرکدام۷۶۸MiB و heap۳۸۴MiB، و backend با سه worker و دو thread برای هر worker و سقف۷۶۸MiB فعال‌اند. حافظهٔ worker۲۵۶وbeat۱۹۲MiB با `docker update` افزایش یافت و پردازش‌های صف restart نشدند. PostgreSQL/Redis/RabbitMQ و حجم‌ها recreate نشدند. مجموع سقف۱۰سرویس۴٬۴۴۸MiB است.

هر سه فرانت از یک build استفاده می‌کنند؛ nonce/CSP و پاسخ شخصی بدون cache حفظ‌اند. routing اختیاری سه upstream و healthcheck دارد. گواهی و مسیر تمدید از `shared/traefik-tls` مشترک استفاده می‌کنند و اطلاع reload به پوشهٔ release جاری می‌رود. SSL عمومی همچنان روی Nginx مرکزی خاتمه می‌یابد.

کنترل پس از انتشار:۲۲بررسی امنیت HTTP،۴۰بررسی SEO/اشتراک‌گذاری و audit خواندنی نقش PostgreSQL/Redis/config بدون خطا گذشتند. هشدار transport دیتابیس برای loopback و نیاز به مشاهدهٔ مستقل firewall/broker همچنان در audit عمومی مستند است؛ این فرمان به‌تنهایی بازبینی مجدد همهٔ ACLهای میزبان نیست. آزمون بار و soak کامل شد؛ نتیجهٔ نهایی پس از اصلاح Nginx در لینک زیر است.

## عملیات

از این انتشار، **هر سه فایل Compose باید همراه هم باشند**؛ فایل امنیتی یا ظرفیت را در recreate بعدی حذف نکنید:

```sh
cd /opt/begamnagam/current
docker compose --env-file .env.internal \
  -f compose.internal.yaml -f compose.hardened.yaml -f compose.performance.yaml ps
```

فرمان `up` بدون service/`--no-deps` ممکن است migrate یا سرویس‌های داده را هم وارد اجرا کند؛ برای اصلاح یک سرویس مشخص، همان سرویس‌ها را صریح انتخاب کنید. هنگام تعویض image فرانت، هر سه نمونه باید به همان image جدید منتقل شوند؛ تصویر با build متفاوت را در یک pool نگه ندارید.

## بازگشت تنظیم ظرفیت

نسخهٔ قبلی `/opt/begamnagam/releases/0.11.0` و فایل‌های قبلی دست‌نخورده‌اند. این بازگشت فقط تنظیم اجراست و schema/داده به عقب برنمی‌گردد. ابتدا از نبود عملیات انتشار/تست هم‌زمان مطمئن شوید. با فایل‌های قبلی و env خصوصی موجود، پراکسی را به routing تک‌نمونه recreate کنید؛ پس از سلامت مسیر۳۰۰۰، frontend2/frontend3 را متوقف کنید. آنگاه در صورت نیاز frontend/backend را با config قبلی recreate و current را هماهنگ کنید تا مسیر اعلان تمدید TLS با پوشهٔ bindشدهٔ پراکسی یکی باشد. کاهش فوری حافظهٔ سرویس درحال‌کار به زیر مصرف واقعی ممکن است OOM ایجاد کند؛ برای rollback از recreate و healthcheck استفاده کنید.

[نتایج پیش از تغییر](../performance-2026-10-28/README.fa.md) و [طرح/مانع Storage قبلی](../performance-2026-10-28/tuning.fa.md) تاریخی‌اند. مجوز تست شامل GETهای مشخص و task بی‌اثر است؛ OTP/SMS/پرداخت/AI زیر بار قرار نمی‌گیرند.

**نتیجهٔ نهایی:** [گزارش پس از اصلاح Nginx و آزمون۳۰دقیقه‌ای](../performance-2026-10-28/optimized.fa.md) کامل شده است؛ شرح اجرای درحال‌انجام در بالا به زمان rollout مربوط است.
