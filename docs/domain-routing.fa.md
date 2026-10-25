# گزارش اصلاح دامنه و جایگزینی Traefik — نسخهٔ زیرساخت۰٫۸٫۱۱

## نتیجه و مرز تأیید

Traefik۳٫۷٫۱۳ روی CT115 جای Caddy را گرفته است. مسیر فعال `/opt/begamnagam/current` به `/opt/begamnagam/releases/0.8.11-traefik` اشاره می‌کند. دامنه از طریق Nginx داخلی، با حفظ نام دامنه، SNI و اعتبارسنجی TLS، برنامهٔ واقعی و فایل‌های آن را برمی‌گرداند. IP داخلی هم HTTPS معتبر با CA قبلی دارد. هشت کانتینر فعال‌اند؛ سرویس‌های دارای health check سالم‌اند. فرانت، PostgreSQL، Redis و RabbitMQ همان شناسهٔ کانتینر پیش از تغییر را دارند.

دسترسی عادی `https://begamnagam.ir` از شبکهٔ این دستگاه و مرورگر با Connection refused متوقف شد؛ DNS در این بررسی۳۷٫۱۱۴٫۲۵۳٫۱۸ بود. بنابراین موفقیت مسیر اینترنت عمومی یا رندر کامل مرورگر ادعا نمی‌شود. دسترسی مستقیم به Nginx۱۹۲٫۱۶۸٫۱٫۶ با همان URL دامنه موفق است. NAT loopback، port forwarding یا firewall علت‌های احتمالی این مانع شبکه‌اند؛ علت دقیق بدون بررسی لبهٔ شبکه ثابت نشده است.

[شواهد ساختاریافته](deployments/ct115-0.8.11-traefik.json) نتیجهٔ درخواست‌ها، وضعیت کانتینرها و محدودیت‌ها را ثبت می‌کند. این انتشار بک‌اند و زیرساخت است؛ image فرانت۰٫۸٫۱۰ حفظ شده و تغییرهای جداگانهٔ SEO دوباره build یا deploy نشده‌اند. commit و push دیگری با عنوان `adds` هنگام کار در checkout مشترک ظاهر شد؛ تاریخچهٔ آن دست‌کاری نشده و این کار هیچ push اجرا نکرده است.

## علت اثبات‌شدهٔ صفحهٔ سفید

پیکربندی فعال Caddy قبلی در release۰٫۸٫۱۰ فقط سایت IP داخلی را داشت. درخواست HTTP با `Host: begamnagam.ir` به آن site نمی‌خورد و پاسخ۲۰۰ با صفر بایت می‌گرفت؛ همان پاسخ از Nginx عبور می‌کرد. درخواست مستقیم CT با این Host هم صفر بایت بود، بنابراین NAT loopback علت آن پاسخ خالی نبود. نبود route دامنه در پیکربندی و mount واقعی کانتینر بررسی شد؛ نتیجه صرفاً از فرض اولیه گرفته نشده است.

در ابتدا candidate دامنه برای Caddy آماده شد؛ با دستور بعدی کارفرما، نسخهٔ نهایی به Traefik تغییر کرد. candidate قبلی برای بازگشت نگه داشته شد و پروکسی فعال دیگر Caddy نیست.

## معماری نهایی

```text
HTTPS begamnagam.ir:443
  → Nginx مرکزی 192.168.1.6، همان گواهی عمومی
  → HTTP 192.168.1.123:80، Host دامنه
  → Traefik
      /api/*، /admin، /admin/*، /static/admin/*، /healthz → 127.0.0.1:8000
      سایر مسیرها → 127.0.0.1:3000

HTTPS 192.168.1.123:443 → Traefik با گواهی CA داخلی قبلی
```

Nginx مرکزی و دامنه‌های دیگر تغییر نکردند. Traefik گواهی عمومی ACME نمی‌گیرد و HTTP دامنه را دوباره به HTTPS redirect نمی‌کند؛ redirect عمومی روی Nginx است. HTTP مستقیم IP به HTTPS می‌رود. این برنامه برای مسیر فعلی WebSocket کاربردی ندارد؛ Fast Refresh توسعه خارج این استقرار است.

