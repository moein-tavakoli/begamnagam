# قرارداد API نسخه اول

نمایش عددها در رابط فارسی است؛ مقادیر عددی JSON و رشته‌های استاندارد شماره،
OTP، شناسه، تاریخ و مرجع بانکی برای API/ذخیره‌سازی با قالب مستند و ارقام انگلیسی
باقی می‌مانند. نمایش قلم snapshot امضاشده را تغییر نمی‌دهد. ورودی انسانی تازه
در کلاینت و مستقلاً در parser مشترک JSON سرور، پیش از اعتبارسنجی/ثبت به ارقام
ASCII یکسان‌سازی می‌شود؛ متن تازه نیز شامل این قاعده است. عدد/Boolean/null
نوع JSON خود را حفظ می‌کنند و رشتهٔ عددی جای عدد JSON پذیرفته نمی‌شود. رمز و
نام کاربری ورود، توکن، امضا، شناسهٔ غیرشفاف، نسخهٔ قرارداد و authority عیناً
حفظ می‌شوند؛ snapshot قبلی و پاسخ/callback درگاه بازنویسی نمی‌شوند.
[جزئیات و بررسی‌ها](persian-digits.fa.md).

## پیشنهاد جایگزین و سقف اختصاصی حساب — محلی

خطای محتوایی پیش‌نمایش می‌تواند `error.details.alternatives` داشته باشد: فهرست `{id,label,text,token,message_tone,expires_at}`. این متن‌ها پیشنهادهای مستقل و از قالب‌های بررسی‌شده‌اند؛ خطای۵۰۰/۵۰۳جزئیات یا پیشنهاد جایگزین ندارد. علت رد در صورت شاهد پالایش محلی می‌تواند عبارت کوتاه خود نویسنده را ذکر کند؛ مدلِ بدون شاهد، واژهٔ مشکل‌دار حدس نمی‌زند و اطلاعات تماس تکرار نمی‌شوند.

پس از انتخاب صریح، `POST /messages/preview` با `{source_mode:"reviewed_alternative", alternative_token, recipient_phone, message_tone}` یک پیش‌نمایش معمول می‌سازد. `text`، `category` یا نتیجهٔ بررسی کلاینت در این درخواست پذیرفته نمی‌شوند. مجوز رمز/امضاشده پنج‌دقیقه‌ای و وابسته به حساب، نشست، گیرنده، لحن و بدنهٔ دقیق قالب است؛ نامعتبر/منقضی با۴۰۹و `alternative_expired` رد می‌شود. این مسیر AI را صدا نمی‌زند و اصل متن ردشده را ارسال نمی‌کند. ثبت سفارش و تأیید نهایی قرارداد قبلی را دارند.

`POST /manage/actions` با `action:"account_limits"`, `object_id`, `reason` و `values:{sender_daily_limit, rewrite_daily_limit}`، مجوز `core.manage_account_limits` و CSRF لازم دارد. فقط این دو کلید با نوع `null` یا integer۰تا۱۰۰۰۰۰۰مجازند؛ Boolean و رشته رد می‌شوند. `null` یعنی تنظیم سایت،۰یعنی تعداد نامحدود. فهرست حساب‌ها همین دو فیلد را برمی‌گرداند. ثبت قبل/بعد و قفل فرستنده برقرارند؛ اعتبار و مصرف پاک نمی‌شوند. [شرح و محدودیت‌ها](message-rejection-and-account-limits.fa.md).

## لحن پیام

bootstrap فهرست `message_tones:[{id,label,description}]` از لحن‌های فعال و `default_message_tone` را می‌دهد. `POST /messages/preview` فیلد اختیاری `message_tone: polite|firm|angry` می‌پذیرد و همان را در پاسخ برمی‌گرداند؛ مقدار نامعتبر422و لحن غیرفعال409با `tone_unavailable` است. انتخاب حذف‌شده از پنل باید با bootstrap تازه به‌روز شود. بدون گزینهٔ فعال، فهرست خالی و پیش‌فرض `polite` است. قیمت/متن/مجوز بررسی همچنان از سرور می‌آیند.

