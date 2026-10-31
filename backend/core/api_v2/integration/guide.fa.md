# راهنمای اتصال فرانت و ربات تلگرام/بله به بگم نگم

قرارداد جدید: `/api/v2`، بدون اسلش پایانی. مسیرهای فعلی `/api/v1` برای وب‌اپ
حفظ شده‌اند. این راهنما قرارداد اپلیکیشن است؛ اتصال حساب ربات، webhook و
ارسال پیام داخل پیام‌رسان هنوز باید در adapter جدا پیاده شود. هیچ ربات یا
webhook عمومی در این تغییر فعال نشده است.

## دسترسی خصوصی و تحویل موقت مستندات

متغیر بک‌اند `API_DOCUMENTATION_ENABLED` پیش‌فرض `0` است. فقط در محیطی که
مالک آن هستید مقدار `1` بگذارید. مهاجرت `0036` باید با
`python manage.py migrate` در همان محیط تنظیم‌شده اعمال شده باشد.
سپس با حساب فعال کارکنان در `/admin/` وارد
شوید؛ superuser دسترسی دارد، برای سایر کارکنان فقط مجوز
`core.view_api_documentation` را از بخش مجوزهای کاربر در ادمین بدهید.
این مجوز هیچ حق مشاهدهٔ پیام خصوصی، مدیریت یا ارسال محصولی نمی‌دهد.

| مسیر | کاربرد |
| --- | --- |
| `/api/v2/document` | Swagger UI قابل بازکردن در مرورگر |
| `/api/v2/document/openapi.json` | فایل OpenAPI قابل واردکردن به ابزار فرانت |
| `/api/v2/document/guide` | همین راهنمای فارسی |
| `/api/v2/document/client.py` | کلاینت پایتون بدون وابستگی جانبی |

صفحه، schema، راهنما، کلاینت، فونت و فایل‌های Swagger همگی همان شرط دسترسی
را دارند؛ فرد غیرمجاز و حالت خاموش هر دو `404` می‌گیرند. به کلید مخفی در
URL، مخفی‌بودن نام مسیر یا `noindex` برای کنترل دسترسی تکیه نشده است. همهٔ
پاسخ‌ها `no-store` هستند. هیچ CDN یا validator خارجی برای مشاهدهٔ schema
فراخوانی نمی‌شود. بعد از تحویل به فرانت، `API_DOCUMENTATION_ENABLED=0`
همهٔ مسیرهای مستندات را می‌بندد و API عملیاتی برقرار می‌ماند.

برای فایل آفلاین، بدون فعال‌کردن مستندات HTTP، در محیط تنظیم‌شدهٔ بک‌اند:

```sh
python manage.py export_api_schema --output /absolute/private/path/begamnagam-openapi.json
```

فایل تحویلی را در مخزن/هاست عمومی قرار ندهید. Swagger از نشست همان مرورگر
برای Try it out استفاده می‌کند؛ برای درخواست‌های محصولی باید حساب دارای
Account تلفنی باشد. ورود OTP یا خروج در Swagger ممکن است نشست کارکنان را
عوض کند و دسترسی مستندات را ببندد. بهتر است گردش کامل محصول را با کلاینت و
نشست جدا بررسی کنید. مستندات خصوصی بودن، API محصول را به API ادمین تبدیل
نمی‌کند؛ endpointهای مدیریت در این قرارداد ربات وجود ندارند.

## قرارداد مشترک HTTP

- هر درخواست تغییردهنده: `Content-Type: application/json`، cookie jar همان
  کاربر، `X-CSRFToken` جاری و بدنهٔ JSON؛ بدنهٔ خالی یعنی `{}`، حتی برای
  `DELETE /session`. CSRF برای ربات هم حذف نشده است.
- ابتدا `GET /session` یا `GET /bootstrap` را بزنید. cookieها را نگه دارید و
  `csrf_token` پاسخ را بخوانید. پس از ورود، توکن تازهٔ پاسخ را جایگزین کنید.
  نشست با خروج یا انقضا بی‌اعتبار می‌شود؛ پاسخ `401` نیاز به ورود دوباره دارد.
- مرورگر هم‌مبدأ: `credentials: 'same-origin'`. فرانت Next مسیر v2 را هم به
  Django پروکسی می‌کند. برای فرانت مستقل، از reverse proxy هم‌مبدأ استفاده
  کنید؛ CORS عمومی و ارسال cookie به origin دلخواه اضافه نشده است.