## فایل‌ها و تنظیمات

بررسی شامل README و AGENTS، Composeهای توسعه/انتشار/داخلی، Caddyfile و mount فعال، شبکه و listenerهای Docker، env خصوصی بدون چاپ اسرار، تنظیمات Django، provider OTP، middleware، پیکربندی Next.js، کوکی‌ها، health check، فایل‌های PWA، لاگ‌های محدود، اسکریپت تشخیصی داخلی و گردش‌کار CI/CD بود.

تغییرهای مرتبط:

- `compose.internal.yaml` و `deploy/traefik/routes.yml`: پروکسی Traefik، ruleهای صریح، upstreamهای موجود، محدودیت peer، TLS داخلی و health محلی.
- `deploy/domain.env.example` و بخش مرتبط `deploy/internal.env.example`: دامنه، IP دقیق Nginx، trust صریح، originهای HTTPS و مسیر leaf TLS؛ بدون اعتبارنامه.
- `backend/config/internal_settings.py`، `settings.py` و `origins.py`: دامنهٔ صریح و fail-closed، secure cookie/redirect، اعتبارسنجی host و CSRF، حفظ همهٔ شروط OTP محدود.
- `backend/core/middleware.py` و `providers/http.py`: استخراج IP از زنجیرهٔ مورد اعتماد و حفظ استثنای محدود OTP؛ مسیرهای دیگر provider باز نمی‌شوند.
- `backend/core/test_domain_routing.py`: سناریوهای منفی origin، host، proxy spoof و فعال‌سازی ناقص.
- `scripts/renew-internal-tls.py` و `deploy/systemd/*`: صدور و تمدید leaf با CA قبلی؛ timer روزانه فعال.
- `scripts/verify-domain-routing.py`: بررسی HTTPS با امکان اتصال مستقیم به edge، بدون خاموش‌کردن اعتبارسنجی گواهی و بدون پیامک/پرداخت.
- همین گزارش، راهنمای استقرار داخلی، README، CHANGELOG و شواهد انتشار.

env خصوصی جدید در `/opt/begamnagam/shared/.env.traefik` است؛ `.env.internal` release به آن symlink دارد. اسرار، کلید تطبیق شماره، فهرست مجاز و بودجهٔ قبلی حفظ شدند. `PUBLIC_DEMO_HOST=begamnagam.ir`، `CENTRAL_NGINX_IP=192.168.1.6`، `TRUST_DOMAIN_PROXY=1` و APP_BASE_URL با HTTPS تنظیم شده‌اند. دامنه و IP دقیق در ALLOWED_HOSTS و CSRF_TRUSTED_ORIGINS هستند؛ wildcard اضافه نشده است.

پروفایل تاریخی `compose.release.yaml` و فایل‌های قدیمی Caddy برای این CT استفاده نمی‌شوند؛ پروفایل جاری CT فقط `compose.internal.yaml` است. نسخهٔ قدیمی و volume ریشهٔ CA برای rollback نگه داشته شده‌اند.

## مرز اعتماد و TLS

Traefik درخواست HTTP دامنه را فقط از peer شبکهٔ Nginx، خود CT یا loopback می‌پذیرد. درخواست مستقیم دستگاه دیگر با XFF جعلی هم۴۰۳ شد. این محدودیت در application proxy است؛ ACL شبکه برای محدودکردن پورت۸۰ به Nginx، دفاع اضافی مفیدی است.

Host دامنه و X-Forwarded-Proto=https و X-Forwarded-Host بازنویسی می‌شوند؛ Forwarded و هدر قدیمی X-Verified-Client-IP حذف می‌شوند. trustedIPs فقط Nginx است و حالت insecure فعال نشده است. Django زنجیرهٔ IP را از راست با حذف فقط hopهای مشخص بررسی می‌کند؛ header نامعتبر یا peer نامجاز پذیرفته نمی‌شود. alias headerهای دارای نقطه/underscore پیش از ورود به WSGI حذف می‌شوند؛ مسیرهای دارای reserved character کدشده رد می‌شوند.

