# استقرار CT داخلی

پروفایل مستقل `compose.internal.yaml` از نسخهٔ زیرساخت۰٫۸٫۱۱ با Traefik اجرا می‌شود. SSL عمومی روی Nginx مرکزی۱۹۲٫۱۶۸٫۱٫۶ می‌ماند؛ Nginx درخواست دامنه را با HTTP به پورت۸۰ CT۱۹۲٫۱۶۸٫۱٫۱۲۳ می‌فرستد. دسترسی مستقیم IP همچنان HTTPS با CA خصوصی دارد. پرداخت و پیام گیرنده آزمایشی‌اند؛ این استقرار مجوز فعال‌سازی عمومی providerها نیست.

## تنظیمات

فایل خصوصی `.env.internal` با دسترسی0600 از `deploy/internal.env.example` ساخته می‌شود. برای مسیر دامنه، مقادیر غیرمحرمانهٔ `deploy/domain.env.example` را به آن اضافه کنید؛ فایل موجود و اسرار را بازنویسی نکنید. `PUBLIC_DEMO_HOST=begamnagam.ir`، `CENTRAL_NGINX_IP=192.168.1.6` و `TRUST_DOMAIN_PROXY=1` همراه `APP_BASE_URL=https://begamnagam.ir` لازم‌اند. IP داخلی و دامنه باید صریحاً در ALLOWED_HOSTS و مبدأهای HTTPS در CSRF_TRUSTED_ORIGINS باشند.

image بک‌اند این انتشار `begamnagam-internal/backend:0.8.11-traefik` است. image فرانت۰٫۸٫۱۰ حفظ شده و دوباره ساخته نمی‌شود. تغییر env زمان اجرا، metadata داخل image فرانت را عوض نمی‌کند. OTP واقعی فقط با اعتبارنامه، همان فهرست مجاز قبلی و سقف هزینه حفظ می‌شود؛ این تغییر هیچ شماره یا مسیر provider دیگری را مجاز نمی‌کند. محدودیت روزانه، ابزار تست ادمین و هدیه۳ارسال حفظ می‌شوند.

CT به‌علت محدودیت runc در LXC از host networking استفاده می‌کند. داده، API و metrics فقط روی127.0.0.1 گوش می‌دهند؛ Traefik فقط روی IP CT پورت۸۰/۴۴۳ و health روی127.0.0.1:8082 دارد. dashboard، Docker socket، ACME عمومی و access log خاموش‌اند. این CT به برنامه اختصاص دارد؛ کانتینر privileged یا runtime قدیمی لازم نیست.

پیکربندی پایدار Traefik در `deploy/traefik/routes.yml` به‌صورت directory و فقط خواندنی mount می‌شود. مسیرهای `/api/*`، `/admin`، `/admin/*`، `/static/admin/*` و `/healthz` به بک‌اند۸۰۰۰ و سایر مسیرها به فرانت۳۰۰۰ می‌روند. rule دامنه فقط peer شبکهٔ Nginx، خود CT و loopback را می‌پذیرد؛ XFF جعلی مجوز نمی‌دهد. Host و هدرهای scheme بازنویسی و IP کاربر از انتهای زنجیرهٔ پراکسی‌های مشخص استخراج می‌شود.

```sh
cd /opt/begamnagam/current
docker compose --env-file .env.internal -f compose.internal.yaml config --quiet
docker compose --env-file .env.internal -f compose.internal.yaml ps
python3 scripts/verify-domain-routing.py --connect-ip 192.168.1.6
```

در به‌روزرسانی همین استقرار، پس از انتقال image و بررسی candidate، فقط سرویس‌های تغییرکرده را با `up -d --no-deps` جایگزین کنید. داده و فرانت این انتشار نیازی به recreate ندارند. استقرار اولیه روی CT تازه، migration و تنظیم مستقل CA می‌خواهد؛ ابزار تمدید زیر مخصوص CA موجود همین مهاجرت است.

## گواهی داخلی و تمدید

ریشهٔ Caddy قبلی در volume به نام `begamnagam-internal_caddy-data` حفظ می‌شود. این volume حذف نمی‌شود و به Traefik mount نیست. `scripts/renew-internal-tls.py --in-docker` با image قفل‌شدهٔ بک‌اند، گواهی۳۰روزهٔ IP با همین ریشه می‌سازد؛ اعتبار بیش از۱۴روز، تطابق کلید، امضای ریشه و SAN را پیش از صرف‌نظر از تمدید بررسی می‌کند. کلید CA داخل CT می‌ماند و تنها هنگام امضا به ابزار یک‌بارمصرف، فقط خواندنی، داده می‌شود. ابزار socket باز نمی‌کند؛ host networking به‌خاطر محدودیت LXC است.

Traefik فقط `INTERNAL_TLS_DIR=/opt/begamnagam/shared/traefik-tls` شامل leaf و کلیدش را می‌بیند. ابزار پس از نوشتن فایل‌ها، reload پیکربندی را تحریک می‌کند. timer روزانه است؛ هر بار گواهی تازه صادر نمی‌کند. نصب پس از موفقیت استقرار:

```sh
python3 scripts/renew-internal-tls.py --in-docker
install -m 644 deploy/systemd/begamnagam-internal-tls.service /etc/systemd/system/
install -m 644 deploy/systemd/begamnagam-internal-tls.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now begamnagam-internal-tls.timer
systemctl start begamnagam-internal-tls.service
journalctl -u begamnagam-internal-tls.service --no-pager
```

فقط گواهی عمومی root.crt برای دستگاه تست قابل انتقال است؛ کلید root.key را جابه‌جا نکنید. بررسی TLS مستقیم با `curl --cacert root.crt https://192.168.1.123/healthz` انجام می‌شود. اعتماد CA روی گوشی اقدام جداگانهٔ صاحب دستگاه است؛ هشدار مرورگر یا TLS verification دور زده نمی‌شود. پذیرش نصب PWA روی گوشی واقعی همچنان انسانی است.

## بررسی و بازگشت

`deploy/check-internal-demo.py` در بک‌اند، با override فقط در فرایند تشخیصی، OTP مصنوعی، هدیه، سفارش بدون تکرار، RabbitMQ/Celery، سابقه و قطع دریافت را بررسی می‌کند؛ تنظیم سرویس و ارسال واقعی را تغییر نمی‌دهد:

```sh
docker compose --env-file .env.internal -f compose.internal.yaml exec -T backend python < deploy/check-internal-demo.py
```

env و رمز مدیریت خارج Git، در shared خصوصی می‌مانند. لاگ‌ها محدود و بدون query/هدر خصوصی‌اند. برای rollback نسخهٔ قبلی و env و imageهایش را نگه دارید؛ volume حذف یا migration را کورکورانه عقب نبرید. روش دقیق بازگشت این انتشار در [گزارش دامنه](domain-routing.fa.md) است.