- ساخت چالش OTP، پیش‌نمایش و نشست `201` می‌دهد؛ سایر عملیات موفق `200`،
  از جمله تکرار درخواست با کلید قبلی. موفقیت ثبت پیام با موفقیت تحویل فرق دارد.
- بدنه حداکثر `8192` بایت؛ ورودی‌های اضافی/نوع اشتباه `422`. شماره و OTP
  رشته‌اند، از جمله صفر ابتدایی؛ مبلغ و تعداد عدد JSON صحیح‌اند، نه float،
  Boolean یا رشتهٔ عددی. ماندهٔ کیف پول رشتهٔ عددی است تا دقت عدد بزرگ حفظ شود.
- ارقام فارسی/عربیِ ورودی انسانی تازه در سرور به ASCII تبدیل می‌شوند.
  UUID، token، signature و snapshotهای قبلی را تغییر ندهید. نمایش UI فارسی
  باشد؛ مقادیر ساختاری JSON را فارسی ذخیره نکنید.
- `X-Request-ID` را برای پیگیری خطا نگه دارید. شمارهٔ کامل، OTP، cookie، متن
  خصوصی، توکن گیرنده و پاسخ‌های دارای این داده‌ها را در لاگ ثبت نکنید.
- endpoint حدس‌زدن حساب دیگر، تغییر آزاد اعتبار، ارسال متن خام، ارسال گروهی
  یا استعلام وضعیت دریافت مقصد وجود ندارد. تغییر محیط یا adapter مجوز
  فعال‌سازی پرداخت/ارسال واقعی تازه نیست.

## گام ۱ — ساخت نشست مستقل هر کاربر ربات

کلید نگهداری state ربات را از **هویت تأییدشدهٔ update پیام‌رسان** بسازید:
`(platform, bot_id, from_user_id)`؛ مثلاً `telegram` و `bale` namespace جدا
دارند. شناسهٔ کاربر را از متن پیام، callback_data یا شمارهٔ ورودی نگیرید.
ورود فقط در چت خصوصی باشد. هر هویت، cookie jar و قفل اجرای جدا دارد؛ یک
کلاینت واردشدهٔ سراسری همهٔ کاربران را صاحب همان حساب می‌کند.

`GET /bootstrap` اطلاعات شروع را یکجا برمی‌گرداند:

```json
{
  "session": {"authenticated": false, "csrf_token": "...", "recent_auth": false,
    "expires_in": 604800, "otp_length": 4, "demo_mode": false, "otp_is_real": true},
  "catalog": {"categories": [], "examples": [], "message_tones": [],
    "default_message_tone": "polite", "rewrite_mode": "template", "freeform_enabled": false,
    "message_packages": [], "package_checkout_enabled": false, "payment_options": {},
    "terms_version": "...", "invitation_policy": {}, "support_contact": "..."}
}
```

این نمونه شکل پاسخ است؛ فهرست واقعی را از سرور بگیرید. پس از ورود، `me` و
`credits` هم اضافه می‌شوند. شمارهٔ کامل حساب برنمی‌گردد. `demo_mode` و
`otp_is_real` مستقل‌اند: ممکن است OTP واقعی و پیام مقصد آزمایشی باشد.
در اجرای کاربر واقعی، OTP و پیام مقصد باید از provider واقعی محیط بیایند؛
به debug_code، دادهٔ ساختگی یا نتیجهٔ demo به‌عنوان موفقیت واقعی رجوع نکنید.
کلاینت نمونه به‌صورت پیش‌فرض OTP غیرواقعی و ارسال در محیط demo را رد می‌کند.

## گام ۲ — دریافت شماره و ورود با OTP

از کاربر شمارهٔ خودش را بخواهید. در تلگرام می‌توان در چت خصوصی از دکمهٔ
`request_contact` استفاده کرد؛ contact متعلق به کاربر دیگر را نپذیرید و در
صورت وجود `contact.user_id` آن را با فرستنده مقایسه کنید. دریافت contact
به‌تنهایی مجوز ورود این اپلیکیشن نیست؛ OTP همچنان لازم است.

برای بله، لایهٔ دریافت شماره را مطابق مستندات رسمی جاری پیام‌رسان پیاده
کنید؛ ورودی متنی شماره هم توسط همین API پشتیبانی می‌شود. یکسان‌بودن تمام
فیلدها، محدودیت‌ها و تضمین‌های webhook تلگرام و بله فرض نشده است.