SESSION_COOKIE_SECURE و CSRF_COOKIE_SECURE فعال، کوکی‌ها host-only و SameSite=Lax، و session دارای HttpOnly است. CSRF و اعتبارسنجی TLS در همهٔ بررسی‌ها روشن بودند. CORS باز نشده است. API، دیتابیس، صف و metrics روی loopback مانده‌اند. dashboard و Docker socket در Traefik فعال نیستند؛ access log خصوصی ذخیره نمی‌شود.

کلید خصوصی root CA قدیمی از CT خارج نشده و به Traefik داده نشده است. فقط leaf و کلید آن در shared/traefik-tls قرار دارند. leaf۳۰روزه دارای SAN برای IP، AKI/SKI و serverAuth است؛ ابزار تمدید امضای CA، کلید و تاریخ را بررسی می‌کند. بررسی سخت‌گیرانهٔ Python و openssl verify موفق است. timer روزانه بررسی و زیر۱۴روز تمدید می‌کند؛ اجرای دوم در زمان استقرار به‌درستی بدون صدور دوباره تمام شد. محدودیت LXC باعث استفاده از host networking برای ابزار امضا شد؛ ابزار socket باز نمی‌کند و capability اضافه یا کانتینر privileged ندارد.

پرداخت و پیام گیرنده همچنان demo، شبکهٔ عمومی providerها disabled و OTP واقعی فقط برای فهرست و سقف قبلی است. بررسی‌ها هیچ OTP واقعی یا برداشت وجه ایجاد نکردند. داده‌ها و اسرار وارد Git نشده‌اند.

## آزمون‌ها و نتیجهٔ واقعی

| بررسی | نتیجه |
| --- | --- |
| مجموعهٔ کامل بک‌اند روی PostgreSQL | ۱۳۴ تست موفق؛ بدون تغییر مدل یا migration |
| Compose نهایی روی CT | معتبر |
| Traefik موقت روی۱۸۰۸۰/۱۸۴۴۳ | ۹ بررسی موفق؛ کانتینر موقت حذف شد |
| Test A/F: HTTPS مستقیم IP | HTML واقعی۱۷۶۱۷بایت؛ همهٔ assetها و مسیرها موفق |
| Test B: HTTP با Host دامنه از خود CT | ۲۰۰، HTML واقعی۱۷۶۱۷بایت |
| Test C: دامنه با اتصال به Nginx داخلی و TLS معتبر | ۲۰۰، HTML واقعی۱۷۶۱۷بایت |
| فایل‌های JS/CSS اصلی | هر۹ فایل۲۰۰؛ URLها هم‌مبدأ HTTPS |
| Refresh مسیرهای history/preferences/help | هر سه HTML واقعی۲۰۰ |
| Test D: bootstrap/health/admin/static | وضعیت‌های واقعی درست؛ admin→۳۰۱، ورود لازم→۳۰۲، static→۲۰۰ |
| API خصوصی بدون نشست، endpoint ناموجود | ۴۰۱ و۴۰۴، مطابق قرارداد |
| CSRF مفقود/مبدأ جعلی، ورودی نامعتبر با CSRF صحیح | ۴۰۳/۴۰۳ و۴۰۰ |
| ورود واقعی پنل ادمین و صفحهٔ ابزار تست | موفق با کوکی امن؛ بدون اجرای reset |
| نشست محصول ساخته‌شده با OTP مصنوعی در فرایند تشخیصی | bootstrap احرازشده و history از هر دو مسیر HTTPS موفق |
| گردش‌کار مصنوعی روی CT | OTP/CSRF، سه هدیه، idempotency، worker، history، opt-out و مالکیت موفق |
| manifest، sw.js و offline.html | ۲۰۰؛ display=standalone و Service-Worker-Allowed=/ |
| گواهی IP و تمدید بدون تغییر trust | تأیید سخت‌گیرانه موفق؛ timer فعال |
| peer نامجاز با XFF جعلی / مسیر encoded slash | ۴۰۳ /۴۰۰ |
| سلامت و حفظ داده | هر۸ کانتینر فعال؛ شناسهٔ داده و فرانت بدون تغییر |
| Test E: مرورگر با DNS عمومی | ERR_CONNECTION_REFUSED؛ رندر و console مرورگر تأیید نشده |

