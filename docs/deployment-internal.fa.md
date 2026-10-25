# استقرار CT داخلی

این پروفایل مستقل در `compose.internal.yaml` برای شبکهٔ خصوصی است. پرداخت و پیام به گیرنده شبیه‌سازی می‌شوند؛ انتشار عمومی نیست. فقط Caddy پورت‌های۸۰/۴۴۳ روی IP مشخص‌شده را باز می‌کند. دیتابیس، کش، صف، metrics و API فقط روی loopback خود CT گوش می‌دهند. اجرای برنامه‌ها با کاربر غیرroot داخل image است؛ root فقط برای مدیریت CT و Docker استفاده می‌شود.

## فایل‌ها و تنظیم

`deploy/internal.env.example` را با کلیدهای مستقل و دسترسی0600 به `.env.internal` تبدیل کنید. برای این CT، `INTERNAL_DEMO_HOST=192.168.1.123` و `APP_BASE_URL=https://192.168.1.123` است. کلید HMAC باید با فهرست هش‌های OTP همان محیط سازگار باشد. اطلاعات کاربران و دیتابیس توسعه به این CT کپی نمی‌شود؛ پایگاه تازه migration می‌گیرد.

OTP واقعی فقط در صورت حفظ تنظیم صریح قبلی، اعتبارنامه، هش شمارهٔ مجاز و سقف‌های مثبت فعال می‌شود. استثنای داخلی فقط برای همان IP خصوصیِ صریح روی HTTPS است؛ دامنه یا IP عمومی، HTTP و شماره‌های خارج فهرست مجاز نمی‌شوند. ارسال واقعی سفارش و پرداخت همچنان بسته‌اند. ابزار تست ادمین، حدود روزانه و هدیه۳ارسال حفظ می‌شوند.

imageهای Linux/amd64 را بیرون CT بسازید و به CT منتقل کنید. منابع مشاهده‌شدهٔ CT هنگام آماده‌سازی ابتدا۵۱۲مگابایت و سپس۲گیگابایت RAM بود. worker یک‌تایی، PostgreSQL و Redis کوچک و سقف‌های حافظه برای همین تست داخلی کم‌ترافیک تنظیم شده‌اند. imageهای فعلی و digest آن‌ها را همراه commit منبع ثبت کنید؛ استقرار هیچ push گیتی لازم ندارد.

این LXC با runc جدید، ایجاد namespace شبکهٔ تو‌در‌تو را با خطای `ip_unprivileged_port_start` رد می‌کند. پروفایل CT از شبکهٔ خود CT و bind صریح همهٔ سرویس‌های خصوصی به127.0.0.1 استفاده می‌کند؛ فقط Caddy روی IP داخلی پورت۸۰/۴۴۳ می‌گیرد. هیچ کانتینر privileged یا runtime قدیمی استفاده نمی‌شود. این CT باید به همین برنامه اختصاص داشته باشد و workload نامطمئن کنار آن اجرا نشود. API مدیریت Caddy خاموش است. آدرس‌های bind را پس از استقرار با `ss -lnt` بررسی کنید؛ این فایل برای میزبان مشترک یا انتشار عمومی مناسب نیست.

```sh
docker compose --env-file .env.internal -f compose.internal.yaml config --quiet
docker compose --env-file .env.internal -f compose.internal.yaml up -d --wait --wait-timeout 300
docker compose --env-file .env.internal -f compose.internal.yaml exec backend python manage.py bootstrap_roles
docker compose --env-file .env.internal -f compose.internal.yaml exec -T backend python < deploy/check-internal-demo.py
```

دستور آخر فقط برای دادهٔ مصنوعی است و در همان فرایند تشخیصی، OTP شبیه‌سازی‌شده استفاده می‌کند. تنظیم سرویس یا OTP واقعی را تغییر نمی‌دهد. ارسال صف از RabbitMQ/Celery، ماندهٔ هدیه، سابقه، قطع دریافت و مالکیت را بررسی می‌کند و درخواست پیامک واقعی/پرداخت نمی‌سازد.

## HTTPS و PWA

Caddy برای IP داخلی گواهی با CA خصوصی می‌سازد. گواهی ریشهٔ عمومی در volume پروکسی در `/data/caddy/pki/authorities/local/root.crt` است؛ فقط همین فایل عمومی را برای اعتماد روی دستگاه تست بگیرید و کلید خصوصی CA را جابه‌جا نکنید. مسیر ریشه را با `curl --cacert root.crt https://192.168.1.123/healthz` بررسی کنید؛ TLS verification را خاموش نکنید.

مرورگر گوشی و رایانه باید این CA را اعتماد کنند تا HTTPS معتبر و نصب PWA/Service Worker فعال باشد. اعتماد سیستم/گوشی اقدام جداگانهٔ صاحب دستگاه است و خودکار انجام نمی‌شود. هشدار گواهی را دور نزنید. پذیرش PWA روی گوشی‌های واقعی همچنان در فهرست تست انسانی است. [مستندات HTTPS داخلی Caddy](https://caddyserver.com/docs/automatic-https#local-https) و [secure context](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts) مبنا هستند.

## نگهداری

فایل env و رمز مدیریت برنامه فقط در shared و نسخهٔ خصوصی محلی نگه داشته می‌شوند و Git آن‌ها را نمی‌گیرد. پروکسی access log فعال ندارد؛ query و هدر خصوصی در runtime log فیلتر می‌شوند. لاگ کانتینرها محدود است. volumeهای داده را همراه کلیدهای رمزنگاری backup کنید؛ برای ریست تست، volume یا حساب‌ها را حذف نکنید.

در CT: `docker compose ... ps`، `docker stats --no-stream` و `free -m` را برای سلامت و مصرف ببینید. برای به‌روزرسانی، imageهای نسخهٔ تازه و تنظیم بررسی‌شده را جایگزین و همین پروژه را بالا بیاورید؛ volumeها باقی می‌مانند. پیکربندی و imageهای قبلی را برای rollback نگه دارید و migration را کورکورانه عقب نبرید.