```http
POST /api/v2/auth/otp-challenges
Content-Type: application/json
X-CSRFToken: <current>
Cookie: <same user jar>

{"phone":"09123456789"}
```

پاسخ: `challenge_id`, `expires_in`, `demo_mode` و در سرویس واقعی
`delivery_status: accepted|unknown`. `unknown` یعنی احتمال رسیدن همان کد
وجود دارد؛ موفقیت قطعی نمایش ندهید و خودکار کد تازه نفرستید. چالش به همین
نشست متصل است. کد را در چت خصوصی دریافت کرده و فقط برای تأیید بفرستید؛ در
state بلندمدت/لاگ نگه ندارید.

```http
POST /api/v2/auth/sessions

{"challenge_id":"<uuid>","code":"0123"}
```

از `csrf_token` **جدید** پاسخ برای درخواست بعدی استفاده کنید. کد نمونه است؛
طول را از `session.otp_length` بخوانید، کد واقعی را از کاربر بگیرید. خطای
`invalid_otp` را به کاربر نشان دهید؛ ارسال contact یا شناسهٔ تلگرام راه میانبر
ورود نیست. درخواست OTP مجدد فقط با اقدام صریح و رعایت مهلت/سقف‌ها انجام شود.

## گام ۳ — getMe، اعتبار و منوی اصلی

`GET /me` همان کاربرد getMe را به‌شکل REST دارد: `id` حساب، `phone_masked`,
`suspended`, `deletion_requested_at`, `recent_auth`. `GET /me/credits`:

```json
{"gift_remaining":3,"gift_total":3,"invitation_rewards_total":0,
 "purchased_remaining":0,"total_remaining":3,"wallet_balance_toman":"0","environment":"live"}
```

هدیه و اعتبار بسته بین سایت و هر دو ربات مشترک‌اند؛ ورود دوباره یا اتصال
پیام‌رسان دیگر هدیهٔ تازه نمی‌دهد. منوی پیشنهادی: «ارسال پیام»، «اعتبار و خرید
بسته»، «سوابق»، «دعوت دوستان»، «تنظیم دریافت»، «پشتیبانی»، «خروج».
`GET /session` برای بررسی سبک نشست کافی است؛ برای هر دکمه bootstrap نگیرید.

## گام ۴ — دسته‌بندی، نمونه و لحن

`GET /catalog` همهٔ داده‌های قابل انتخاب و capabilityها را می‌دهد.
`GET /categories` دسته‌های دارای نمونهٔ فعال و
`GET /categories/{category_id}/examples` نمونه‌های همان دسته را می‌دهد.
`category_id` عدد یکتای دسته است؛ `example.id` عدد یکتای نمونه و
`example.topic` شناسهٔ موضوع برای فیلد `category` پیش‌نمایش است. این‌ها را با
هم جابه‌جا نکنید. مقدار `text` همان نمونه را با `source_mode:suggestion`
بفرستید. نمونه، متن نهایی تأییدشدهٔ پیامک محسوب نمی‌شود.

لحن را فقط از `catalog.message_tones` فعال انتخاب کنید؛ شناسه‌ها
`polite|firm|angry` هستند. اگر لحن عوض/غیرفعال شد، catalog را تازه بگیرید.
متن آزاد فقط با `freeform_enabled:true` و `source_mode:freeform` مجاز است؛
نبود سرویس/کلید یا شکست بررسی مستقل، نتیجهٔ موفق ساختگی نمی‌سازد.

## گام ۵ — دریافت شمارهٔ مقصد

این شماره را **جدا از شمارهٔ ورود** و با برچسب روشن از کاربر بگیرید. سپس:

```http
POST /api/v2/recipients/validations

{"phone":"+989901234567"}
```

```json
{"valid":true,"phone":"09901234567","phone_masked":"099•••••567"}
```

پاسخ فقط شماره‌ای است که همین کاربر وارد کرده و قالب/خودگیرندگی آن بررسی
شده است؛ اعتبار تحویل، عضویت یا رضایت مقصد را تضمین نمی‌کند. شمارهٔ کامل
را فقط در state کوتاه‌عمر رمز‌شده نگه دارید؛ به callback_data یا URL نگذارید.
بعد از تغییر شماره، پیش‌نمایش و رضایت قبلی را پاک کنید.

## گام ۶ — آماده‌سازی و نمایش دقیق پیش‌نمایش

