# راهنمای SEO

SEO فنی برای محیط محلی و انتشار عمومی آماده است. index عمومی به‌صورت پیش‌فرض خاموش است؛ پروفایل پیامک واقعی و تنظیمات SEO مستقل‌اند. فعال‌کردن index به مبدأ عمومی HTTPS و تنظیم صریح نیاز دارد و به‌تنهایی ارسال واقعی، پرداخت یا استقرار را فعال نمی‌کند.

## متادیتا و مسیرها

صفحه‌های عمومی `/`، `/help`، `/privacy`، `/links`، `/pricing` و `/about` عنوان و توضیح فارسی مستقل، canonical، Open Graph، Twitter Card و JSON-LD دارند. تصویر اشتراک‌گذاری محلی در `/images/social-card.png` با اندازهٔ۱۲۰۰×۶۳۰ استفاده می‌شود. لینک‌های داخلی با مسیرهای یکنواخت و متن قابل‌فهم نگه داشته می‌شوند. دادهٔ ساختاریافته فقط محتوای عمومی همان صفحه را توصیف می‌کند؛ شماره، متن خصوصی، توکن گیرنده و امتیاز/قیمت تأییدنشده نباید وارد آن شوند.

`/profile`، `/history`، `/invitations`، `/preferences`، `/r` و زیرمسیرهایش، `/admin`، `/api`، صفحهٔ آفلاین و خطاهای۴۰۴ نباید index شوند یا در sitemap بیایند. صفحات خصوصی عنوان و توضیح مستقل و عمومی دارند، اما canonical، Open Graph، Twitter Card و JSON-LD عمومی را به ارث نمی‌برند. متادیتا هیچ اطلاعاتی از نشست کاربر نمی‌خواند. `noindex` و robots جای کنترل دسترسی را نمی‌گیرند؛ احراز هویت، CSRF و حفاظت توکن‌ها همچنان لازم‌اند.

## متاتگ و دادهٔ ساختاریافته

تعریف مرکزی در `frontend/lib/seo.ts` است. `rootMetadata` زبان/RTL در layout، نام برنامه، manifest، آیکون‌های SVG/PNG، آیکون Apple با اندازهٔ۱۸۰، تنظیمات نصب و `no-referrer` را همراهی می‌کند. canonical و پیش‌نمایش اجتماعی فقط با `publicMetadata` به صفحات عمومی اضافه می‌شوند. صفحات خطا و خصوصی از پیش‌فرض `noindex` استفاده می‌کنند.

متاتگ تأیید اینماد با مقدار `5251197` فقط در متادیتای `frontend/app/page.tsx` تعریف شده و در `head` صفحهٔ اصلی با نام `enamad` قرار می‌گیرد. این تغییر با مجوز صریح در ۲۰۲۶-۱۰-۲۸ روی هر شش فرانت منتشر شد؛ حضور یک تگ در `head` صفحهٔ اصلی با HTTPS دامنه از Nginx اصلی و گواهی معتبر تأیید شد. مسیر IP عمومی از شبکهٔ اپراتور در زمان بررسی در دسترس نبود. [شواهد انتشار](deployments/ct115-0.12.1-enamad.json).

هر صفحهٔ عمومی عنوان، توضیح، نویسنده/ناشر برند و canonical یکتا دارد. Open Graph شامل عنوان، توضیح، URL صفحه، نام سایت، زبان `fa_IR` و تصویر PNG با URL مطلق، نوع MIME، عرض، ارتفاع و متن جایگزین است؛ برای مبدأ HTTPS، `og:image:secure_url` هم تولید می‌شود. Twitter Card از نوع `summary_large_image` با عنوان/توضیح همان صفحه و تصویر/متن جایگزین مشترک است. متاتگ‌ها در HTML اولیهٔ head حاضرند؛ برای پیش‌نمایش به اجرای JavaScript یا دریافت bootstrap نیاز نیست. Telegram، WhatsApp، Facebook، X/Twitter، LinkedIn، Slack و Discord از این خروجی استاندارد استفاده می‌کنند؛ بررسی خودکار شناسهٔ خزندهٔ آن‌ها را می‌فرستد و حضور متاتگ‌ها را در head می‌سنجد. نمایش واقعی هر پیام‌رسان و کش آن پس از انتشار باید جدا بررسی شود.