`/manage/ai` در `values` سه Boolean مستقل `tone_polite_enabled`, `tone_firm_enabled`, `tone_angry_enabled` و در `tone_options` شرح گزینه‌ها را دارد. ذخیره، مجوز `core.manage_ai`، CSRF، دلیل و revision لازم دارد. `/manage/ai/test` هم فیلد اختیاری `message_tone` را با همان گزینه‌های فعال می‌پذیرد. [معنا و حدود لحن‌ها](ai-ollama.fa.md#مدیریت).

## کیف پول و روش پرداخت

`GET /api/v1/wallet` ماندهٔ صحیح تومان به‌صورت رشته، وضعیت روش‌ها، `withdrawable:false`،۱۰۰گردش آخر و۳۰درخواست شارژ آخر صاحب نشست را می‌دهد. `GET /wallet/topups/<uuid>` فقط شارژ متعلق به همان حساب و محیط را برمی‌گرداند. اطلاعات provider، شماره و متن پیام در این پاسخ‌ها نیست.

`POST /wallet/topups` بدنهٔ دقیق `{amount_toman: integer, consent: true, terms_version: "wallet-credit-v1"}`، `Idempotency-Key` و CSRF می‌خواهد. مبلغ۱تا۲۱۴۷۴۸۳۶۴۷تومان است. پاسخ `id, amount_toman, status, created_at, redirect_url` دارد؛ redirect فقط برای همان پرداخت pending برمی‌گردد. `unknown` اجازهٔ تلاش خودکار تازه نمی‌دهد؛ شارژ فقط پس از verify سمت سرور ثبت می‌شود. callback به `/wallet?topup=<uuid>` هدایت می‌کند.

فروش تازه فقط بسته‌ای است. پیش‌نمایش فقط `payment_method:credit` با قیمت صفر می‌سازد؛ درخواست صریح `wallet|gateway` با409و `package_required` رد می‌شود، مستقل از هدیه و کلیدهای روش پرداخت. `POST /orders` پیش‌نمایش قدیمی پولی را رد می‌کند و اعتبار هدیه/بسته را اتمیک رزرو می‌کند. `POST /orders/<uuid>/pay-wallet` برداشت تازه نمی‌کند؛ فقط پاسخ سفارش تاریخیِ قبلاً پرداخت‌شده را تکرار می‌کند. `/orders/<uuid>/payments` فقط همان authority تاریخی pending در محیط جاری را ادامه می‌دهد و درخواست درگاه تازه نمی‌سازد. وضعیت‌های `wallet_paid|wallet_returned` برای سوابق قدیمی حفظ‌اند؛ callback، verify و تعهد برگشت هزینه تغییری نمی‌کنند.

کلیدهای `wallet_enabled` و `gateway_enabled` از API مدیریت تنظیمات با reason/revision و مجوز فعلی مدیریت محدودیت قابل تغییرند. سوابق `wallet-entries` و `wallet-topups` در API رکوردهای ادمین، فقط خواندنی و با مجوز مدل مربوط هستند. هیچ endpoint برداشت، انتقال یا افزایش دلخواه موجودی وجود ندارد. [قرارداد مالی و رفتار خاموش‌کردن](wallet.fa.md).

## پنل مدیریت Next.js

برای پیش‌نمایش‌های جدیدِ موفق، `Preview.original_text` متن دقیق ورودی را جدا از خروجی نهایی و به‌صورت رمزگذاری‌شده نگه می‌دارد. این فیلد در پاسخ پیش‌نمایش، سفارش و تاریخچهٔ کاربر وجود ندارد. پس از ثبت سفارش، `POST /api/v1/manage/orders/<uuid>/texts` با `reason`، نشست فعال کارکنان و هر دو مجوز `core.view_order` و `core.view_private_message_text`، متن اولیه/نهایی را برمی‌گرداند؛ هر مشاهده با `message_text_viewed` ثبت می‌شود. سوابق مدیر شامل متن نیستند. در ادمین جنگو هم همین مجوز و ثبت سابقه اعمال می‌شود. پیام‌های قدیمی مقدار خالی دارند؛ متن اولیهٔ آن‌ها بازسازی نمی‌شود. دادهٔ ردشده یا بازنویسی ناموفق ذخیره نمی‌شود؛ تنها متن نهایی بررسی‌شده وارد snapshot پیامک می‌شود.

مسیر فرانت `/manage` است. APIهای کارکنان در `/api/v1/manage/` از نشست جنگو و CSRF استفاده می‌کنند؛ حساب تلفنی عادی دسترسی ندارد. فهرست‌ها مجوز مشاهدهٔ مدل و اقدامات مجوز اختصاصی لازم دارند. قرارداد مسیرها و کنترل نسخهٔ تنظیمات در [راهنمای مدیریت](management.fa.md) آمده است. `/admin/` برای مدیریت پیشرفته باقی می‌ماند.

## تنظیمات محدودیت در زمان اجرا

قیمت بسته از snapshot بسته می‌آید و فقط در بخش بسته‌ها قابل تنظیم است. تعرفهٔ تکی دیگر در تنظیمات مدیر پذیرفته نمی‌شود؛ `bootstrap.price_toman` و قیمت تمام پیش‌نمایش‌های تازه صفرند. [API خرید و مدیریت بسته‌ها](message-packages.fa.md) و [کیف پول](wallet.fa.md).

تنظیم مشترک `SiteLimits` در ادمین، تعداد/بازهٔ ارسال و دریافت، فاصله‌ها، ساعت تهران، دفعات و مهلت دعوت، اعتبار OTP/پیش‌نمایش، سقف هزینه و سهمیهٔ بازنویسی را تعیین می‌کند. `RequestLimit` تعداد و بازهٔ درخواست هر مسیر را کنترل می‌کند. API مدیریتی عمومی یا دسترسی فرستنده برای تغییر این داده‌ها وجود ندارد؛ مجوز `core.manage_site_limits`، دلیل تغییر و ثبت قبل/بعد لازم‌اند. هر درخواست وب یک snapshot دارد؛ درخواست بعدی و worker تنظیم ذخیره‌شده را می‌خوانند.

در پاسخ دعوت، `daily_remaining` و `sends_remaining` می‌توانند `null` باشند؛ یعنی سقف تعداد غیرفعال است، نه صفر نوبت. `max_sends`, `daily_limit`, `window_hours`, `cooldown_hours`, `validity_days` تنظیم جاری را توضیح می‌دهند؛ مهلت یا سقف غیرفعال با `null` نمایش داده می‌شود. تغییر عدد پایین‌تر از مصرف قبلی، مانده را صفر می‌کند و عدد منفی برنمی‌گرداند. دلیل عمومی گیرنده همچنان قطع دریافت، صف باز و سقف/فاصله را از هم تفکیک نمی‌کند.

`sender_window_hours`، `recipient_window_hours` و `invitation_window_hours` صفر را برای غیرفعال‌کردن سقف تعداد متناظر می‌پذیرند؛ مقدار تعداد و تاریخچه حفظ می‌شوند. با `invitation_window_hours=0`، پاسخ دعوت `daily_remaining=null` و `daily_limit=null` دارد، در حالی که `window_hours=0` است. فیلدهای فاصلهٔ ساعتی نیز با صفر خاموش‌اند. `sending_start_hour` در محدودهٔ ۰ تا ۲۳ و `sending_end_hour` در محدودهٔ ۰ تا ۲۴ است؛ صفر یعنی نیمه‌شب. شروع و پایان برابر فقط وقتی `sending_window_enabled=false` است پذیرفته می‌شوند. کنترل قطع دریافت، پیام/دعوت در انتظار نتیجه، اعتبارها، انقضای OTP/پیش‌نمایش و محدودیت‌های امنیتی مستقل‌اند.

اعتبار OTP و پیش‌نمایش جدید از تنظیم جاری می‌آید؛ snapshotهای قبلی تمدید نمی‌شوند. دفتر هزینه با تغییر سقف پاک نمی‌شود و نتیجهٔ نامعلوم دوباره ارسال نمی‌شود. سهمیهٔ۳هدیه و۳جایزهٔ دعوت طبق تصمیم کارفرما تغییری نکرده‌اند.

از نسخه۰٫۸٫۱۵ پروفایل `config.live_sms_settings`، `demo_mode:false`، `otp_is_real:true` و `payment_backend:disabled` برمی‌گرداند. هر حساب ۳ هدیهٔ واقعی دارد؛ پس از اتمام هدیه، سفارش تازه به اعتبار بسته نیاز دارد؛ نبود اعتبار409با `credit_required` می‌دهد. خرید بسته تا آماده‌سازی و مجوز مستقل درگاه بسته است و مسیر پرداخت تکی، تراکنش تازه نمی‌سازد. ارسال رایگان به رضایت و `terms_version` جاری نیاز دارد؛ پیش‌نمایش یا سفارش آزمایشی قدیمی باید دوباره ساخته و تأیید شود. `accepted` پذیرش کاوه‌نگار و `delivered` رسید تحویل است؛ `delivered_demo` تاریخی هرگز واقعی محسوب نمی‌شود.

مبنای مسیرها `/api/v1` است؛ بدون slash پایانی. فرانت همه درخواست‌ها را از همان مبدأ می‌فرستد و Next.js آن‌ها را به Django بازنویسی می‌کند. نسخه۰٫۷ اتصال‌های محافظت‌شده ارائه‌دهندگان را دارد؛ اجرای پیش‌فرض محلی همچنان demo و شبکه خارجی خاموش است. در تنظیم انتشار، Caddy مسیرهای API/admin را مستقیم به backend خصوصی می‌رساند.

## نشست و CSRF

ابتدا `GET /bootstrap` فراخوانی می‌شود تا cookie `csrftoken` تنظیم شود. درخواست‌های تغییردهنده باید JSON، cookie نشست و هدر `X-CSRFToken` را داشته باشند. پس از ورود، CSRF دوباره از cookie خوانده می‌شود، چون Django توکن را می‌چرخاند. cookie نشست HttpOnly است؛ bearer token در localStorage نگهداری نمی‌شود.

```js
await fetch('/api/v1/messages/preview', {
  method: 'POST',
  credentials: 'same-origin',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfTokenFromCookie,
  },
  body: JSON.stringify({ category: 'appreciation', text: 'از همراهی شما ممنونم.', recipient_phone: '09xxxxxxxxx' }),
});
```

## قرارداد عمومی

بدنهٔ JSON بیش از۸۱۹۲بایت با HTTP413 و کد `request_too_large` رد می‌شود. خطاهای ValueError غیرمنتظره، متن داخلی یا مقدار خصوصی را در پاسخ منعکس نمی‌کنند؛ پیام‌های اعتبارسنجی مشخص عمومی حفظ شده‌اند. همهٔ پاسخ‌های API دارای CSP محدود و `no-store` هستند. فرم بومی ادمین از referrer همان origin برای CSRF استفاده می‌کند؛ API و لینک‌های گیرنده همچنان `no-referrer` هستند.

- موفقیت APIهای JSON با HTTP 200 برمی‌گردد؛ تکرار سفارش نیز همان سفارش را با 200 بازمی‌گرداند.
- شناسهٔ پیش‌نمایش، چالش و سفارش UUID است؛ حدس‌نزدنی‌بودن شناسه جای کنترل مالکیت را نمی‌گیرد.
- مبلغ‌ها عدد صحیح و به تومان‌اند؛ قیمت از سرور و پیش‌نمایش ذخیره‌شده می‌آید.
- تاریخ‌ها ISO 8601 هستند؛ کلاینت نمایش را به فارسی/منطقهٔ زمانی مناسب تبدیل می‌کند.
- شماره ایرانی با ارقام فارسی یا عربی و قالب `09…` یا `+98…` پذیرفته و یکسان‌سازی می‌شود.
- شماره کامل در سابقه یا پاسخ سفارش نمایش داده نمی‌شود.
- خطا به صورت زیر است؛ `fields` اختیاری است:

```json
{"error":{"code":"validation_error","message":"داده‌های ورودی را بررسی کنید.","fields":{}}}
```

خطاهای ورودی/محتوا، احراز هویت، مالکیت، CSRF، محدودیت نرخ و قطع سرویس با status متناسب برمی‌گردند. کلاینت باید پیام سرور را نمایش دهد و با خطا ادامه مسیر را موفق فرض نکند.

## راه‌اندازی و ورود

| روش و مسیر | ورودی | خروجی مهم |
| --- | --- | --- |
| `GET /bootstrap` | ندارد | `demo_mode`, `otp_is_real`, `authenticated`, `phone_masked`, `price_toman`, `categories`, `rewrite_mode` |
| `POST /auth/request-otp` | `phone` | `challenge_id`؛ فقط در حالت OTP شبیه‌سازی‌شده، `debug_code` |
| `POST /auth/verify-otp` | `challenge_id`, `code` | `authenticated: true`, `phone_masked`؛ تنظیم نشست |
| `POST /auth/logout` | `{}` | خروج و بی‌اعتبارشدن نشست |

هر دسته شامل `id`, `label`, `description`, `example` است. شناسه‌های دسته: `appreciation`, `encouragement`, `congratulations`, `body`, `breath`, `noise`, `shared_space`. پیام‌های مثبت هم از همان پیش‌نمایش، تأیید شماره، پرداخت و کنترل‌های گیرنده می‌گذرند؛ ارسال گروهی در این API وجود ندارد.

OTP به نشست درخواست‌کننده متصل، زمان‌دار و محدود به تعداد تلاش است. در حالت پیش‌فرض `OTP_BACKEND=demo` کد در پاسخ و رابط نمایش داده می‌شود و SMS ندارد. این رفتار ورود واقعی محسوب نمی‌شود و در حالت غیرآزمایشی فعال نیست.

در dev/لوکال، کد جدید دقیقاً چهار رقم ASCII است، از جمله صفر ابتدایی؛ نمونهٔ
`0123`. API رقم فارسی/عربی را یکسان‌سازی می‌کند، اما کد کوتاه‌تر/بلندتر و
غیرعددی را رد می‌کند و شش رقم را نمی‌بُرد. چالش شش‌رقمی پیش از این تغییر به
درخواست کد تازه نیاز دارد. HMAC، وابستگی به نشست، مهلت، شمارش تلاش و تک‌مصرف‌بودن
حفظ شده‌اند. متن ثابت پیامک خط `Code:` و timestamp شمسی تهران دارد.

تکمیل خودکار OTP ساختار JSON را تغییر نمی‌دهد. در حالت `KAVENEGAR_OTP_MODE=sms` و با `APP_BASE_URL` عمومی HTTPS معتبر، خط آخر متن ثابت پیامک به‌شکل `@begamnagam.ir #0123` از دامنهٔ تنظیم‌شده و همان کد تولید می‌شود؛ مقدار نمونه است. مرورگر پشتیبان فقط با اجازهٔ کاربر کد را در فرم می‌گذارد و تأیید همچنان POST دارای CSRF و `challenge_id` همان نشست است. حالت `lookup` قالب تأییدشدهٔ ارائه‌دهنده را تغییر نمی‌دهد؛ قالب آن نیز برای این قابلیت باید خط آخر متناظر را داشته باشد. [راهنمای تکمیل خودکار و PWA](otp-pwa.fa.md).

از نسخه۰٫۸٫۳، حالت صریحاً فعال‌شده می‌تواند `demo_mode=true` و `otp_is_real=true` داشته باشد: کد ورود واقعی است، اما پرداخت و پیام به گیرنده شبیه‌سازی می‌شوند. از نسخه۰٫۸٫۱۴، `POST /auth/request-otp` برای همهٔ شماره‌های معتبر ایران کار می‌کند و فهرست مجاز شمارهٔ ورود وجود ندارد؛ `OTP_TEST_RECIPIENT_HASHES` حذف شده است. فهرست پایلوت تحویل پیام در حالت خارجی هم شرط ورود نیست. اعتبارسنجی شماره، CSRF، حداکثر۳درخواست هر شماره در۱۰دقیقه،۶درخواست هر نشست، محدودیت سیل IP و بودجهٔ مشترک پیش از تماس provider اعمال می‌شوند. پاسخ کد واقعی هرگز `debug_code` ندارد و `demo_mode=false` در پاسخ همان درخواست OTP است؛ `demo_mode` در bootstrap همچنان محیط پرداخت/پیام را توصیف می‌کند. `GET /healthz` هم `otp_is_real` را بدون افشای شماره یا اعتبارنامه برمی‌گرداند. smoke قبل از درخواست کد، چنین محیطی را رد می‌کند.

نسخه۰٫۸٫۴ در پاسخ OTP واقعی، `delivery_status=accepted` برای پذیرش سرویس‌دهنده یا `unknown` برای پاسخ نامطمئن دارد؛ هیچ‌کدام رسید گوشی نیست. در unknown، کد احتمالی را می‌توان وارد کرد و ارسال خودکار تکرار نمی‌شود. شکست قطعی TLS/DNS/اتصال پیش از ارسال یا پاسخ ردشده، خطای `otp_unavailable` با HTTP503 می‌دهد و چالش مصرف‌شده می‌شود؛ پاسخ موفق ساختگی برنمی‌گردد.

## پیش‌نمایش

در رابط۰٫۸٫۶، شمارهٔ گیرنده در همان صفحهٔ متن نهایی وارد می‌شود و «آماده‌سازی متن» پیش‌نمایش متصل به آن شماره را می‌سازد؛ صفحه عوض نمی‌شود. ویرایش شماره، پیش‌نمایش و تأیید قبلی را پاک می‌کند و قبل از ارسال، پیش‌نمایش تازه لازم است. API و کنترل اتصال شماره/قیمت/متن در سرور تغییری نکرده‌اند.

در رابط۰٫۸٫۵، همهٔ ورودی‌های شماره/OTP ارقام فارسی و عربی را هنگام تغییر به انگلیسی تبدیل می‌کنند؛ قبل از درخواست API، یکسان‌سازی شماره/کد نیز انجام می‌شود. متن آزاد پیام یا شناسه‌ها با تبدیل عمومی JSON بازنویسی نمی‌شوند. سرور همچنان مستقل از فرانت قالب و ارقام شماره/کد را بررسی می‌کند.

`POST /messages/preview` به ورود نیاز ندارد، ولی به نشست و CSRF و محدودیت نرخ نیاز دارد:

```json
{"category":"appreciation","text":"از همراهی شما ممنونم."}
```

پاسخ شامل `preview_id`, `rewritten_text`, `full_sms`, `sms_segments`, `price_toman`, `expires_at`, `moderation_mode`, `terms_version` است. متن ورودی حداکثر ۲۸۰ نویسه است. `template` یعنی انتخاب قالب بررسی‌شده بدون مدل؛ `ollama_curated` یعنی انتخاب محدود قالب با مدل محلی. متن خام کاربر و خروجی آزاد مدل وارد SMS نمی‌شوند. خطای مدل یا ورودی ممنوع پیش‌نمایش معتبر تولید نمی‌کند.

پیش‌نمایش به نشست سازنده متصل است و پس از تأیید شماره در همان نشست قابل استفاده می‌ماند. متن و مبلغ قابل تغییر از سمت کلاینت نیستند. تغییر موضوع یا متن نیازمند پیش‌نمایش تازه است.

## سفارش و تأیید ارسال

### سهمیهٔ رایگان۰٫۸٫۹

هر `Account` موجود یا جدید۳ارسال رایگان یک‌باره دارد؛ ورود مجدد یا تغییر روز آن را شارژ نمی‌کند. bootstrap فقط برای حساب تأییدشده `free_sends_total:3` و `free_sends_remaining` را برمی‌گرداند. اعتبار خریداری‌شده در `purchased_sends_remaining` و بسته‌های فعال در `message_packages` هستند؛ `package_checkout_enabled` وضعیت خرید تازه را مشخص می‌کند.

پیش‌نمایش با سهمیهٔ باقی‌مانده `is_free:true, price_toman:0` دارد؛ ساختن چند پیش‌نمایش، سهمیه را رزرو نمی‌کند. `POST /orders` برای quote رایگان یک واحد را اتمیک رزرو و سفارش را با `is_free:true, amount_toman:0, payment_mode:free` ثبت می‌کند. فیلدهای قیمت/رایگان ارسالی کلاینت معتبر نیستند؛ snapshot سرور ملاک است. همان Idempotency-Key دوباره سهمیه مصرف نمی‌کند. اگر تب دیگری سهمیه را مصرف کرده باشد، پاسخ409با `free_quota_changed` می‌آید؛ کاربر باید متن و هزینهٔ تازه را تأیید کند، پرداخت خودکار رخ نمی‌دهد. پیش‌نمایش‌های قدیمی خرید تکی باید دوباره ساخته شوند. هر ارسال غیرهدیه یک اعتبار از بسته رزرو می‌کند.

`POST /orders/{id}/confirm-free` با `{}` برای مالک تأییدشده، CSRF و سفارش رایگان معتبر است. کنترل تعلیق/گیرنده و مجوز سرویس انجام و همان outbox ساخته می‌شود؛ تکرار آن ارسال یا مصرف سهمیهٔ تازه ندارد. `POST /orders/{id}/payments` سفارش رایگان را به درگاه نمی‌برد. مسیر قدیمی pay-demo در محیط demo سفارش رایگان را به همین منطق هدایت می‌کند؛ پرداخت صفر یا تراکنش مالی ساختگی ساخته نمی‌شود. `paid_at` در سفارش رایگان زمان اجازهٔ پردازش صف است؛ `financial_status:free` و `is_free` مشخص می‌کنند پولی پرداخت نشده است.

انقضای رزرو پرداخت‌نشده پس از۱۵دقیقه، انقضای صف ارسال‌نشده، توقف یا شکست قطعی ارسال، سهمیه را یک‌بار برمی‌گرداند و `financial_status:free_credit_returned` می‌دهد. نتیجهٔ نامعلوم سهمیه را آزاد نمی‌کند تا ارسال تکراری رخ ندهد. سه سهمیهٔ رزروشده می‌توانند موقتاً مانده را صفر کنند. سایر محدودیت‌ها، مصرف اعتبار بسته پس از سهمیه، تعدیل محتوا و سیاست provider برقرارند؛ رایگان بودن، ارسال واقعی را فعال نمی‌کند.

از نسخه۰٫۸٫۸ سقف فرستنده۵سفارش در۲۴ساعت گذشته است؛ پرداخت‌نشده/لغوشده نیز حساب می‌شود. به هر گیرنده از مجموع فرستنده‌ها حداکثر یک پیام در۲۴ساعت می‌رسد و همان جفت فرستنده/گیرنده نیز فاصله۲۴ساعته دارد. شمارهٔ خود، قطع دریافت و رزرو باز همچنان مانع‌اند. علت خصوصی در خطای عمومی گیرنده افشا نمی‌شود. ابزار ادمین `/admin/core/account/test-limits/` فقط در محیط آزمایشیِ صریحاً فعال‌شده، با مجوز و CSRF پنجرهٔ شمارش را از نو شروع می‌کند؛ API عمومی یا تغییر در OTP/پرداخت ندارد. از نسخه۰٫۸٫۱۲ مدیر با مجوز مستقل می‌تواند برای یک حساب ارسال نامحدود آزمایشی را فعال کند؛ فقط در محیط کاملاً demo و با حفظ قطع دریافت و سفارش باز اثر دارد. پارامترهای درخواست کاربر نمی‌توانند این مجوز را تغییر دهند.

در رابط جاری، پیش‌نمایش، شمارهٔ ثابت گیرنده، مصرف اعتبار و تأیید قوانین در یک مرحله‌اند. پس از تأیید، ابتدا سفارش و سپس تأیید هدیه/بستهٔ همان سفارش فراخوانی می‌شود؛ خرید بسته جداست. تلاش دوباره همان سفارش و کلید را حفظ می‌کند و شماره/متن سفارش ساخته‌شده قابل ویرایش نیستند. پیش‌نمایش تازه، تأیید قوانین تازه می‌خواهد.

`POST /orders` نیازمند ورود است. هدر `Idempotency-Key` باید UUID تازه‌ای برای هر قصد خرید باشد؛ در retry همان کلید حفظ می‌شود.

```json
{"preview_id":"uuid","recipient_phone":"09xxxxxxxxx","consent":true,"terms_version":"نسخه بازگشتی از quote"}
```

پاسخ: `id`, `status`, `amount_toman`, `payment_mode`. یک پیش‌نمایش برای یک سفارش است. استفاده دوباره از همان کلید با محتوای متفاوت باید خطای تعارض بدهد. فرستادن به شماره خود و سفارش خارج از محدودیت‌ها پذیرفته نمی‌شود. API علت خصوصی عدم امکان ارسال به گیرنده را نمایش نمی‌دهد.

`POST /orders/{id}/pay-demo` با بدنه `{}` فقط در محیط demo و برای صاحب سفارش معتبر است. سفارش هدیه یا اعتباری را به همان منطق تأیید ارسال هدایت می‌کند؛ پرداخت تکی یا capture تازه نمی‌سازد. سفارش پولی تاریخیِ قبلاً پرداخت‌شده فقط پاسخ قبلی را می‌دهد و سفارش پولی پرداخت‌نشده409با `package_required` می‌گیرد. بازیابی همان outbox با beat انجام می‌شود. این endpoint در محصول واقعی بسته است؛ آزمون خودکار آن در دیتابیس جدا اجرا می‌شود.

| وضعیت | معنا |
| --- | --- |
| `awaiting_payment` | سفارش ساخته و هدیه/اعتبار رزرو شده؛ تأیید ارسال انجام نشده |
| `queued` | تأیید ارسال ثبت و outbox آماده شده |
| `delivered_demo` | پردازش شبیه‌سازی موفق؛ هیچ SMS واقعی یا خوانده‌شدن ادعا نمی‌شود |
| `cancelled` | سفارش متوقف شده |
| `failed` | پردازش ناموفق |

`GET /orders/{id}` فقط برای صاحب سفارش است. `GET /messages` سابقه همان فرد را در `{ "results": [...] }` می‌دهد. هر ردیف شامل شناسه، شماره پوشیده، متن بررسی‌شده، وضعیت، مبلغ و زمان ساخت است. این وضعیت‌ها رسید محلی‌اند و در فاز provider واقعی باید از افشای رفتار گیرنده جلوگیری شود.

## ترجیح دریافت

`GET /preferences` و `POST /preferences` نیازمند تأیید شماره و نشست‌اند و فقط ترجیح شمارهٔ خود کاربر را می‌خوانند یا تغییر می‌دهند:

```json
{"blocked":true}
```

این API وضعیت یک شمارهٔ دلخواه را نمی‌پذیرد و ابزار جست‌وجوی گیرنده نیست. توقف دریافت دوباره پیش از پردازش نهایی کنترل می‌شود. بازفعال‌سازی `blocked:false` به تأیید OTP حداکثر۵دقیقه‌ای نیاز دارد. مسیر بی‌حساب گیرنده در ادامه آمده است.

## سلامت و مدیریت

`GET /healthz` خارج از prefix API سلامت پایگاه و کش را برای Compose بررسی می‌کند. پنل Django در `/admin/` با حساب مدیر ساخته‌شده توسط اپراتور در دسترس است. هیچ رمز پیش‌فرضی وجود ندارد. دسترسی API عمومی با دسترسی مدیر یکسان نیست.

## Version 0.3.0 additions (local demo)

`POST /messages/preview` accepts optional `recipient_phone` for compatibility. A
recipient-bound quote requires a verified sender and cannot be retargeted at
checkout. The UI always uses this bound form. Response adds `full_sms` and
`sms_segments`; `rewritten_text` remains the reviewed body for existing clients.
The server rejects final messages over three Unicode SMS segments.

Order responses add `financial_status` and `delivery_status`. `text` now exposes
the frozen full SMS including the service/footer URL; internal reviewed body is
kept separately. Live delivery/read receipts are never inferred from demo states.
Historical demo captures and compensating refunds remain readable and idempotent.
New demo sends use isolated gift/package credits and create no per-message capture;
definitive failure returns one reserved unit. They never move real money or call
a real provider, and are never substituted for the user-facing real product.


## نسخه۰٫۷: اتصال، رضایت و کنترل گیرنده

UI همیشه quote دارای گیرنده می‌سازد. `terms_version` همراه quote ثابت می‌شود؛ ایجاد سفارش در حالت خارجی به `consent:true` و همان نسخه نیاز دارد. `consent_at` و نسخه در سرور ثبت می‌شوند؛ تغییر تنظیم شرایط، snapshot قبلی را عوض نمی‌کند. بدنهٔ پیام و قیمت/گیرنده را از کلاینت نمی‌پذیریم.

`POST /orders/{id}/payments` با `{}` فقط برای مالک، همان authority تاریخیِ pending در محیط جاری را با همان `attempt_id` و `redirect_url` برمی‌گرداند؛ intent یا درخواست درگاه تازه نمی‌سازد. سفارش تازهٔ هدیه/بسته یا سفارش پولی بدون authority قبلی409با `package_required` و تلاش نامعلوم/نامنطبق409با `payment_reconciliation` می‌گیرد. `GET /payments/return/zarinpal?Authority=…&Status=…` فقط محرک verify مستقلِ محیط متناظر است؛ query و نشست مرورگر اثبات پرداخت نیستند. callback خرید بسته به credits، شارژ به wallet و سفارش تاریخی به history برمی‌گردد. pay-demo بیرون حالت demo غیرفعال است.

وضعیت‌های افزوده: `accepted` یعنی پذیرش ارائه‌دهنده، `delivered` یعنی DLR تحویل، `unknown` یعنی نتیجه نیازمند تطبیق. هیچ‌کدام خوانده‌شدن یا هویت گیرنده را ثابت نمی‌کند. پاسخ سفارش، `financial_status` و `delivery_status` مستقل دارد؛ refund باز `refund_pending` و refund تأییدشده `refunded` است. توقف بعد پرداخت، موفقیت دیرهنگام و مبلغ نامطابق به رسیدگی مستقل می‌روند؛ ارسال دوم از حدس نتیجه مجاز نیست. تاریخچه پس از retention متن پاک‌شده را با placeholder نشان می‌دهد.

لینک پیامک تازه از نسخه۰٫۸٫۱۶ به‌شکل `begamnagam.ir/r/A7k2P9xQ` است؛ کد فقط۸حرف انگلیسی و عدد دارد و `#` در متن پیامک نیست. GET/HEAD مسیر `/r/<code>` بدون lookup یا تغییر ترجیحات، با۳۰۷ به `/r#<code>` می‌روند؛ سپس صفحهٔ موجود، کد را با JSON و CSRF ارسال می‌کند. پاسخ redirect و صفحه `no-store`، `no-referrer` و `noindex` دارند. لینک‌های fragment قبلی معتبر می‌مانند و snapshot قدیمی تغییر نمی‌کند. مسیر تازه به proxy می‌رسد؛ پیش از فعال‌سازی باید ثبت URI این مسیر در همهٔ proxyها، access/error log و analytics بسته یا حذف شود. APP_BASE_URL و HTTPS تغییری نمی‌کنند. ابتدا bootstrap و CSRF دریافت و سپس:

| مسیر POST | JSON | خروجی |
| --- | --- | --- |
| `/recipient/actions/inspect` | `token` | `active`, `can_report`؛ بدون هویت/متن |
| `/recipient/actions/stop` | `token` | `blocked:true` |
| `/recipient/actions/report` | `token`, `reason`, `details` | `receipt` UUID و `blocked:true` |

`reason` یکی از `unwanted`, `harassment`, `wrong_number`, `other` و توضیح حداکثر۵۰۰نویسه است. از نسخه۰٫۸٫۱۳ کد تازه۸نویسهٔ تصادفی از حروف انگلیسی بزرگ/کوچک و اعداد است؛ لینک‌های قبلی۴۳نویسه‌ای نیز پذیرفته می‌شوند. کد فقط پس از پذیرش ارسال فعال می‌شود؛ stop۳۶۵روز و report۳۰روز معتبر است. GET هیچ تغییری نمی‌دهد. گزارش تکراری همان پرونده را می‌دهد؛ علت خصوصی/شماره/فرستنده بازگردانده نمی‌شوند. پاسخ همه این مسیرها `no-store` و `no-referrer` است.

`POST /account/deletion` با `{}` و OTP تازه، درخواست حذف شماره طی۳۰روز را ثبت و ارسال جدید حساب را متوقف می‌کند؛ رکورد حداقلی مالی و منع دریافت باقی می‌مانند. `GET /operations/status` فقط برای staff فعال با `core.view_operations` مجاز و خروجی آن جمعی است. اقدام‌های مدیریتی حساس از admin با مجوز مستقل، دلیل و audit انجام می‌شوند. bootstrap یک `session_identity` غیرقابل‌استفاده به‌عنوان اعتبارنامه دارد؛ فقط برای تشخیص تعویض حساب و پاک‌کردن حافظه خصوصی تب‌هاست.

## لحن حساب و پیش‌نمایش۰٫۸٫۱۲

قرارداد قدیمی `gentle|direct` با سه لحن سراسری ابتدای این سند جایگزین شده است. پیش‌نمایش تازه، انتخاب مجاز `polite|firm|angry` را می‌پذیرد و همان را برمی‌گرداند؛ تیک قدیمی حساب روی انتخاب تازه اثر ندارد. متن نهایی و لحن snapshot ثابت‌اند و تغییر تنظیم مدیر پیش‌نمایش یا سفارش قبلی را بازنویسی نمی‌کند. worker همان متن بررسی‌شده و امضای معتبر را دوباره اعتبارسنجی می‌کند.

تیک `unlimited_demo_sends` فقط از پنل مدیریت با مجوز `manage_test_sending` و ثبت دلیل قابل تنظیم است. فقط سقف‌ها و فاصله‌های ارسال/پیش‌نمایش مربوط به همان حساب را در محیط بستهٔ demo کنار می‌گذارد؛ محدودیت IP، OTP، بودجه، قطع دریافت، تعلیق، ارسال به خود و رزرو باز حفظ می‌شوند. تیک `direct_message_tone` مجوز مستقل `manage_message_tone` دارد. هیچ‌کدام فیلد قابل‌ویرایش API عمومی یا profile نیستند.

## لینک کوتاه لغو۰٫۸٫۱۳

کدهای تازه دقیقاً۸نویسه از `A–Z`, `a–z`, `0–9` و حساس به بزرگی/کوچکی‌اند؛۴یا۶نویسه پذیرفته نمی‌شود. کد تصادفی است و از شماره یا شناسهٔ ترتیبی ساخته نمی‌شود. هش HMAC کد، unique است؛ برخورد احتمالی در savepoint با کد تازه تکرار می‌شود و شکست مکرر پاسخ۵۰۳ می‌دهد و کل پیش‌نمایش rollback می‌شود. Digest کدهای ارسال‌شده پس از انقضا هم رزرو می‌ماند، ولی اتصال به گیرنده پاک می‌شود تا کد قدیمی به گیرندهٔ تازه اختصاص پیدا نکند.

هر سه مسیر recipient/actions سقف۳۰درخواست در۱۰دقیقه برای نشست و کد، و۱۲۰درخواست در۱۰دقیقه برای IP دارند؛ تغییر نشست یا کد، محدودیت IP را دور نمی‌زند. کوتاه‌شدن کد مجوز مشاهدهٔ شماره، فرستنده یا متن نمی‌دهد؛ GET تغییری ایجاد نمی‌کند و POST نیازمند CSRF است. snapshot و لینک پیام‌های قبلی بازنویسی نمی‌شوند. تعداد بخش پیامک از متن کامل تازه محاسبه می‌شود و الزاماً برای هر موضوع کاهش نمی‌یابد.

## توضیح وضعیت ارسال۰٫۸٫۱۷

پاسخ سفارش و هر مورد سابقه، `status_reason` با مقدار `null` یا `{code,message}` دارند. این توضیح در رسید و «پیام‌های من» نمایش داده می‌شود. دلیل از نتیجهٔ ذخیره‌شدهٔ همان سفارش خوانده می‌شود؛ تنظیم فعلی گیرنده برای توضیح تاریخچه بررسی نمی‌شود.

کدهای عمومی: `account_unavailable` (محدودیت حساب خود فرستنده)، `recipient_unavailable` (محدودیت کلی ارسال یا دریافت برای شماره)، `moderation_rejected`، `order_expired`، `queue_expired`، `sending_window` و `result_pending`. کد `send_unavailable` توضیح عمومی شکست‌هایی است که علت قابل‌نمایش ندارند؛ دلیل خام provider، کمبود اعتبار و جزئیات سیستم برگردانده نمی‌شوند. موفقیت، خطای قدیمی ذخیره‌شده را نمایش نمی‌دهد. نتیجهٔ نامشخص، شکست قطعی معرفی نمی‌شود و توضیح آن از ارسال دوباره جلوگیری می‌کند.

محدودیت گیرنده در API همچنان یک پاسخ مشترک برای قطع دریافت، فاصلهٔ سراسری دریافت و سفارش باز دارد؛ عضویت یا قطع دریافت شماره مشخص نمی‌شود. فاصلهٔ ناشی از پیام قبلی خود فرستنده با `pair_cooldown` و تعداد ساعت، سقف حساب با `daily_limit` و محدودیت ارسال به شمارهٔ خود با `self_recipient` توضیح داده می‌شود. کنترل‌ها و زمان‌های محدودیت تغییر نکرده‌اند.

پیام خطاهای HTTP۵xx عمومی است و جزئیات fields در آن برگردانده نمی‌شود. رابط هم پاسخ۵xx و خطای runtime نامشخص را عمومی نشان می‌دهد؛ پیام‌های خطاهای قابل اقدام۴xx حفظ می‌شوند. `status_reason` اطلاعات مالی نیست؛ `financial_status` همچنان مستقل و مرجع برگشت سهمیه/وجه است.

## جملهٔ آغاز پیام۰٫۸٫۱۸

`full_sms` پیش‌نمایش تازهٔ پیام گیرنده با `نمیدونم بهت بگم یا نگم؟` و یک newline آغاز می‌شود؛ پس از آن `rewritten_text` و سپس خط نام سرویس/لغو قرار دارد. تعداد بخش از همین متن کامل محاسبه می‌شود. اگر انتخاب بلندِ بررسی‌شده با جملهٔ آغاز از۲۰۱واحدUTF-16عبور کند، متن کاملِ کوتاه‌ترِ بررسی‌شده از همان موضوع و لحن جایگزین و در `rewritten_text` و snapshot ذخیره می‌شود؛ متن بریده نمی‌شود. اگر هیچ متن مجازی جا نشود، پیش‌نمایش و grant rollback و `message_too_long` برگردانده می‌شود.

Adapter دقیقاً snapshot تأییدشده را می‌فرستد؛ جمله در ارسال یا retry دوباره اضافه نمی‌شود. پیش‌نمایش‌ها و سفارش‌های قبلی بازنویسی نمی‌شوند. این جمله برای پیام گیرنده است؛ متن ثابت OTP تغییری نمی‌کند.


## دعوت دوستان۰٫۹٫۰

هر دو مسیر زیر نیازمند نشست حساب تأییدشده، CSRF و `Idempotency-Key` UUID برای POST هستند:

| مسیر | ورودی | خروجی |
| --- | --- | --- |
| `GET /api/v1/invitations?offset=0` | صفحهٔ۵۰تایی | `results`, `next_offset`, `total`, `registered`, `earned_credits`, `daily_remaining`, `consent_version` |
| `POST /api/v1/invitations` | `phone`, `consent:true`, `consent_version:invitations-v1` | دعوت با snapshot بررسی‌شده و outbox |
| `POST /api/v1/invitations/<uuid>/resend` | همان تأیید، بدون شماره | درخواست نوبت بعد برای دعوت متعلق به همان حساب |

هر دعوت شامل شمارهٔ پوشیده، تاریخ، وضعیت `waiting/registered/expired`، `registered_at`، تعداد درخواست، نوبت باقی‌مانده، `can_resend`، `next_send_at`، وضعیت مستقل پیامک، توضیح عمومی و تاریخچهٔ حداکثر۳درخواست است. `reward_credits` پس از ثبت جایزه۳ و در غیر این صورت۰ است؛ `reward_pending` وضعیت افزودن پس از ثبت‌نام را نشان می‌دهد. bootstrap مجموع سهمیهٔ اولیه و جایزه‌ها را در `free_sends_total` و مجموع جایزه را در `free_sends_earned_total` می‌دهد.

شناسهٔ درخواست در retry همان اقدام حفظ می‌شود. درخواست تازه برای شمارهٔ موجود، نوبت تازه ایجاد نمی‌کند؛ باید از resend استفاده شود. حداکثر۳نوبت،۲۴ساعت فاصله،۵درخواست در۲۴ساعت،۳۰روز مهلت resend و۴۸ساعت عمر صف برقرارند. نوبت ناموفق قطعی هم مصرف می‌شود. `pending/submitting/unknown` اجازهٔ resend ندارند؛ retry پردازشگر همان outbox است. `accepted` به‌معنی خواندن یا ثبت‌نام نیست.

کدهای عمومی مهم: `self_invitation`, `already_registered`, `already_invited`, `already_added`, `invitation_limit`, `invitation_pending`, `invitation_cooldown`, `invitation_daily_limit`, `invitation_expired`, `consent_required`. اعلام عضویت قبلی فقط در این پنل احرازشده خواسته شده است؛ هویت دعوت‌کنندهٔ دیگر و قطع دریافت افشا نمی‌شوند. جزئیات اعتبار provider و خطاهای فنی در پاسخ نیستند. فهرست به مالک محدود و no-store/noindex است؛ پیامک متن آزاد، نام فرستنده یا کد معرف ندارد.

پس از اولین تأیید OTP و ساخت Account تازه، با قفل مشترک شماره، دعوت ثبت‌شده پیش از ساخت حساب registered می‌شود. جایزهٔ۳ارسال با قفل دعوت‌کننده و دعوت و ثبت `reward_awarded_at` یک‌بار اعمال می‌شود؛ beat callback ازدست‌رفته را ترمیم می‌کند. دعوت‌شده همان هدیهٔ۳ارسال اولیه را می‌گیرد و ورود مجدد هیچ جایزه‌ای ندارد. دعوت از ماندهٔ فرستادن پیام کم نمی‌کند؛ هزینه زیر همان budget مشترک provider است. شبکه در demo خاموش می‌ماند.


## بازنویسی آزاد۰٫۱۰٫۰

bootstrap فقط با AI_MODE=gapgpt، کلید/مدل و سقف مثبت، rewrite_mode=gapgpt می‌دهد؛ بدون آن UI قالب آماده و اعلان غیرفعال‌بودن را دارد. POST preview جدید source_mode=freeform یا suggestion می‌فرستد. freeform غیرفعال۴۰۹با freeform_unavailable دارد؛ suggestion غیرفعال باید دقیقاً مثال واقعی باشد. نبود source_mode برای کلاینت قدیمی در حالت قالب حفظ شده است. در حالت GapGPT، category خالی یا hint است و هرگز متن را محدود نمی‌کند؛ category داخلی custom است.

حساب تأییدشده و گیرندهٔ معتبر پیش از تماس AI لازم‌اند. ورودی۲۸۰نویسه، پالایش محلی، تولید و بررسی مستقل مدل و کنترل محلی خروجی برقرارند؛ تهدید/دادهٔ تماس/دستور دورزدن و فحش بدون منظور پیش از شبکه رد می‌شوند. خطا یا پاسخ نامعتبر، قالب جایگزین یا retry خودکار ندارد. rewrite_daily_limit با۴۲۹سقف حساب را توضیح می‌دهد؛ خطاهای فنی/اعتبار عمومی‌اند.

اصلاح نسخهٔ۰٫۱۲٫۲، خطای معنایی را از رد محتوایی جدا می‌کند. پاسخ‌ها همچنان در قالب معمول `error.code` و `error.message` هستند و پیش‌نمایش ارسال تولید نمی‌کنند:

| HTTP | کد | معنی |
| --- | --- | --- |
| 422 | `rewrite_intent_changed` | بازبین تغییر منظور یا اضافه‌شدن ادعا را تشخیص داده است؛ پیام دربارهٔ حفظ‌نشدن منظور است، نه تهدیدبودن ورودی. |
| 422 | `rewrite_intent_unclear` | مدل هدف جمله را روشن تشخیص نداده است. |
| 422 | `rewrite_output_rejected` | نسخهٔ تولیدشده در کنترل محلی، قالب یا لحن تأیید نشده است. |
| 422 | `moderation_rejected` | رد محتوایی/حریم خصوصی با توضیح متناسب؛ اگر علت معلوم نیست پیام خنثی است. |
| 503 | `rewrite_unavailable` | خطای شبکه، مهلت، پاسخ ناقص یا ساختار نامعتبر سرویس. |

تعریف، ابراز محبت و شوخی دوستانهٔ بی‌آزار بدون درخواست عملی هم منظور معتبر دارند. مثال پرامپت مجوز عبور نیست؛ تمام کنترل‌ها، بازبینی مستقل و امضای دقیق متن برقرارند. فقط کد ثابتِ علت و نام کنترل‌های شکست‌خورده ثبت می‌شوند؛ توضیح آزاد مدل، متن کاربر و پاسخ خام در audit یا لاگ قرار نمی‌گیرند. این اصلاح روی سرور منتشر شده است؛ [ارزیابی واقعی و محدودیت آن](ai-gapgpt.fa.md#اصلاح-رد-اشتباه-پیام-دوستانه).

پاسخ شکل قبلی دارد: moderation_mode=gapgpt، rewritten_text بدنهٔ تأییدشده، full_sms جملهٔ آغاز+بدنه+لینک لغو و حداکثر۳بخش است. generated_body رمز و review_signature فقط داخلی‌اند. تأیید نهایی شامل حفظ منظور است و همان snapshot بدون AI دوباره به adapter می‌رود. تغییر بدنه، گیرنده، صاحب، قیمت، شرایط یا انقضا امضا را باطل می‌کند. کلید فعلاً خالی است و اتصال واقعی آزموده نشده است.

## حذف سقف هزینهٔ روزانه۰٫۱۰٫۱

در پروفایل هدیهٔ واقعی با flag خصوصی `PROVIDER_DAILY_BUDGET_UNLIMITED=1`، پرشدن بودجهٔ روزانه مانع OTP، پیام یا دعوت نیست. ثبت هزینه، idempotency، ماندهٔ۳هدیه، پرداخت بسته و قرارداد پاسخ سفارش حفظ شده‌اند. API عملیات `provider_budget_unlimited:true, provider_budget_limit_rial:null` می‌دهد؛ مقدار رزرو تاریخچه پاک نمی‌شود. علت‌های داخلی معتبرِ توقف پیش از provider در delivery/outbox ذخیره می‌شوند و جزئیات فنی/اعتبار در رسید عمومی پنهان می‌مانند. سفارش لغوشدهٔ قبلی بازپخش نمی‌شود.

## Synchronous local AI and administration

`rewrite_mode` and preview `moderation_mode` may be `ollama` for locally generated, independently reviewed freeform text. Both `ollama` and `gapgpt` previews retain encrypted bodies and exact signed snapshots. Legacy `ollama_curated` remains a reviewed-template snapshot type. New AI requests run synchronously, with no background job or provider fallback. Local admission is immediate; `429 ai_busy` means capacity is occupied and the caller may explicitly retry. A model timeout or uncertain review yields `503 rewrite_unavailable`; no draft is queued for later dispatch.

Staff with `core.manage_ai` may GET/POST `/api/v1/manage/ai`; writes require CSRF, `values`, `revision`, and `reason`. Editable values are `provider` (`template`, `ollama`, `gapgpt`), `ollama_model`, `gapgpt_model`, `timeout_seconds` (2–20), `parallel_requests` (1–2), `daily_limit`, and `user_daily_limit`. Endpoints and credentials remain server-owned. Selecting GapGPT requires existing credentials and positive paid-provider limits. `POST /api/v1/manage/ai/test` accepts a transient `text` of up to 280 characters, tests only the saved local model, and returns `allowed`, `message`, and `elapsed_seconds`; it never creates an SMS, preview or order. The payload never returns credentials. See [Ollama operating guide](ai-ollama.fa.md).

### Message submission trust boundary

The server is authoritative even for direct HTTP clients and modified browser code. Preview accepts only `text`, `category`, `recipient_phone`, `source_mode`, `message_tone`, and the compatibility field `payment_method` (only `credit` can create a quote); the backend computes moderation and the final snapshot. Order creation accepts only `preview_id`, `recipient_phone`, `consent`, `terms_version`, and legacy `wallet_consent` for compatibility; that field cannot authorize a new direct charge. Attempts to supply a replacement body, moderation result, price, identity or signature are rejected with `422 server_snapshot_required`. Free confirmation and demo payment accept an empty JSON object only. Editing rendered text or a JavaScript preview object cannot change the stored outgoing SMS.

AI previews bind the exact approved body, full SMS, owner, recipient, price, terms and expiry with a keyed signature. The order copies server data only; the snapshot is checked again before dispatch authorization. The real SMS worker reloads and locks the preview and verifies the order immediately before provider submission, so a change between its two transactions cancels dispatch. Missing consent in a real run, changed/expired snapshots, another owner's preview, unsigned output, raw profanity and fabricated client review flags cannot authorize an outgoing message. Changing text or recipient requires a fresh backend preview and confirmation. Both AI providers share these controls.

### GapGPT preset and output bounds

The active model since release 0.12.1 is gpt-4.1-mini. It uses Chat Completions with response_format=json_object and max_tokens=256 for each of the two stateless calls. The older Luna preset uses max_completion_tokens and reasoning_effort=none; reported reasoning tokens count within its output bound. Both incomplete choices and any failed/uncertain review are rejected without retry or fallback. No client API keys or provider-selected text overrides are accepted. The local product launcher forwards the private GapGPT environment to Python services only. See [operating guide](ai-gapgpt.fa.md).

تنظیم سراسری GapGPT در `GET/POST /api/v1/manage/limits` فیلد بولی `rewrite_daily_unlimited` دارد (پیش‌فرض `false`). مقدار `true` فقط سقف `rewrite_daily_limit` را کنار می‌گذارد؛ `rewrite_user_limit`، شمارش مصرف، مجوز مدیریت، CSRF، دلیل تغییر و کنترل revision برقرارند. با بازگشت به `false` مصرف قبلی همان روز در سقف عددی لحاظ می‌شود؛ صفر در سقف سایتِ محدود یا سقف هر حساب، بازنویسی را غیرفعال می‌کند.


## تعرفه‌ها و کارت‌به‌کارت — تغییر محلی

صفحهٔ `/pricing` و چهار بستهٔ۳/۹/۳۰/۹۰پیامی، کارت مقصد و دریافت رسید در بله/تلگرام، تأیید مستند ادمین و فعال‌سازی دستی بسته اضافه شده‌اند. زرین‌پال پس از verify مستقل خودکار فعال می‌کند. پیش‌فرض کارت خاموش و مقصد خالی است؛ شرایط پرداخت واقعی و مجوز انتشار جدا باقی‌اند. [قرارداد کامل API و راهنمای عملیات](pricing-card-payments.fa.md).


## پشتیبانی متنی — محلی

گفت‌وگوی خصوصی حساب واردشده و صندوق مشترک همهٔ ادمین‌های فعال در `/manage` ← «پشتیبانی» اضافه شد؛ نشان قرمزِ بی‌پاسخ مستقل از خواندن است، فایل مجاز نیست، متن رمز‌شده و درخواست‌ها با CSRF/مالکیت/کلید تکرار کنترل می‌شوند. نام بانک هم در تنظیمات و snapshot کارت‌به‌کارت آمده است. [مسیرها، قواعد و نگهداری](support-chat.fa.md).


## موجودی سرویس‌ها — محلی

نوار بالای مدیریت با مجوز `core.view_operations`، اعتبار کاوه‌نگار را از API رسمی به تومان و با زمان استعلام نشان می‌دهد. GapGPT تا تأیید API موجودیِ سازگار با کلید، لینک کیف پول رسمی دارد. مقدار نامعلوم صفر نمایش داده نمی‌شود. [قرارداد و محدودیت‌ها](provider-balances.fa.md).


دسته‌بندی و مدیریت پیام‌های نمونه در هر دو پنل، فعلاً در توسعهٔ محلی آماده است. [راهنمای قابلیت و API](message-examples.fa.md).