نمونهٔ آماده (مقادیر category و text را از example انتخاب‌شده بردارید):

```http
POST /api/v2/message-previews

{"recipient_phone":"09901234567","source_mode":"suggestion",
 "category":"appreciation","text":"از مهربانی و کمکی که به من کردی ممنونم",
 "message_tone":"polite"}
```

متن آزاد:

```json
{"recipient_phone":"09901234567","source_mode":"freeform",
 "text":"متن اولیهٔ کاربر","message_tone":"polite"}
```

پاسخ `preview_id`, `full_sms`, `rewritten_text`, `sms_segments`, `expires_at`,
`terms_version`, `price_toman`, `is_free` دارد. **full_sms کامل**، مقصد ماسک‌شده
و نوع اعتبار مصرفی را قبل از تأیید کاربر نشان دهید. `is_free:false` یعنی
اعتبار بسته لازم است؛ قیمت صفر مجوز ارسال بدون اعتبار نیست.

`GET /message-previews/{preview_id}` همان snapshot منقضی‌نشدهٔ صاحب حساب را
بدون تماس AI دوباره می‌دهد؛ پاسخ منقضی409و منبع حساب دیگر404است.

اگر `422` دارای `error.details.alternatives` بود، پیشنهادهای مستقل را به
انتخاب کاربر بگذارید. فقط بعد از انتخاب صریح، این بدنه را بفرستید:

```json
{"recipient_phone":"09901234567","source_mode":"reviewed_alternative",
 "alternative_token":"<selected token>","message_tone":"polite"}
```

در این حالت text/category نفرستید. پیشنهاد به همان حساب، نشست، گیرنده و
لحن وابسته و زمان‌دار است؛ تغییر مقصد/نشست یا انقضا پیش‌نمایش تازه لازم دارد.
مدل یا کلاینت هرگز حکم بررسی و متن نهایی را در درخواست ارسال تعیین نمی‌کنند.

## گام ۷ — رزرو اعتبار و ارسال بدون تکرار

پس از دکمهٔ صریح «تأیید و ارسال»، یک UUID تولید و **پیش از درخواست** در state
ماندگار همین اقدام ذخیره کنید. با ویرایش صفحه یا دریافت update تکراری کلید
تازه نسازید. همهٔ درخواست‌های یک کاربر باید در ربات با قفل/صف ترتیبی اجرا شوند.

```http
POST /api/v2/messages
Idempotency-Key: <stored uuid>

{"preview_id":"<preview uuid>","recipient_phone":"09901234567",
 "consent":true,"terms_version":"<from preview>"}
```

پاسخ `id` و وضعیت `awaiting_payment` می‌دهد؛ این نام برای سازگاری هسته حفظ
شده و در مسیر اعتبار یعنی **رزرو شده و منتظر تأیید ارسال**. پول تازه دریافت
نمی‌شود؛ یک هدیه یا واحد بسته اتمیک رزرو شده است. بلافاصله `id` را ذخیره کنید:

```http
PUT /api/v2/messages/{id}/submission

{}
```

بدنهٔ دیگری شامل متن/قیمت پذیرفته نمی‌شود. تأیید روی همان id تکرارپذیر است
و outbox/تحویل دوباره نمی‌سازد. اگر پاسخ رزرو گم شد، **همان بدنه و همان کلید**
POST را تکرار کنید؛ اگر پاسخ تأیید گم شد، GET همان پیام را بگیرید یا PUT همان
id را تکرار کنید. دوبارکلیک و update تکراری نباید سفارش تازه بسازند.

پیش‌نمایش/رزرو منقضی، شروط عوض‌شده یا اعتبار تغییرکرده به نمایش پیش‌نمایش و
رضایت تازه نیاز دارند. `credit_required` یعنی به منوی خرید بروید؛ تلاشی برای
فعال‌کردن درگاه یا مصرف هدیهٔ ساختگی نکنید. رزرو رهاشده با روال انقضای فعلی
سرور و worker آزاد می‌شود؛ endpoint لغو/ارسال دوبارهٔ پیام وجود ندارد.

## گام ۸ — رسید و سوابق