| صفحه | JSON-LD |
| --- | --- |
| همهٔ صفحات عمومی | `Organization` برای برند بگم نگم، `WebSite`، دو `ImageObject` برای لوگو و تصویر اشتراک‌گذاری و موجودیت صفحه با شناسه‌های canonical ثابت |
| `/` | `WebPage` متصل به `WebApplication` و `Service`؛ قابلیت‌ها، راهنمای نرم‌افزار، زبان و پوشش شماره‌های ایران |
| `/help` | `FAQPage` و `BreadcrumbList`؛ متن سؤال/جواب دقیقاً از منبع مشترک `help-content.ts` می‌آید و هر سؤال پیوند ثابت به بخش قابل‌مشاهدهٔ خودش دارد |
| `/privacy`، `/links` و `/pricing` | `WebPage` و `BreadcrumbList` |
| `/about` | `AboutPage` متصل به موجودیت برند و `BreadcrumbList` |
| صفحات خصوصی، لینک گیرنده و آفلاین | بدون JSON-LD عمومی و بدون پیش‌نمایش حاوی دادهٔ خصوصی |

طبق تصمیم کارفرما، فقط نام «بگم نگم»، نام لاتین `BegamNagam`، دامنه و نشان موجود مبنا هستند. `Organization` موجودیت برند سرویس است؛ `legalName`، نشانی، تلفن، کدپستی، ایمیل، شبکهٔ اجتماعی و اطلاعات ثبتی ادعا نمی‌شوند. تا دریافت اطلاعات واقعی، `sameAs` و `ContactPoint` اضافه نکنید. قیمت/`Offer`، امتیاز/نقد، تاریخ انتشار/ویرایش و `SearchAction` ساختگی وجود ندارند. هدیهٔ محدود به معنی رایگان‌بودن نامحدود نرم‌افزار نیست. صفحات فقط فارسی‌اند و alternate زبان ساختگی تولید نمی‌شود. متاتگ keywords، refresh، revisit-after و برچسب‌های تکراری برای پرکردن head اضافه نشده‌اند.

سیاست sitemap همچنان فقط URLهای canonical عمومی را شامل می‌شود؛ تاریخ `lastModified` نباید با هر build یا درخواست عوض شود. JSON-LD فقط با script معمولی و escape کاراکتر `<` رندر می‌شود. مقدار JSON-LD از محتوای عمومی ثابت می‌آید و هرگز از query، Host یا وضعیت حساب ساخته نمی‌شود.

| تنظیم | نتیجه |
| --- | --- |
| `APP_BASE_URL=http://localhost:3000` | مبدأ پیش‌فرض محلی برای canonical، URL اجتماعی، JSON-LD و sitemap |
| `APP_BASE_URL=https://begamnagam.ir` | مبدأ نهایی انتشار عمومی، بدون `www`؛ ثبت‌شده در `deploy/release.env.example` |
| `SEO_INDEXABLE=0` یا تعریف‌نشده | `noindex` و sitemap بدون URL؛ مناسب demo، CT داخلی و staging |
| `SEO_INDEXABLE=1` | فقط پس از مجوز انتشار و با مبدأ عمومی HTTPS؛ sitemap شامل شش مسیر عمومی است، مسیرهای خصوصی همچنان خارج می‌مانند |

مبدأ باید فقط scheme و host و در صورت نیاز port داشته باشد؛ credential، path، query و fragment را داخل آن نگذارید. از نشانی درخواست یا `Host` ورودی برای ساخت canonical استفاده نکنید. دامنهٔ نهایی اعلام‌شده `begamnagam.ir` و مبدأ یکتای انتشار `https://begamnagam.ir` است؛ تنظیم دامنه به‌تنهایی انتشار یا index عمومی را فعال نمی‌کند.

در build انتشار، canonical صفحه‌ها به `https://begamnagam.ir/`، `https://begamnagam.ir/help` ، `https://begamnagam.ir/privacy` ، `https://begamnagam.ir/links`، `https://begamnagam.ir/pricing` و `https://begamnagam.ir/about` اشاره می‌کند. JSON-LD و تصویر اشتراک‌گذاری هم از همین مبدأ ساخته می‌شوند. پس از فعال‌سازی مجاز index، همین شش URL در `https://begamnagam.ir/sitemap.xml` می‌آیند و robots آن را معرفی می‌کند. تنظیم محلی و CT داخلی مبدأ خودشان را نگه می‌دارند.

در هر دو حالت، robots خواندن HTML را مجاز می‌گذارد تا موتور جست‌وجو `noindex` صفحه‌ها را ببیند؛ مسیرهای `/api/`، `/admin/` و `/static/admin/` منع می‌شوند. در حالت پیش‌فرض، نشانی sitemap هم در robots معرفی نمی‌شود. محافظت از index بر پایهٔ `noindex` است؛ احراز هویت و محدودیت دسترسی نیز مستقل برقرارند.

