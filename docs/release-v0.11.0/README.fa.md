# انتشار امنیتی۰٫۱۱٫۰ — ۲۰۲۶-۱۰-۲۷

به درخواست صریح کارفرما، نسخه روی CT فعال شد. مسیر جاری `/opt/begamnagam/releases/0.11.0` و image فرانت/بک‌اند هر دو۰٫۱۱٫۰ هستند. [شواهد اجرا و digestها](../deployments/ct115-0.11.0-security.json) و [بررسی اولیه](../security-audit-2026-10-27.fa.md) وضعیت قبل و بعد را مستند می‌کنند.

## تغییرات اعمال‌شده

- PostgreSQL هیچ قاعدهٔ `trust` ندارد. TCP فقط برای دو نقش همین دیتابیس از loopback با SCRAM مجاز است؛ مدیریت از Unix socket و peer/mapping انجام می‌شود. برنامه با نقش بدون superuser، ساخت DB/role، replication، bypass RLS یا مالکیت جدول/schema کار می‌کند. مالک مهاجرت جداست و default privileges نیز تنظیم شد.
- env برنامه، migration و مدیریت سرویس‌ها جدا شدند؛ رمز مدیریتی DB و broker در backend/worker/beat نیست.
- Redis دارای رمز و ACL فرمان/کلید برای برنامه، کاربر PING سلامت و مدیر جداست؛ default خاموش و protected mode روشن است. serializer JSON است؛ داده و شمارنده‌ها flush نشدند و محدودکنندهٔ پیش‌فرض کلید قدیمی خود را حفظ می‌کند.
- RabbitMQ حساب بدون tag مدیریتی و vhost مستقل دارد؛ منابع مجاز به `celery` و انتشار لازم محدودند. حساب مدیریتی قبلی حذف و remote control/events سلری خاموش شدند؛ pidbox فعال وجود ندارد.
- migrationهای۰۰۱۶تا۰۰۱۸ اجرا شدند؛ بدنهٔ Order/Preview هم رمز شده است. policy/overrideها خالی ماندند و همان محدودیت‌های قبلی محیط واقعی اعمال می‌شوند؛ تنظیمات نامحدود مخصوص لوکال منتقل نشدند.
- محدودکنندهٔ ورود ادمین، CSRF/مجوزهای مدیریت، خطای عمومی و۴۱۳، CSP با nonce، HSTS و جلوگیری از cache/index پاسخ خصوصی فعال‌اند. سئو و JSON-LD نیز در image فرانت هستند. `cryptography` به50.0.2 با wheel رسمی Linux و SHA256 تأییدشده ارتقا یافت.
- SSH فقط کلید می‌پذیرد؛ password/keyboard-interactive و forwardingهای غیرضروری بسته‌اند. root با کلید موجود حفظ شد. اتصال مستقل جدید پیش از حذف timer بازگشت تأیید شد.
- firewall ماندگار CT پیش‌فرض input را drop می‌کند؛ loopback/پاسخ اتصال، SSH/TLS از LAN و HTTP از Nginx مرکزی مجازند. قواعد Docker flush نشدند. proxy و job تمدید گواهی اکنون مسیر release یکسانی را می‌بینند؛ HTTPS خصوصی با CA معتبر و HTTPS دامنه۲۰۰ دادند.

OTP و پیامک واقعی، سه هدیه، هزینهٔ روزانهٔ مجاز، کنترل محتوا، opt-out و پرداخت بسته حفظ شدند. ماندهٔ حساب‌ها و ledger مقایسه شدند. برای تست هیچ OTP/پیامک واقعی ارسال نشد؛ task بی‌اثر `celery.accumulate` عبور از صف را بررسی کرد.

## بکاپ و عملیات بعدی

بکاپ رمز‌شده و restore قبل از تغییر بررسی شد؛ snapshot نهایی با توقف همهٔ نویسنده‌های قدیمی گرفته شد. restore پس از انتشار، شامل۱۳۶فیلد رمز‌شده، موفق بود. هیچ restore روی DB اصلی یا حذف رکورد محصول انجام نشد.