`GET /messages/{id}` فقط پیام متعلق به همین حساب را نشان می‌دهد. پس از ارسال
با فاصله‌های پیشنهادی ۲، ۵، ۱۰ و ۳۰ ثانیه وضعیت را دریافت کنید؛ بعد از بازهٔ
انتظار ربات، نتیجه را «در حال بررسی» نگه دارید و دکمهٔ دریافت رسید بگذارید.
حلقهٔ polling نامحدود یا درخواست در هر update نسازید. اعلان تغییر وضعیت را
در state ربات deduplicate کنید؛ callback تحویل به ربات در این نسخه وجود ندارد.

| status | معنی و رفتار ربات |
| --- | --- |
| `awaiting_payment` | رزرو منتظر تأیید؛ همان submission را ادامه دهید |
| `queued` | در صف؛ منتظر worker بمانید |
| `accepted` | سرویس پیامک پذیرفته؛ رسید تحویل قطعی نیست |
| `delivered` | رسید تحویل واقعی ثبت شده |
| `unknown` | نتیجه نامعلوم؛ خودکار دوباره ارسال نکنید |
| `failed` / `cancelled` | ناموفق/لغوشده؛ دلیل عمومی و وضعیت اعتبار را تازه بخوانید |
| `delivered_demo` | فقط شبیه‌سازی؛ به کاربر واقعی «تحویل شد» نگویید |

`status_reason` توضیح عمومی است؛ علت خصوصی قطع دریافت/حساب مقصد از پاسخ
استنباط نشود. `financial_status` وضعیت رزرو/برگشت اعتبار را جدا می‌دهد.
برای نمایش معمول، text شامل SMS نهایی است؛ متن اولیهٔ خصوصی برنمی‌گردد.

سوابق: `GET /messages?limit=20` و در صفحهٔ بعد
`GET /messages?limit=20&cursor=<next_cursor>`. فیلتر اختیاری `status` دارد.
cursor امضاشده، مخصوص حساب/منبع/فیلتر و تا ۷ روز معتبر است؛ آن را تغییر ندهید
و با فیلتر دیگری استفاده نکنید. `has_more:false` پایان فهرست است. پیش‌فرض۲۰،
حداکثر۵۰؛ تعداد کل محاسبه نمی‌شود. روی کارت هر پیام دکمهٔ دریافت رسید بگذارید.

## گام ۹ — خرید بسته و کیف پول

`GET /message-packages`، `GET /wallet` و `GET /me/credits` را بخوانید. نمایش
دکمهٔ خرید به `package_checkout_enabled` و روش‌های فعال وابسته باشد؛ کلیدها
به‌تنهایی مجوز پرداخت نیستند. مبلغ/تعداد فقط از package snapshot سرور می‌آید.

```http
POST /api/v2/credit-purchases
Idempotency-Key: <stored uuid>

{"package_id":1,"package_revision":0,"payment_method":"gateway",
 "wallet_consent":true,"wallet_terms_version":"<catalog.payment_options.wallet_terms_version>"}
```

روش‌ها `gateway|wallet|card`؛ شناسه و revision را تازه از فهرست بگیرید. در
درگاه، `redirect_url` را به‌صورت دکمهٔ بازکردن مرورگر بفرستید. `Status=OK`،
اسکرین‌شات یا برگشت کاربر اثبات پرداخت نیست؛ `GET /credit-purchases/{id}`
را بخوانید تا وضعیت `credited` سرور ثبت شود، سپس اعتبار را تازه بگیرید.
callback فعلی `/api/v1/payments/return/zarinpal` و verify مستقل سرور برقرارند؛
مسیر callback ربات جایگزین آن نیست. timeout/unknown کلید خرید جدید نمی‌سازد.

در کارت‌به‌کارت، کارت و `receipt_channels` از snapshot خرید می‌آیند؛ رسید
را همان‌جا بفرستید، سپس
`PUT /credit-purchases/{id}/receipt` با
`{"receipt_sent":true,"reference":"..."}`. این endpoint آپلود فایل نیست و
اعتبار خودکار نمی‌دهد؛ تأیید واقعی ادمین لازم است. لغو خرید کارتِ باز:
`DELETE /credit-purchases/{id}` با `{}`؛ پرداخت درگاه را لغو نمی‌کند.

شارژ کیف پول: `POST /wallet/topups` با کلید UUID و
`{"amount_toman":10000,"consent":true,"terms_version":"wallet-credit-v1"}`؛
شرایط جاری را از سرور بگیرید، سپس `GET /wallet/topups/{id}`. مانده غیرقابل
برداشت است. تاریخچه‌ها صفحه‌بندی دارند: `/credit-purchases`, `/wallet/topups`,
`/wallet/entries` و `/me/credit-entries`. دفتر credit فقط واحد بسته را ثبت
می‌کند؛ هدیه/جایزه در خلاصهٔ اعتبار است. در پروفایل هدیهٔ واقعی فعلی، پرداخت
پولی همچنان بسته است؛ این قابلیت آن را فعال نمی‌کند.