برای تست شبکه، URL واقعی HTTPS و hostname verification حفظ شدند؛ فقط resolver اتصال به IP داخلی Nginx را انتخاب کرد. نتیجهٔ HTTP client جای رندر مرورگر، نصب PWA یا تست روی گوشی واقعی نیست. تست جدید فرانت یا build آن انجام نشد، چون سورس/رابط فرانت در این انتشار تغییر نکرده است.

## پشتیبان و بازگشت

پشتیبان اولیه در `/opt/begamnagam/backups/domain-routing-20261025T172035Z` شامل release، env خصوصی و وضعیت پیش از تغییر است. پیش از Traefik نیز پشتیبان جدا از candidate Caddy و env دامنه گرفته شد؛ مسیر دقیق در شواهد JSON آمده است. volumeها حذف نشده‌اند. نسخهٔ baseline۰٫۸٫۱۰ و imageهایش حفظ‌اند.

برای بازگشت کامل به baseline داخلی، با root روی CT:

```sh
systemctl disable --now begamnagam-internal-tls.timer
ln -s /opt/begamnagam/releases/0.8.10 /opt/begamnagam/rollback.next
mv -Tf /opt/begamnagam/rollback.next /opt/begamnagam/current
cd /opt/begamnagam/current
docker compose --env-file .env.internal -f compose.internal.yaml config --quiet
docker compose --env-file .env.internal -f compose.internal.yaml up -d --no-deps --force-recreate backend worker beat proxy
```

این دستور باید از release قدیمی با Compose و env قدیمی اجرا شود؛ داده و فرانت را recreate نمی‌کند. baseline قبلی فقط IP را پشتیبانی می‌کند و مشکل دامنه در آن برمی‌گردد. برای بازگشت محدود به candidate دامنهٔ Caddy، دایرکتوری `0.8.11-domain` و override `compose.domain.yaml` محفوظ است؛ آن candidate پذیرش کامل این انتشار را ندارد. هیچ downgrade دیتابیس لازم نیست.

## کارهای باقی‌مانده

۱. مسیر DNS/IP عمومی، NAT و firewall لبه بررسی شود؛ تا اتصال عادی دامنه برقرار نشود، Test E و دسترسی واقعی اینترنت باز می‌مانند. نتیجهٔ مستقیم Nginx، مشکل قبلی پاسخ خالی برنامه را رفع‌شده نشان می‌دهد، اما سلامت مسیر عمومی را ثابت نمی‌کند.

۲. گواهی فعلی Nginx نام `www.begamnagam.ir` را پوشش نمی‌دهد؛ بررسی TLS با hostname mismatch رد شد. این انتشار فقط apex درخواستی را route می‌کند و Nginx/دامنه‌های دیگر را تغییر نداده است.

۳. پذیرش انسانی نصب PWA، آفلاین و گوشی واقعی محفوظ است؛ گواهی CA داخلی باید با اقدام صاحب دستگاه اعتماد شود. هیچ هشدار امنیتی مرورگر دور زده نشده است.

Context7 در این محیط ابزار قابل‌فراخوانی نداشت؛ مستندات رسمی [Traefik entrypoints](https://doc.traefik.io/traefik/reference/install-configuration/entrypoints/)، [IPAllowList](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ipallowlist/)، [File provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/)، [Docker run](https://docs.docker.com/reference/cli/docker/container/run/) و [تنظیمات Django](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header) مرجع پیکربندی بودند.
