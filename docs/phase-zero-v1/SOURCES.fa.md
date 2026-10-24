# منابع، روش و حدود تحقیق

شناسه: BN-SRC-001 | تاریخ دسترسی: ۲۴ اکتبر ۲۰۲۶

## ۱. روش

مبنای نیازمندی، بسته محلی پروپوزال ۰٫۲ و آخرین دستور کارفرماست. بررسی نمونه، خواندن source/config و docs/verification.md بود؛ گزارش قبلی شاهد تاریخی است. اسناد جدید تحلیل و پیشنهادند و از code یا مستند فروشنده برای خود مجوز اجرا تولید نمی‌کنند.

طبق AGENTS.md، ابتدا Context7 resolve-library-id برای Django، Next.js و Go تلاش شد؛ پاسخ اتمام سهمیه ماهانه داد و library ID معتبر دریافت نشد، بنابراین query-docs قابل ادامه نبود. این محدودیت پیش از رجوع به منابع رسمی گزارش شد. اطلاعات API/پشتیبانی از منابع رسمی زیر گرفته شد؛ APIهای برنامه در DATA-API طرح خود پروژه‌اند و نقل syntax پیاده‌سازی کتابخانه نیستند.

راهنمای محلی UI/UX برای مرور اصول فرم موبایل و focus استفاده شد. نتیجه، وایرفریم مستندی است؛ هیچ خروجی UI اجرایی تولید نشده است. focus-not-obscured enhanced با AA یکسان معرفی نشده؛ هدف ارزیابی تمام معیارهای قابل اعمال WCAG2.2AA است.

## ۲. دفتر منابع رسمی

| منبع | استفاده در بسته | نتیجه دسترسی/محدودیت |
| --- | --- | --- |
| [Django downloads/support](https://www.djangoproject.com/download/) | ADR-01، پشتیبانی شاخه5.2 | جدول رسمی قابل خواندن؛ نسخه نصب‌شده را صرفاً از repository گزارش کردیم |
| [Go documentation](https://go.dev/doc/) | مقایسه گزینه بک‌اند | مرجع رسمی؛ benchmark دو زبان انجام نشد |
| [Next.js PWA guide](https://nextjs.org/docs/app/guides/progressive-web-apps) | ADR-04 و معیارهای PWA | قابل خواندن؛ راهنما جای شواهد دستگاه نیست |
| [MDN installable PWA](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable) | نصب و fallback پلتفرم | قابل خواندن؛ حداقل مرورگر با کل تعهد پروژه فرق دارد |
| [MDN Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers) | چرخه SW، cache و update | قابل خواندن؛ نمونه کد آن در برنامه اعمال نشد |
| [WCAG2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/) | هدف AA در UX/MF | مرجع کامل معیارهای قابل اعمال، بدون ادعای انطباق فعلی |
| [Web Vitals](https://web.dev/articles/vitals) | اهداف عملکرد و تفکیک lab/field | قابل خواندن؛ داده میدانی این محصول وجود ندارد |
| [Ollama Generate API](https://docs.ollama.com/api/generate) | خروجی ساختاری، انتخاب‌گر محدود | مستند قابل خواندن؛ مدل نصب/اجرا/benchmark نشد |
| [کاوه‌نگار REST](https://kavenegar.com/rest.html) | localid/استعلام، واحد cost و بخش فارسی | خوانده شد؛ contract test و ارسال انجام نشد |
| [کاوه‌نگار pricing](https://kavenegar.com/pricing.html) | قیمت پلن و تفکیک از هزینه پیام | قابل خواندن؛ بعضی جزئیات صفحه یکدست نیست؛ تعرفه نهایی/مجوز محتوا نامعلوم |
| [SMS.ir](https://sms.ir/) | گزینه جایگزین SMS | timeout؛ REST/Swagger عمومی نیز در ابزار باز نشد؛ قابلیت/تعرفه تأیید نشده |
| [زرین‌پال overview](https://www.zarinpal.com/docs/paymentGateway/) | اجزای درگاه و استعلام | مستند قابل خواندن؛ وضعیت حساب/قرارداد ما معلوم نیست |
| [زرین‌پال sandbox](https://www.zarinpal.com/docs/paymentGateway/sandBox) | وجود مسیر آزمایشی | خوانده شد؛ هیچ درخواست sandbox ارسال نشد |
| [زرین‌پال currency](https://www.zarinpal.com/docs/paymentGateway/moreFeatures/currency) | صراحت واحد IRT/IRR | خوانده شد؛ مبلغ سفارش باید مستقل بررسی شود |
| [زرین‌پال reverse](https://www.zarinpal.com/docs/paymentGateway/moreFeatures/reverse) | محدودیت۳۰دقیقه و نیاز IP | خوانده شد؛ refund خارج این پنجره قطعی نشده |
| [زیبال pricing](https://zibal.ir/pricing) | نرخ/سقف نمایش‌داده‌شده و ابهام مثال محاسبه‌گر | متن عمومی خوانده شد؛ formula حداقل خرید کوچک استنتاج نشد |
| [راهنمای کارمزد زیبال](https://help.zibal.ir/article/payment-fees-guide/) | شیوه کسر هزینه | قابل خواندن؛ API/قرارداد refund تأیید نشده |
| [زیبال API](https://help.zibal.ir/ipg/) | پیگیری مستندات فنی | فقط پوسته «در حال بارگذاری» در خواندن متنی؛ docs.zibal.ir هم باز نشد |
| [لیارا pricing](https://liara.ir/pricing/) | هزینه ثابت AI/توکن و لاگ | صفحه اصلی قابل خواندن؛ قیمت mirror/جست‌وجوی قدیمی مبنا نیست |

اطلاعات قیمت، قابلیت و قرارداد تغییر می‌کنند. این‌ها مشاهده عمومی در تاریخ بالا هستند؛ تعرفه معتبر حساب، اجازه محتوای ناشناس، تعهد تحویل، حداقل مبلغ و refund باید پیش از اتصال واقعی دوباره تأیید شوند. شکست دسترسی ابزار، شاهد نبود قابلیت سرویس نیست.

## ۳. تفکیک واقعیت و پیشنهاد

- واقعیت مشاهده‌شده کد: manifest فعلی، template-only، وضعیت demo، مدل‌ها و مسیرهای موجود؛ شاهد در audit.
- واقعیت مستندی: محتوای صفحات رسمی با محدودیت ذکرشده؛ مجوز تجاری ما از آن نتیجه نمی‌شود.
- پیشنهاد محصول: ساعت، سهمیه، retention، بازپرداخت پایلوت، قیمت نمونه، بودجه، بار و معماری؛ همگی منتظر تصمیم کارفرما.
- ناشناخته باقی‌مانده: قرارداد ارائه‌دهندگان، قیمت واقعی هر بخش، حداقل/کف درگاه، بازپرداخت دیرهنگام، کیفیت/هزینه مدل واقعی و ظرفیت روی منابع نهایی.

هیچ ادعای حقوقی درباره مجازبودن ارسال به افراد غیرعضو، دوره قانونی نگهداری مالی یا معافیت مالیاتی نشده است. مدتی که برای داده مالی پیشنهاد شده فرض برنامه‌ریزی است؛ الزام معتبر پیش از استفاده واقعی باید تعیین شود.