## محیط توسعه و ساخت انتشار

در اجرای نیتیو، `make dev-ui` همان `npm run dev` داخل `frontend/` است. متغیرهای SEO را در `frontend/.env.local` (بر اساس `frontend/.env.example`) یا محیط پردازش قرار دهید؛ فایل `.env` ریشهٔ Compose خودکار توسط این فرمان خوانده نمی‌شود. برای تغییر env یک بار dev server را دوباره اجرا کنید؛ برای تغییر source از Fast Refresh استفاده کنید.

**مبدأ و flag سئو هنگام build فرانت تثبیت می‌شوند؛ robots و sitemap نیز همان زمان ساخته می‌شوند.** پس از هاردنینگ CSP، HTML و JSON-LD با nonce هر درخواست به‌صورت پویا رندر می‌شوند و `private, no-store` دارند. متادیتای عمومی همچنان در head حضور دارد. تغییر `APP_BASE_URL` یا `SEO_INDEXABLE` به build دوباره نیاز دارد؛ env زمان اجرا یا restart یک image آماده کافی نیست. این دو مقدار عمومی در تنظیم `env` فرانت تثبیت شده‌اند؛ هیچ credential نباید به آن اضافه شود. `compose.yaml` مقادیر ریشه را به builder می‌فرستد. `compose.internal.yaml` و `compose.release.yaml` فقط image آماده را مصرف می‌کنند، بنابراین مقدار درست باید در همان image ثبت شده باشد. جزئیات امنیت و هزینهٔ رندر پویا در [گزارش هاردنینگ](security-audit-2026-10-27.fa.md) آمده است.

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
2. HTML صفحه‌های عمومی را بررسی کنید: عنوان/توضیح، یک canonical مطلق به همان مبدأ، URL تصویر اشتراک‌گذاری، زبان فارسی و JSON-LD معتبر. URL خصوصی، توکن و اطلاعات کاربر نباید در خروجی باشند.
3. در demo، صفحات باید `noindex` و sitemap خالی باشد؛ `robots.txt` باید خواندن HTML را مجاز، API/admin را منع و نشانی sitemap را حذف کند. در image عمومیِ مجاز، sitemap باید دقیقاً شش URL عمومی با canonical هماهنگ داشته باشد و در robots معرفی شود؛ مسیرهای خصوصی باید همچنان `noindex` باشند.
4. JSON-LD عمومی را با [Schema Markup Validator](https://validator.schema.org/) و در صورت پشتیبانی نوع داده، [Rich Results Test](https://search.google.com/test/rich-results) بررسی کنید. برای سایت خصوصی، کد عمومیِ بدون اطلاعات کاربر را برای بررسی وارد کنید.
5. پس از انتشار مجاز، مالکیت دامنه را در Search Console تأیید، sitemap را ارسال و canonical/indexing را با URL Inspection بررسی کنید. دادهٔ ساختاریافته نمایش rich result یا رتبه را تضمین نمی‌کند.

### بررسی خودکار HTML و خزنده‌های اشتراک‌گذاری

اسکریپت فقط GET بدون کوکی می‌فرستد؛ API، ورود، OTP، ارسال پیام، پرداخت و توقف دریافت را اجرا نمی‌کند. کد لینک گیرنده در این بررسی ساختگی است و GET آن تغییری در حساب ایجاد نمی‌کند. هنگام بررسی build عمومی روی localhost، assetها هم فقط از همان origin محلی خوانده می‌شوند.

برای محصول واقعی محلی با گواهی تولیدشده توسط `make dev-product`:

```sh
python3 scripts/check-seo.py \
  --base-url https://localhost:3000 \
  --canonical-origin https://localhost:3000 \
  --ca-file .local/local-product/localhost.crt
```

برای بررسی یک build عمومی که جداگانه روی localhost:3101 اجرا شده است:

```sh
python3 scripts/check-seo.py \
  --base-url http://127.0.0.1:3101 \
  --canonical-origin https://begamnagam.ir \
  --expect-indexable
```

پس از انتشار مجاز همین فرمان با `--base-url https://begamnagam.ir` قابل اجراست. بررسی شامل۴۰درخواست، سه صفحهٔ عمومی با query بازاریابی و هفت شناسهٔ خزنده، شش صفحهٔ خصوصی از جمله مدیریت،۴۰۴، redirect امن گیرنده، آفلاین، PNG واقعی با ابعاد صحیح، manifest، robots و sitemap است. تمام ارجاعات graph بین صفحات resolve می‌شوند و متن FAQ با محتوای HTML تطبیق داده می‌شود. این اسکریپت جای نتیجهٔ Schema Validator یا پیش‌نمایش داخل خود پیام‌رسان را نمی‌گیرد. Next.js اسلش انتهایی origin را در canonical/OG ریشهٔ HTML حذف می‌کند؛ `https://begamnagam.ir` و `https://begamnagam.ir/` همان URL ریشه‌اند.

## نتیجهٔ بررسی ۲۰۲۶-۱۰-۲۷

- `npm test`: هر۳۵آزمون موفق؛ شامل پوشش تمام مسیرهای صفحه، سیاست ایندکس، تصاویر واقعی و graphها.
- `npm run typecheck`: موفق.
- `npm run build`: موفق در کپی مستقل محلی با `APP_BASE_URL=https://begamnagam.ir` و `SEO_INDEXABLE=1`؛ dev server اصلی بدون توقف ادامه داشت.
- `scripts/check-seo.py`: هر۴۰درخواست در محیط توسعهٔ HTTPS با `noindex` و هر۴۰درخواست در build انتشار محلی با ایندکس فعال موفق بودند؛ اجرای نهایی شامل مسیر مدیریت و nonceهای CSP نیز بود.
- هر سه JSON-LD عمومی جداگانه با روش Code snippet در [Schema Markup Validator](https://validator.schema.org/) بررسی شدند: صفر خطا و صفر هشدار؛ فقط دادهٔ عمومی برند ارسال شد.
- نمایش پاسخ قطع دریافت و عنوان/متادیتا در مرورگر دسکتاپ و عرض۳۷۵پیکسل بررسی شد؛ عرض سند۳۷۵بود و اسکرول افقی نداشت.

تغییرات فقط محلی‌اند؛ در این نوبت روی سرور مستقر نشده‌اند. تست خزنده‌ها خواندن HTML است و آزمون ارسال واقعی لینک در داخل پیام‌رسان‌ها نیست. رتبه، ایندکس‌شدن یا نمایش rich result از نتیجهٔ Schema Validator استنتاج نمی‌شود.

## GEO و دسترسی AI

صفحهٔ معرفی، پاسخ‌های قابل ارجاع، تفکیک خزندهٔ جست‌وجو از آموزش و فایل اختیاری `llms.txt` در نسخهٔ۰٫۱۳٫۰ منتشر و روی HTTPS دامنه از Nginx مرکزی آزموده شدند. دسترسی مستقل اینترنتی و ایندکس واقعی هنوز تأیید نشده‌اند. سیاست کارفرما «جست‌وجو و پاسخ مجاز، آموزش مسدود» است؛ توضیح محدودیت Google-Extended و شواهد کامل در [راهنمای GEO](geo.fa.md) آمده است.

## منابع

Context7 MCP در محیط این تغییر در دسترس نبود؛ راهنمای همراه نسخهٔ نصب‌شدهٔ Next.js و منابع رسمی زیر استفاده شدند:

- [Next.js Metadata API](https://nextjs.org/docs/app/api-reference/functions/generate-metadata)
- [Next.js JSON-LD و امن‌سازی محتوای script](https://nextjs.org/docs/app/guides/json-ld)
- [Next.js robots](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots) و [sitemap](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap)
- [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables)
- [Google: canonical و URLهای تکراری](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Google: سیاست دادهٔ ساختاریافته](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
- [Google: اطلاعات برند/Organization](https://developers.google.com/search/docs/appearance/structured-data/organization)
- [Open Graph protocol و مشخصات تصویر](https://ogp.me/)
- [Schema.org: WebApplication](https://schema.org/WebApplication)، [Service](https://schema.org/Service) و [ImageObject](https://schema.org/ImageObject)

صفحهٔ `/links` یک صفحهٔ عمومی برای لینک بیو، با چیدمان مستقل مناسب گوشی و همان رنگ/فونت محصول است. نشانی‌های شبکه‌های اجتماعی از شناسه‌های اعلام‌شدهٔ کارفرما ساخته شده‌اند؛ لینک‌ها با `noopener noreferrer` در زبانهٔ جدید باز می‌شوند. به ورود یا موفقیت bootstrap وابسته نیست. تغییر حاضر محلی است و مجوز انتشار تازه نگرفته است.