## گام ۱۰ — دعوت دوستان

شرایط جاری از `catalog.invitation_policy`. پس از رضایت برای دعوت آشنای مایل:
`POST /invitations` با کلید UUID و
`{"phone":"09...","consent":true,"consent_version":"invitations-v1"}`.
فهرست `/invitations` و جزئیات `/invitations/{id}` فقط متعلق به دعوت‌کننده‌اند.
`GET /invitations/summary` تعداد دعوت، ثبت‌نام، اعتبار جایزه و ماندهٔ سهمیهٔ
درخواست دعوت را می‌دهد؛ policy جاری در catalog است.
این فرایند صریح، تنها استثنای گزارش عضویت/ثبت‌نام مقصد است؛ وضعیت قطع دریافت
و هویت دعوت‌کنندهٔ دیگر هرگز برنمی‌گردد. ثبت‌نام موفق می‌تواند۳اعتبار جایزه
بدهد و همچنان۳هدیهٔ اولیهٔ دعوت‌شده مستقل است.

ارسال مجدد فقط با `can_resend:true` و اقدام تازهٔ کاربر:
`POST /invitations/{id}/reminders` با کلید UUID جدا و
`{"consent":true,"consent_version":"invitations-v1"}`. همان اقدام را با همان
کلید retry کنید. `null` در سقف/مانده یعنی سقف متناظر خاموش، نه صفر اعتبار.
فاصله‌ها، pending/unknown، قطع دریافت و محدودیت حساب همچنان اعمال می‌شوند.

## گام ۱۱ — تنظیم دریافت، پشتیبانی و خروج

- `GET /me/preferences` و `PATCH /me/preferences` با `{"blocked":true|false}`
  فقط شمارهٔ تأییدشدهٔ خود حساب را تغییر می‌دهند. برای فعال‌کردن دوباره، OTP
  کمتر از۵دقیقه لازم است؛ مقصدی در این درخواست پذیرفته نمی‌شود.
- `GET /support` تعداد خوانده‌نشده و وضعیت حضور پشتیبانی را می‌دهد.
  `POST /support/messages` با `{"text":"..."}` و کلید UUID، پشتیبانی خصوصی
  متنی می‌سازد. فایل مجاز نیست. `GET /support/messages` حداکثر۵۰پیام و
  `before_cursor` می‌دهد؛ برای قدیمی‌ترها `?before=<integer>` بفرستید.
  پس از نمایش، `PUT /support/read-marker` با
  `{"through_sequence":<last displayed sequence>}`؛ خواندن با پاسخ‌دادن فرق دارد.
- `POST /me/deletion-requests` با `{}` و OTP کمتر از۵دقیقه، درخواست حذف داده
  می‌سازد و ارسال را فوراً معلق می‌کند؛ اجرای redaction طبق روال۳۰روزه است.
- `DELETE /session` با `{}`، نشست همین ربات را خارج می‌کند. cookieها، CSRF و
  state متن/شمارهٔ آن کاربر را پاک کنید؛ سایر کاربران را دست نزنید.

گیرنده با لینک خصوصی پیام خودش نیز می‌تواند اقدام کند:
`POST /recipient-capabilities/inspections` با `{"token":"..."}`،
`PUT /recipient-capabilities/preference` برای قطع دریافت با همان بدنه، و
`POST /recipient-reports` با `token, reason, details?`. دلیل‌ها
`unwanted|harassment|wrong_number|other`؛ گزارش هم دریافت را قطع می‌کند.
token در JSON است، نه URL/query؛ از لینک دیگران جمع‌آوری نکنید. این مسیرها
ورود لازم ندارند، اما نشست CSRF دارند و هویت فرستنده را افشا نمی‌کنند.

## رسیدگی به خطا و محدودیت

ساختار خطا:

```json
{"error":{"code":"credit_required","message":"..."}}
```

