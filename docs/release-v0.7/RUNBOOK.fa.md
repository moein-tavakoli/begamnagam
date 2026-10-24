# اجرای نسخه نامزد و بازگشت —۰٫۷

این راهنما تنظیمات قابل بررسی را تحویل می‌دهد؛ استقرار بیرونی اجرا نشده است. محیط فعلی localhost:3000 با hot reload و providerهای demo باقی می‌ماند. فایل `compose.release.yaml` مستقل است؛ آن را با Compose توسعه merge نکنید، چون پورت‌های demo نباید به تنظیم انتشار وارد شوند.

## آماده‌سازی اپراتور

۱. [بررسی‌های انسانی](HUMAN-REVIEW.fa.md) و موارد G3/G5/G6 را اجرا و شاهد ثبت کنید. قرارداد/تعرفه/دامنه/بودجه واقعی، افراد پشتیبانی و مالی، کلیدها و مسیر refund پس از تسویه باید تعیین شوند. فایل JSON به‌خودی‌خود امضای کارفرما نیست.

۲. imageها را از build بازبینی‌شده به digest ثابت ثبت کنید. `deploy/release.env.example` را به فایل ignored با دسترسی0600 به نام `.env.release` کپی کنید و تمام placeholderها را عوض کنید. کلید HMAC پایدار و کلید رمزنگاری مستقل باشند؛ داده و کلید backup در دو محل جدا نگه داشته شوند. تغییر مستقیم HMAC سابقه منع دریافت را می‌شکند.

۳. شبکه فقط برای همین برنامه باشد؛ workload نامطمئن به آن متصل نشود. فقط Caddy پورت۸۰/۴۴۳ دارد؛ backend، DB، Redis و RabbitMQ پورت میزبان ندارند. proxy هدر scheme را بازنویسی می‌کند و `config.release_settings` فقط پشت همین مرز خصوصی مجاز است. انتشار مستقیم backend اعتماد به هدر را ناامن می‌کند. access log فعال نیست؛ لاگ runtime نیز فیلد request و response headers را حذف می‌کند تا query پرداخت و هدر خصوصی وارد log نشوند. پنل مدیریت برای افراد مشخص، پشت کنترل دسترسی شبکه/VPN و MFA سازمانی قرار بگیرد؛ MFA در خود این برنامه پیاده نشده است.

۴. تنظیم انتشار پیش‌فرض providerها را خاموش و دیتابیس تازه را halted نگه می‌دارد. فعال‌سازی خارجی به `provider.env.example`، allowlist HMAC شماره‌های داوطلب، قرارداد/بازپرداخت/حریم خصوصی مصوب، سقف ریالی مثبت، نسخه شرایط بازبینی‌شده و مسئول پشتیبانی نیاز دارد. ابتدا فقط سه موضوع مثبت و ساعت۹تا۲۱ تهران. مجوز عمومی ارسال از مجوز توسعه استنتاج نمی‌شود.

پس از مجوز مستقل استقرار، اپراتور می‌تواند این فرمان‌ها را در محیط مصوب اجرا کند؛ در این تحویل اجرا نشده‌اند:

```sh
docker compose --env-file .env.release -f compose.release.yaml config --quiet
docker compose --env-file .env.release -f compose.release.yaml up --no-build -d
docker compose --env-file .env.release -f compose.release.yaml exec backend python manage.py bootstrap_roles
docker compose --env-file .env.release -f compose.release.yaml exec backend python manage.py check --deploy --fail-level WARNING
docker compose --env-file .env.release -f compose.release.yaml exec backend python manage.py release_readiness --human-checks /path/to/reviewed-checks.json --require-live-ready
```

مسیر پرونده بررسی باید داخل کانتینر با mount فقط‌خواندنی در دسترس باشد؛ شاهد خصوصی را در image عمومی کپی نکنید. readiness نامعتبر با exit غیرصفر رد می‌شود. حتی خروجی موفق این دستور، مجوز انتشار یا ازسرگیری ارسال نیست. بازبینی readiness در حالت halt انجام می‌شود؛ سپس اپراتور دارای مجوز با دلیل در admin resume می‌کند.

## پایش و توقف

`ops_snapshot` سن صف، پرداخت/ارسال نامعلوم، refund و گزارش باز و مصرف بودجه را جمعی نشان می‌دهد. سن بیش از۱۲۰ثانیه هشدار دارد؛ رزرو ناخالص۸۰٪ هشدار و رسیدن به سقف مانع هزینه تازه است. هزینه مشاهده‌شده بالاتر از رزرو، ارسال را متوقف می‌کند. خرابی Redis، halt یا خارج‌بودن از ساعت، صف را حفظ و ارسال را عقب می‌اندازد. زمان۲۴ساعتهٔ پیام حل‌نشده یا ارسال‌نشده به مسیر refund و رسیدگی می‌رود؛ وضعیت تحویل نامعلوم اجازه ارسال دوباره نیست.

در تکرار برداشت/ارسال، افشای داده، شکست توقف دریافت یا عبور هزینه، ابتدا halt با audit؛ سپس بررسی مالی و unknownها ادامه پیدا کند. خاموش‌کردن worker/beat بدون حفظ تطبیق، راه‌حل مالی نیست. شناسه درخواست و کد خطا را ثبت کنید؛ متن، شماره، OTP، capability و کلید را در ticket/log قرار ندهید. refund دستی فقط با مرجع مستند و مجوز مالی ثبت شود؛ پاسخ موفق reverse یا DLR، تأیید خوانده‌شدن پیام نیست.

