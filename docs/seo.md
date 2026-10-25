# راهنمای SEO

این مخزن همچنان نسخهٔ demo محلی است. SEO فنی آماده شده، اما index عمومی به‌صورت پیش‌فرض خاموش است. فعال‌کردن index به مجوز انتشار عمومی و مبدأ واقعی HTTPS نیاز دارد و مجوز ارسال واقعی، پرداخت یا استقرار ایجاد نمی‌کند.

## متادیتا و مسیرها

صفحه‌های عمومی `/`، `/help` و `/privacy` عنوان و توضیح فارسی مستقل، canonical، Open Graph، Twitter Card و JSON-LD دارند. تصویر اشتراک‌گذاری محلی در `/images/social-card.png` با اندازهٔ۱۲۰۰×۶۳۰ استفاده می‌شود. لینک‌های داخلی با مسیرهای یکنواخت و متن قابل‌فهم نگه داشته می‌شوند. دادهٔ ساختاریافته فقط محتوای عمومی همان صفحه را توصیف می‌کند؛ شماره، متن خصوصی، توکن گیرنده و امتیاز/قیمت تأییدنشده نباید وارد آن شوند.

`/history`، `/preferences`، `/r` و زیرمسیرهایش، `/admin`، `/api` و صفحهٔ آفلاین نباید index شوند یا در sitemap بیایند. `noindex` و robots جای کنترل دسترسی را نمی‌گیرند؛ احراز هویت، CSRF و حفاظت توکن‌ها همچنان لازم‌اند.

| تنظیم | نتیجه |
| --- | --- |
| `APP_BASE_URL=http://localhost:3000` | مبدأ پیش‌فرض محلی برای canonical، URL اجتماعی، JSON-LD و sitemap |
| `APP_BASE_URL=https://begamnagam.ir` | مبدأ نهایی انتشار عمومی، بدون `www`؛ ثبت‌شده در `deploy/release.env.example` |
| `SEO_INDEXABLE=0` یا تعریف‌نشده | `noindex` و sitemap بدون URL؛ مناسب demo، CT داخلی و staging |
| `SEO_INDEXABLE=1` | فقط پس از مجوز انتشار و با مبدأ عمومی HTTPS؛ sitemap شامل سه مسیر عمومی است، مسیرهای خصوصی همچنان خارج می‌مانند |

مبدأ باید فقط scheme و host و در صورت نیاز port داشته باشد؛ credential، path، query و fragment را داخل آن نگذارید. از نشانی درخواست یا `Host` ورودی برای ساخت canonical استفاده نکنید. دامنهٔ نهایی اعلام‌شده `begamnagam.ir` و مبدأ یکتای انتشار `https://begamnagam.ir` است؛ تنظیم دامنه به‌تنهایی انتشار یا index عمومی را فعال نمی‌کند.

در build انتشار، canonical صفحه‌ها به `https://begamnagam.ir/`، `https://begamnagam.ir/help` و `https://begamnagam.ir/privacy` اشاره می‌کند. JSON-LD و تصویر اشتراک‌گذاری هم از همین مبدأ ساخته می‌شوند. پس از فعال‌سازی مجاز index، همین سه URL در `https://begamnagam.ir/sitemap.xml` می‌آیند و robots آن را معرفی می‌کند. تنظیم محلی و CT داخلی مبدأ خودشان را نگه می‌دارند.

در هر دو حالت، robots خواندن HTML را مجاز می‌گذارد تا موتور جست‌وجو `noindex` صفحه‌ها را ببیند؛ مسیرهای `/api/`، `/admin/` و `/static/admin/` منع می‌شوند. در حالت پیش‌فرض، نشانی sitemap هم در robots معرفی نمی‌شود. محافظت از index بر پایهٔ `noindex` است؛ احراز هویت و محدودیت دسترسی نیز مستقل برقرارند.

## محیط توسعه و ساخت انتشار