| HTTP / کد | اقدام پیشنهادی |
| --- | --- |
| `400 invalid_otp` | تصحیح کد/ورود مجدد؛ کد را کوتاه یا حدس نزنید |
| `401 authentication_required` | فقط همین هویت را دوباره وارد کنید |
| `403 csrf_failed` | GET /session، توکن تازه و ادامهٔ همان اقدام با همان کلید |
| `403 reauthentication_required` | OTP تازه برای همان شماره، سپس اقدام صریح |
| `404 not_found` | منبع متعلق به حساب نیست یا وجود ندارد؛ اطلاعات دیگری جست‌وجو نکنید |
| `409 preview_expired/quote_recipient_changed` | پیش‌نمایش و رضایت تازه |
| `409 credit_required/free_quota_changed` | اعتبار را تازه و تصمیم کاربر را دوباره بگیرید |
| `409 recipient_unavailable` | فقط توضیح عمومی؛ علت خصوصی مقصد را حدس نزنید |
| `409 idempotency_conflict` | خطای state ربات؛ کلید قبلی را برای دادهٔ جدید بازاستفاده نکنید |
| `409 payment_disabled/freeform_unavailable` | منوی قابلیت‌ها را تازه کنید؛ موفقیت جایگزین نسازید |
| `422 invalid_input/invalid_query/invalid_cursor` | ورودی/صفحه را اصلاح کنید؛ خطای محتوایی ممکن است پیشنهاد داشته باشد |
| `429 rate_limited/daily_limit` | کار را متوقف و به کاربر زمان انتظار نشان دهید؛ retry تند ممنوع |
| `503 otp_unavailable/rewrite_unavailable/service_unavailable` | شکست واقعی؛ state/کلید اقدام را حفظ و با سیاست backoff ادامه دهید |

هدر `Retry-After` در همهٔ محدودیت‌های فعلی هسته تضمین نشده است؛ عدد دلخواه
را به‌عنوان مهلت قطعی سرور نشان ندهید. سقف عمومی v2 برای هر حساب۳۰۰درخواست
در دقیقه است و سقف‌های اختصاصی OTP، پیام، دعوت، پشتیبانی، AI و هزینه نیز
جدا اعمال می‌شوند. همهٔ کاربران ربات IP خروجی مشترک دارند؛ هدر
`X-Forwarded-For` ساختگی نفرستید و IP ورودی webhook را هویت محصول حساب نکنید.
محدودیت‌های IP فعلی، از جمله دعوت۱۰۰درخواست در روز، همچنان برقرارند؛ برای
ترافیک واقعی بالاتر، تغییر مستند policy با تأیید مالک محیط لازم است.

## الگوی adapter برای تلگرام و بله

state machine مشترک پیشنهادی:

```text
START -> PHONE -> OTP -> MENU
MENU -> CATEGORY/EXAMPLE or FREEFORM -> DESTINATION -> TONE -> PREVIEW
PREVIEW -> explicit CONFIRM -> RESERVE -> SUBMISSION -> RECEIPT -> MENU
```

در state سرور: namespace هویت، cookie jar، CSRF، challenge_id/انقضا،
example/topic، لحن، مقصد رمز‌شده، preview/انقضا، کلید اقدام و message_id را
نگه دارید. متن خام و OTP را بعد از نیاز پاک کنید. cookieها bearer credential
هستند؛ رمز‌شده با TTL نشست نگهداری شوند. کلید ربات و کلید provider را به
فرانت یا callback_data ندهید. دادهٔ callback فقط شناسهٔ کوتاه رکورد state
خود سرور باشد؛ متعلق‌بودن آن به کاربر/update را پیش از هر درخواست بررسی کنید.

updateها را با `(platform, bot_id, update_id)` در store ماندگار deduplicate
کنید. رویداد پردازش‌شده یا در حال پردازش، سفارش/OTP تازه نمی‌سازد. webhook
باید سریع تأیید شود و آماده‌سازی AI را بیرون چرخهٔ پاسخ webhook اجرا کنید؛
خود API پیش‌نمایش همگام است و ممکن است تا مهلت فعلی AI طول بکشد. ابتدا callback
دکمه را در پیام‌رسان acknowledge کنید و وضعیت انتظار نشان دهید. درخواست‌های
یک هویت را هم‌زمان روی یک cookie jar اجرا نکنید؛ کاربران مستقل می‌توانند
به‌صورت محدود هم‌زمان پردازش شوند.