## انتشار تدریجی و rollback

قبل هر تغییر، digestهای سالم قبلی، migration tip و پشتیبان رمز‌شده را ثبت کنید. schema فعلی افزایشی است. بعد migration رمزکردن snapshotها، backend قدیمی‌تر از۰٫۵ قابل استفاده نیست. رجوع به۰٫۵/۰٫۶ نیز فقط بعد تطبیق schema/API و flags مجاز است؛ در مهاجرت رضایت، rollback به کدی که ثبت رضایت خارجی ندارد برای ترافیک واقعی مجاز نیست. حد بازگشت عملیاتی این نامزد، کد بازبینی‌شده سازگار با رضایت نسخه۰٫۶ یا جدیدتر است.

۱. ارسال را halt کنید؛ پرداخت و ارسال حل‌نشده را query کنید. مهاجرت destructive/down را کور اجرا نکنید.

۲. candidate را بدون جابه‌جایی داده یا تغییر secret بالا آورید، health و bootstrap و مسیر غیرمالی را بررسی کنید. `RELEASE-CONFIG.json` فقط lint تنظیمات است؛ DNS/TLS عمومی آزموده نشده است.

۳. هنگام شکست candidate، همان digest سالم frontend/backend را برگردانید؛ DB را دست‌نخورده نگه دارید. در صورت ناسازگاری schema، سرویس halt بماند و طرح اصلاح افزایشی یا restore جدا اجرا شود. عملیات مالی و suppression جدید حذف نشوند.

۴. JS/CSS نسخه قبلی را تا پایان عمر صفحات باز در origin دارایی‌ها نگه دارید؛ SW فقط چهار فایل عمومی را cache می‌کند و از دسترس‌رفتن chunkهای قدیمی را جبران نمی‌کند. استقرار تک‌کانتینری بدون نگهداری asset قدیم، ادعای upgrade بی‌وقفه ندارد. آزمون سازگاری chunk قدیم و درگاه/standalone روی دستگاه واقعی هنوز باز است؛ تا حل آن، انتشار عمومی متوقف می‌ماند.

تمرین محلی این تحویل، خرابی candidate فرانت با exit23 و بازگرداندن همان image سالم را در پروژه جدا اثبات کرد: health/صفحه اصلی برگشت و watermark مالی ثابت ماند. [نتیجه](ROLLBACK.json). این شاهد rollback چندنسخه‌ای asset یا rollout عمومی نیست.

## پشتیبان و restore

از `scripts/backup-restore.py` با backend venv و کلید0600 استفاده کنید؛ راهنمای کامل در [نسخه۰٫۵](../release-v0.5/README.fa.md) است. ابزار فقط DB تازه `begamnagam_restore_*` می‌سازد، overwrite منبع ندارد، آخرین suppression/حذف/بودجه منبع موجود را overlay می‌کند، intent خارجی را query-only و ارسال را halted می‌گذارد. drift مالی پس از snapshot، readiness را رد می‌کند. این ابزار به منبع جاری برای آخرین overlay نیاز دارد؛ بازیابی پس از ازدست‌رفتن منبع اصلی به راهکار خارج دستگاه/WAL و تطبیق عملیاتی نیاز دارد و در این تحویل آزموده نشده است.

بازپخش ارسال پس از restore ممنوع است. اول رمزگشایی، مالی، منع دریافت، درخواست حذف و تلاش‌های خارجی را تطبیق کنید. بازگردانی نهایی تنها با مسئول مشخص و audit. [تمرین۰٫۷](RESTORE.json) توقف مصنوعی ثبت‌شده پس از snapshot را حفظ کرد؛ حذف حساب پس از snapshot در این تمرین مستقیم اجرا نشد. زمان حدود۴٫۴ثانیه روی این لپ‌تاپ، SLA/RTO عملیاتی نیست.

## بازاجرای آزمون محلی

`python3 scripts/verify-release-config.py` فقط topology را با مقادیر مصنوعی بررسی می‌کند و کانتینر بالا نمی‌آورد. `scripts/local-benchmark.py --help` پروفایل داده مصنوعی را توضیح می‌دهد؛ DSNهای loopback از env و Redis14 جدا لازم‌اند، دیتابیس تازه و صف/hostname مستقل ساخته می‌شوند. `scripts/synthetic-pilot.py --help` از Redis13 جدا و HTTP fixture محلی استفاده می‌کند. این ابزارها را روی DB واقعی یا cache مشترک اجرا نکنید.

`rehearse-local-rollback.py` عمداً فقط پروژهٔ آزمایشی `begamnagam-g6` و پورت۳۰۸۰ را می‌پذیرد. به override محلی imageها در `.local/phase-two-clean.yaml` نیاز دارد. این فایل محیط آزمون است و خروجی Git نیست؛ برای تکرار، هر پنج سرویس app را به imageهای ساخته‌شدهٔ `begamnagam-{backend,migrate,worker,beat,frontend}:latest` یا digest همان build نگاشت کنید. نمونه development روی پورت۳۰۰۰ در این تمرین متوقف نمی‌شود.
