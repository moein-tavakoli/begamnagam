# ساخت و ادامهٔ اصلاحات امنیتی ۳٫۱٫۴

این راهنما برنامهٔ ادامهٔ کار است، **شاهد استقرار نیست**. گزارش وضعیت واقعی و موارد باز در [ارزیابی امنیت](production-security-assessment-2026-11-17.fa.md) و digest خروجی‌های بررسی‌شده در [manifest محلی](../deploy/security-images-3.1.4.env) ثبت شده‌اند. مجوز قبلیِ آزمون بدون اختلال، اجازهٔ توقف دیتابیس یا Docker را ایجاد نمی‌کند؛ استقرار تابع [سیاست مخزن](../AGENTS.md#deployment-policy) است.

## بازتولید imageها

فایل‌های Dockerfile با پایهٔ رسمیِ tag+digest کار می‌کنند. در ارزیابی، mirror رسمی `public.ecr.aws/docker/library/` با همان digest برای دسترسی به imageهای پایه استفاده شد. اگر mirror لازم بود، فقط prefix منبع را عوض کنید و digest را ثابت نگه دارید؛ image ناشناس یا tag شناور جایگزین نشود.

```sh
docker build --platform linux/amd64 -t begamnagam-security/backend:3.1.4 backend
docker build --platform linux/amd64 \
  --build-arg INTERNAL_API_URL=http://backend:8000 \
  --build-arg APP_BASE_URL=https://begamnagam.ir \
  --build-arg SEO_INDEXABLE=1 \
  -t begamnagam-security/frontend:3.1.4 frontend
```

چهار image زیرساخت با `deploy/Dockerfile.security-alpine` از پایه‌های دقیقِ `deploy/internal.env.example` ساخته می‌شوند؛ این مرحله zlib را به `1.4-r0` می‌رساند و entrypoint، user و volume پایه را حفظ می‌کند. نمونه:

```sh
docker build --platform linux/amd64 \
  -f deploy/Dockerfile.security-alpine \
  --build-arg BASE_IMAGE=redis:7.4.12-alpine3.22@sha256:7f7d30b7fdd09467bac58198a1f166dd69789d348d4fe859cccb20e0cf287fbe \
  -t begamnagam-security/redis:3.1.4 deploy
```

همین الگو برای postgres، rabbitmq و proxy با پایهٔ متناظر اعمال می‌شود. imageهای پیش‌فرض Compose، پایهٔ upstream هستند؛ برای خروجی دارای اصلاح zlib از **manifest خروجی ساخته‌شده** استفاده کنید. Debian بک‌اند هم zlib مشخص‌شده در Dockerfile را نصب می‌کند. اگر نسخهٔ دقیق بسته از مخزن حذف شده بود، نسخهٔ بعدی را بررسی، دوباره scan و ثبت کنید؛ pin را بی‌بررسی حذف نکنید.

هر rebuild ممکن است digest خروجی تازه بدهد. imageهای تازه را با DB روز اسکن و تست کنید، سپس manifest و شواهد را به digest واقعی تغییر دهید؛ نتیجهٔ اسکن قدیمی به image تازه نسبت داده نشود. backend اجرایی دیگر pip ندارد؛ انتشار افزایشیِ متکی به `pip install` در image فعال جایگزین build کامل نیست.

## دروازهٔ انتشار مجاز

۱. درخواست صریح انتشارِ همین تغییر و زمان نگهداریِ سرویس‌های تک‌نمونه ثبت شود. promotion از dev به prod فقط با PR و گذر سه بررسی backend/frontend/compose است؛ push و merge از نسخه‌بندی استنباط نشوند.

۲. imageهای تأییدشده منتقل و digest آن‌ها پس از load کنترل شود. از build روی سرور زنده برای این اسکن استفاده نشود. env خصوصی، کلیدها، نقش runtime دیتابیس، تنظیمات provider واقعی، سقف هدیه، idempotency و سابقهٔ حذف پیام حفظ شوند.

۳. پیش از recreate، snapshot تنظیمات و شناسهٔ imageهای قبلی و بکاپ قابل بازیابی ثبت شود. برای بازگرداندن دیتابیس، الزام [حفظ قطع دسترسی پیام](operations.md#حفظ-قطع-دسترسی-پیام-در-بازیابی) اجرا شود؛ بکاپ قدیمی نباید پیام پنهان‌شده را دوباره در دسترس کاربر قرار دهد.

۴. manifest فقط متغیرهای image را override می‌کند؛ بعد از env خصوصی داده شود. هر سه فایل Compose ضروری‌اند. دستور زیر صرفاً اعتبارسنجی است و سرویس را تغییر نمی‌دهد:

```sh
docker compose --env-file .env.internal \
  --env-file deploy/security-images-3.1.4.env \
  -f compose.internal.yaml -f compose.hardened.yaml -f compose.performance.yaml \
  -p begamnagam-internal config --quiet
```

۵. ترتیب توقف کنترل‌شدهٔ worker/beat، تخلیهٔ کار جاری بدون لغو/بازپخش پیام، تعویض سرویس داده و بازگشت سلامت باید قبل از پنجره مشخص باشد. به‌دلیل دیتابیس و broker تک‌نمونه، `up --force-recreate` هم‌زمان بدون پنجرهٔ مجاز اجرا نشود. هر شش فرانت یک image تأییدشده بگیرند.

۶. قبل و بعد از انتشار، نسخه، وضعیت health، خطاها، صف و زمان پاسخ بررسی شوند. `scripts/check-security-probes.py` فقط با مجوزِ همان هدف و TLS معتبر اجرا شود؛ یک ثانیه فاصله، health guard، بدون کوکی و بدون ذخیرهٔ پاسخ دارد. `scripts/smoke.py` مخصوص demo است و روی production اجرا نشود. آزمون محصولِ کاربر همچنان باید provider واقعی داشته باشد؛ سرویس را برای سبزشدن تست به demo تبدیل نکنید.

## نگهداری میزبان و موارد باز scanner

ارتقای Docker/containerd/runc و۲۷بستهٔ باقی‌ماندهٔ میزبان، جدا از انتشار برنامه برنامه‌ریزی شود. live-restore خاموش است؛ ابتدا سازگاری نسخهٔ منتخب با Compose، داده و شبکهٔ host در محیط جدا بررسی شود. قرارگرفتن فایل جدید روی دیسک به معنی رفع نسخهٔ قدیمیِ بارشده در حافظه نیست؛ فرایندهای ثبت‌شده در شواهد باید در پنجرهٔ نگهداری reload/restart و دوباره بررسی شوند. کرنل Proxmox و OSِ Nginx مرکزی در مرحلهٔ جدا و با دسترسی/مجوز خودشان بررسی می‌شوند.

هشدارهای gosu و OpenTelemetry در گزارش باقی مانده‌اند. از ignore عمومی یا ادعای صفر آسیب‌پذیری استفاده نشود؛ برای helper، upstream با Go و dependency جدید پیگیری و برای فعال‌کردن telemetry، reachability و نسخهٔ اصلاح‌شده دوباره بررسی شود. اسکن روز انتشار باید هشدارهای تازه را هم لحاظ کند.