در تلگرام، webhook را با `secret_token` ثبت و هدر
`X-Telegram-Bot-Api-Secret-Token` را با مقایسهٔ ثابت‌زمان بررسی کنید. برای بله
سازوکار اصالت webhook را از مستندات/امکانات رسمی همان محیط تأیید کنید؛ هدر
تلگرام را برای بله فرض نکنید. این نسخه به هیچ webhook عمومی اعتماد یا مسیر
بی‌احراز هویت برای ارسال پیام اضافه نمی‌کند.

در adapter هر پیام‌رسان، فقط دریافت update، هویت فرستنده، دریافت شماره/متن،
ساخت دکمه و ارسال پاسخ فرق می‌کند. لایهٔ HTTP اپلیکیشن برای هر دو همین است.
این راهنما، اتصال زنده به تلگرام یا بله را آزموده یا فعال اعلام نمی‌کند.

## استفاده از کلاینت نمونه

فایل `/api/v2/document/client.py` را در پروژهٔ ربات وارد کنید؛ Python standard
library کافی است. فراخوانی شبکه در import ندارد. نمونهٔ مراحلِ handlerها:

```python
import uuid
from client import BotAPI

# فقط یک هویت معتبر از update؛ این متغیر برای همهٔ کاربران مشترک نباشد.
api = BotAPI('https://begamnagam.ir/api/v2')
startup = api.bootstrap()
challenge = api.request_otp(phone_from_private_chat)
# بعد از پیام بعدی همین کاربر:
api.verify_otp(challenge['challenge_id'], otp_from_user)
me, credits = api.getme(), api.credits()
catalog = api.call('GET', '/catalog')
example = selected_example_from_catalog
destination = api.validate_recipient(destination_from_user)['phone']
preview = api.preview(destination, source_mode='suggestion',
                      category=example['topic'], text=example['text'])
# full_sms را نمایش دهید؛ فقط پس از دکمهٔ صریح کاربر ادامه دهید.
stored_action_key = str(uuid.uuid4())  # پیش از شبکه در store ماندگار ذخیره شود.
message = api.reserve_message(preview, destination, key=stored_action_key,
                              consent=explicit_user_confirmation)
# message.id را ذخیره کنید؛ پس از timeout کلید تازه نسازید.
api.submit_message(message['id'])
receipt = api.get_message(message['id'])
```

کد، نمونهٔ چند handler متوالی است و متغیرهای ورودی باید از state معتبر
تأمین شوند؛ فایل آمادهٔ اجرای bot نیست. در handler ناهمگام، فراخوانی همگام را
داخل `await asyncio.to_thread(...)` و قفل همان هویت قرار دهید تا event loop
متوقف نشود. نمونهٔ کلاینت عمداً retry/ارسال خودکار ندارد. `APIResponseError`
شامل `status`, `code`, `payload` و `TransportError` نشانهٔ نتیجهٔ نامعلوم شبکه
است. وضعیت unknown را موفق فرض نکنید.

## معیار تحویل به پیاده‌ساز ربات

ورود واقعی با cookie jar جدا، رد کد/چالش کاربر دیگر، چرخش CSRF، منوی اعتبار
مشترک، انتخاب نمونه و لحن، تغییر مقصد و ابطال preview، رضایت صریح، تکرار
update و timeout بدون دو بار مصرف، تفکیک accepted/delivered/unknown، سوابق
چندصفحه‌ای، دعوت و دریافت جایزه، خرید خاموش/فعال مطابق محیط، پشتیبانی و خروج
را بررسی کنید. پرداخت و پیام واقعی تازه برای تست به مجوز محیط و هزینه نیاز
دارند؛ آزمون خودکار این مخزن از دیتابیس جدا و providerهای mock استفاده می‌کند.

مراجع رسمی: [Django sessions](https://docs.djangoproject.com/en/5.2/topics/http/sessions/)،
[CSRF](https://docs.djangoproject.com/en/5.2/ref/csrf/)،
[OpenAPI](https://spec.openapis.org/oas/v3.0.3.html)،
[Swagger UI](https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/)،
[Telegram Bot API](https://core.telegram.org/bots/api)،
[Bale Bot API](https://docs.bale.ai/).
Context7 MCP در نشست پیاده‌سازی در دسترس نبود؛ منابع رسمی Django/Swagger/
OpenAPI/Telegram بررسی شدند. سایت رسمی بله در این نشست timeout داد؛ بنابراین
API اختصاصی یا تضمین امنیتی تأییدنشده‌ای برای بله در کد adapter اختراع نشده است.