ابزار `scripts/backup-hardened.py` روی میزبان CT از کانتینرهای موجود استفاده می‌کند؛ کلید مستقل0600 خارج release است. بکاپ روزانه۰۳:۱۵ و rehearsal یکشنبه‌ها۰۴:۱۵ به وقت تهران، هرکدام با حداکثر۵دقیقه تأخیر تصادفی، فعال‌اند. هر دو unit یک‌بار موفق اجرا شدند. archive رمز‌شده و کلید جداگانه به دستگاه اپراتور هم کپی شدند. replication خودکار خارج میزبان و سیاست نگهداری هنوز تنظیم نشده‌اند؛ بکاپ قبلی حذف نشد.

این ابزار فقط backup و rehearsal موقت دارد؛ فرمان بازیابی production نیست. در بحران، نویسنده‌ها/worker/beat را متوقف، به DB تازه restore و آن DB را halted نگه دارید. آخرین suppression، درخواست حذف و رویدادهای مالی پس از snapshot باید تطبیق داده شوند؛ unknown/submitting و سفارش لغوشده مجوز ارسال دوباره نیستند. [runbook بازیابی](../release-v0.7/RUNBOOK.fa.md) همچنان لازم است. archive جدید Fernet روی dump سفارشی PostgreSQL است و با قالب `BNBACKUP1` ابزار قدیمی متفاوت است.

تمام فرمان‌های این release، از جمله `up`/recreate بعدی، باید overlay امنیتی را داشته باشند:

```sh
cd /opt/begamnagam/current
docker compose --env-file .env.internal \
  -f compose.internal.yaml -f compose.hardened.yaml ps
docker compose --env-file .env.internal \
  -f compose.internal.yaml -f compose.hardened.yaml \
  exec -T backend python manage.py audit_security --database --redis
systemctl status begamnagam-firewall.service
systemctl list-timers 'begamnagam-*'
```

env migration را به برنامه/فرانت ندهید. برای image قدیمی، ابتدا مهاجرت رمزنگاری باید با کلید صحیح و توقف نویسنده‌ها reverse شود؛ تعویض image کافی نیست. حساب قدیمی broker بازنشسته شده، پس env قدیمی به‌تنهایی اتصال معتبر ندارد. بازگشت بعد از فعال‌شدن نسخه، عملیاتی مستقل با تطبیق داده است.

## اعتبارسنجی و موارد باز

۲۹۹تست بک‌اند با PostgreSQL/Redis ایزوله،۳۸تست فرانت، TypeScript/build و سازگاری migration موفق‌اند. candidate روی CT،۱۹کنترل امنیتی و۴۰بررسی SEO را گذراند؛ مسیر HTTPS دامنه۲۲کنترل امنیت تمام stack و۴۰بررسی SEO را گذراند. یک timeout شبکه در تلاش اول، با اجرای کامل موفق بعدی بررسی شد. اعتبارسنجی معمول TLS حفظ شد و دامنه از IP داخلی edge آزموده شد؛ این اسکن مستقل اینترنت نیست.

DB/Redis بدون رمز رد شدند، مجوز Redis با `ACL DRYRUN` بدون اجرای فرمان مخرب بررسی شد، صف بدون SMS کار کرد و هر۸کانتینر سالم و بدون OOM هستند. volumeها حفظ شدند.

پیکربندی جاری Nginx مرکزی، اعتماد forwarded headers و حذف URI خصوصی از log آن لایه در این نشست مجدداً قابل بازرسی نبودند. edge تا CT همچنان HTTP در LAN است و فقط همان edge مجاز است؛ TLS تأییدشدهٔ بین دو میزبان و MFA وب نیازمند تنظیم/ثبت عامل اپراتورند. حساب اپراتور جدا از root، اسکن کامل CVE سیستم‌عامل/imageها و بررسی NAT از اینترنت نیز در این انتشار انجام نشدند.