در اجرای نیتیو، `make dev-ui` همان `npm run dev` داخل `frontend/` است. متغیرهای SEO را در `frontend/.env.local` (بر اساس `frontend/.env.example`) یا محیط پردازش قرار دهید؛ فایل `.env` ریشهٔ Compose خودکار توسط این فرمان خوانده نمی‌شود. برای تغییر env یک بار dev server را دوباره اجرا کنید؛ برای تغییر source از Fast Refresh استفاده کنید.

**metadata، robots و sitemap این برنامه هنگام build فرانت تولید می‌شوند.** تغییر `APP_BASE_URL` یا `SEO_INDEXABLE` پس از ساخت، به build دوباره نیاز دارد؛ env زمان اجرا یا restart یک image آماده کافی نیست. `compose.yaml` مقادیر ریشه را به builder می‌فرستد. `compose.internal.yaml` و `compose.release.yaml` فقط image آماده را مصرف می‌کنند، بنابراین مقدار درست باید در همان image ثبت شده باشد.

نمونهٔ ساخت image برای یک بررسی انتشارِ جدا از ویرایش UI، از ریشهٔ مخزن و با متغیرهای بازبینی‌شدهٔ محیط:

```sh
docker build \
  --build-arg INTERNAL_API_URL=http://backend:8000 \
  --build-arg APP_BASE_URL="$APP_BASE_URL" \
  --build-arg SEO_INDEXABLE="${SEO_INDEXABLE:-0}" \
  -t "$FRONTEND_IMAGE" frontend
```

`APP_BASE_URL` و `FRONTEND_IMAGE` باید پیش از این فرمان export شده و غیرخالی باشند. برای CT خصوصی، مبدأ همان HTTPS داخلی و `SEO_INDEXABLE=0` است. برای انتشار عمومی، ابتدا مجوز و دامنهٔ واقعی بررسی می‌شود و سپس image با مقدار۱ ساخته و مرجع بازبینی‌شدهٔ آن در فایل انتشار قرار می‌گیرد. هیچ کلید یا credential را به build argهای frontend ندهید.

## بررسی پیش از انتشار عمومی

1. `npm test` و `npm run typecheck` را در `frontend/` اجرا کنید؛ بررسی خروجی واقعی production به `npm run build` جداگانه با env مقصد نیاز دارد.
2. HTML سه صفحهٔ عمومی را بررسی کنید: عنوان/توضیح، یک canonical مطلق به همان مبدأ، URL تصویر اشتراک‌گذاری، زبان فارسی و JSON-LD معتبر. URL خصوصی، توکن و اطلاعات کاربر نباید در خروجی باشند.
3. در demo، صفحات باید `noindex` و sitemap خالی باشد؛ `robots.txt` باید خواندن HTML را مجاز، API/admin را منع و نشانی sitemap را حذف کند. در image عمومیِ مجاز، sitemap باید دقیقاً سه URL عمومی با canonical هماهنگ داشته باشد و در robots معرفی شود؛ مسیرهای خصوصی باید همچنان `noindex` باشند.
4. JSON-LD عمومی را با [Schema Markup Validator](https://validator.schema.org/) و در صورت پشتیبانی نوع داده، [Rich Results Test](https://search.google.com/test/rich-results) بررسی کنید. برای سایت خصوصی، کد عمومیِ بدون اطلاعات کاربر را برای بررسی وارد کنید.
5. پس از انتشار مجاز، مالکیت دامنه را در Search Console تأیید، sitemap را ارسال و canonical/indexing را با URL Inspection بررسی کنید. دادهٔ ساختاریافته نمایش rich result یا رتبه را تضمین نمی‌کند.

## منابع

Context7 MCP در محیط این تغییر در دسترس نبود؛ راهنمای همراه نسخهٔ نصب‌شدهٔ Next.js و منابع رسمی زیر استفاده شدند:

- [Next.js Metadata API](https://nextjs.org/docs/app/api-reference/functions/generate-metadata)
- [Next.js JSON-LD و امن‌سازی محتوای script](https://nextjs.org/docs/app/guides/json-ld)
- [Next.js robots](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots) و [sitemap](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap)
- [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables)
- [Google: canonical و URLهای تکراری](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Google: سیاست دادهٔ ساختاریافته](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
