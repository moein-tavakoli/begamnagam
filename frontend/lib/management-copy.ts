// Presentation only. Stored codes and API payloads remain canonical.
const explanations: Record<string, string> = {
  draft_without_intent: 'پس از حذف عبارت‌های نامناسب، درخواست یا احساس مشخصی در متن باقی نمانده است.',
  unsafe_or_changed_intent: 'بازبین نتوانسته هم ایمن‌بودن متن و هم حفظ منظور اولیه را تأیید کند.',
  unsafe_content: 'متن با قواعد محتوای مجاز سازگار نیست؛ احتمال توهین، تهدید یا محتوای آسیب‌زا تشخیص داده شده است.',
  contact_details: 'متن شامل اطلاعات تماس یا نشانه‌های شناسایی شخصی است.',
  draft_instructions: 'متن شامل دستور به سامانه یا قالب فنی است؛ باید فقط پیام مخاطب نوشته شود.',
  invalid_draft: 'متن اولیه خالی، ناخوانا یا خارج از طول مجاز است.',
  invalid_polite_body: 'متن بازنویسی‌شده شرایط لازم برای ارسال را نداشته است.',
  checks_uncertain: 'نتیجهٔ بررسی ایمنی یا حفظ منظور قطعی نیست؛ متن تأیید نشده است.',
  candidate_rejected: 'متن پیشنهادی در بررسی محلی تأیید نشده است.',
  review_rejected: 'بازبین مستقل متن پیشنهادی را تأیید نکرده است.',
  generation_unsafe: 'مدل، متن اولیه را از نظر ایمنی نامناسب تشخیص داده و بازنویسی نکرده است.',
  generation_private: 'مدل وجود اطلاعات خصوصی را تشخیص داده و بازنویسی نکرده است.',
  generation_unclear: 'منظور متن اولیه برای بازنویسی روشن نبوده است.',
  generation_rejected: 'مدل نتوانسته متن اولیه را به یک پیام مجاز تبدیل کند.',
  review_unsafe: 'بازبین مستقل، ایمن‌بودن متن پیشنهادی را تأیید نکرده است.',
  review_private: 'بازبین مستقل احتمال وجود اطلاعات خصوصی در متن پیشنهادی را تشخیص داده است.',
  review_intent: 'بازنویسی منظور اولیهٔ کاربر را حفظ نکرده است.',
  review_added_claims: 'بازنویسی ادعا یا مطلبی افزوده که در متن اولیه نبوده است.',
  review_format: 'پاسخ مدل فقط متن پیام نیست و قالب مجاز ارسال را ندارد.',
  review_register: 'بازنویسی زبان و شیوهٔ بیان متن اولیه را بیش از حد تغییر داده است.',
  review_tone: 'لحن بازنویسی با گزینهٔ انتخاب‌شدهٔ کاربر هماهنگ نبوده است.',
  invalid_tone: 'لحن انتخاب‌شده برای این درخواست معتبر یا فعال نبوده است.',
  configuration_unavailable: 'تنظیمات یا اعتبارنامهٔ لازم برای سرویس هوش مصنوعی آماده نبوده است.',
  local_configuration_unavailable: 'تنظیمات مدل محلی آماده یا معتبر نبوده است.',
  provider_timeout: 'مهلت پاسخ‌گویی سرویس بیرونی تمام شده است.',
  local_timeout: 'مهلت پاسخ‌گویی مدل محلی تمام شده است.',
  local_unavailable: 'ارتباط با مدل محلی برقرار نشده است.',
  invalid_response: 'پاسخ سرویس هوش مصنوعی ناقص یا دارای ساختار نامعتبر بوده است.',
  invalid_local_response: 'پاسخ مدل محلی ساختار معتبر نداشته است.',
  incomplete_local_response: 'مدل محلی پاسخ را کامل نکرده است.',
  invalid_local_review: 'پاسخ بازبین محلی ساختار قابل تأیید نداشته است.',
  invalid_schema: 'پاسخ هوش مصنوعی ساختار قابل بررسی نداشته است.',
  moderation_rejected: 'پیام در بررسی محتوا تأیید نشده و ارسال آن متوقف شده است.',
  moderation_unavailable: 'سرویس بررسی محتوا در دسترس نبوده؛ متن تأیید نشده است.',
  preview_accepted: 'پیش‌نمایش پیام با موفقیت آماده شده؛ این به معنی ارسال پیامک نیست.',
  ai_unavailable: 'سرویس هوش مصنوعی موقتاً در دسترس نبوده است.',
  rewrite_unavailable: 'سرویس بازنویسی موقتاً امکان آماده‌کردن پیام را نداشته است.',
  service_unavailable: 'سرویس موقتاً در دسترس نبوده است؛ درخواست تکمیل نشده است.',
  ai_busy: 'ظرفیت پردازش هوش مصنوعی پر بوده است؛ درخواست انجام نشده است.',
  rewrite_busy: 'ظرفیت بازنویسی پر بوده است؛ درخواست انجام نشده است.',
  rewrite_limit: 'سقف مجاز درخواست بازنویسی تکمیل شده است.',
  rate_limited: 'تعداد درخواست‌ها از سقف مجاز بیشتر شده است.',
  account_unavailable: 'حساب فرستنده در زمان پردازش مجاز یا در دسترس نبوده است.',
  recipient_unavailable: 'ارسال به این مقصد در زمان بررسی مجاز یا ممکن نبوده است.',
  recipient_cooldown: 'باید فاصلهٔ مجاز بین دو ارسال به این مقصد رعایت شود.',
  sms_disabled: 'ارسال پیامک در تنظیمات سرویس غیرفعال بوده است.',
  sending_halted: 'ارسال پیامک به‌صورت عملیاتی متوقف شده است.',
  queue_expired: 'مهلت پردازش پیام در صف گذشته و ارسال آن لغو شده است.',
  preview_expired: 'مهلت تأیید پیش‌نمایش پیام گذشته است.',
  submission_uncertain: 'نتیجهٔ تحویل به سرویس پیامک قطعی نیست؛ برای جلوگیری از تکرار، دوباره ارسال نشود.',
  provider_rejected: 'سرویس پیامک درخواست را نپذیرفته است.',
  provider_terminal_failure: 'سرویس پیامک شکست نهایی ارسال را گزارش کرده است.',
  provider_unavailable: 'ارتباط با سرویس بیرونی برقرار نشده است.',
  daily_budget_wait: 'پیام منتظر فراهم‌شدن بودجهٔ روزانهٔ ارسال است.',
  daily_budget_exhausted: 'سقف بودجهٔ روزانهٔ ارسال تکمیل شده است.',
  provider_cost_halt: 'ارسال به‌دلیل کنترل هزینهٔ سرویس متوقف شده است.',
  provider_cost_exceeded: 'هزینهٔ گزارش‌شده از حد مجاز بیشتر است؛ ارسال باید بررسی شود.',
  cost_ceiling_missing: 'سقف هزینهٔ لازم برای ارسال تنظیم نشده است.',
  outside_pilot_allowlist: 'مقصد در فهرست مجاز اجرای محدود قرار ندارد.',
  policy_unavailable: 'شرایط مجازبودن ارسال قابل تأیید نبوده است.',
  unknown_deadline: 'مهلت تعیین نتیجهٔ نامعلوم گذشته است؛ وضعیت مالی نیاز به تطبیق دارد.',
  recipient_controls_unavailable: 'کنترل لغو دریافت یا محدودیت مقصد در دسترس نیست؛ ارسال ایمن متوقف می‌ماند.',
  wallet_receipt_conflict: 'رسید پرداخت با ثبت کیف پول سازگار نیست؛ باید پیش از اقدام مالی تطبیق داده شود.',
  refund_open: 'بازپرداخت ناتمام وجود دارد و باید بررسی شود.',
  payment_unknown: 'نتیجهٔ پرداخت هنوز قطعی نیست و باید با درگاه تطبیق داده شود.',
  delivery_unknown: 'نتیجهٔ تحویل پیامک هنوز قطعی نیست؛ ارسال تکراری انجام نشود.',
  outbox_pending: 'پیام‌هایی در صف انتظار پردازش قرار دارند.',
  oldest_queue_seconds: 'قدیمی‌ترین پیام صف هنوز منتظر تعیین تکلیف است.',
  queue_age: 'زمان انتظار قدیمی‌ترین پیام صف از حد هشدار گذشته است؛ وضعیت صف را بررسی کنید.',
  reports_open: 'گزارش‌های کاربران هنوز بررسی یا بسته نشده‌اند.',
  budget_80_percent: 'حداقل هشتاد درصد بودجهٔ روزانهٔ ارسال رزرو شده است.',
  invalid_input: 'اطلاعات درخواست معتبر نبوده است.',
};

export function managementExplanation(value: unknown): string {
  if (!value) return 'علتی ثبت نشده است.';
  if (/^(template|gapgpt|ollama)(_(polite|firm|blunt|angry))?$/.test(String(value))) return 'متن با روش و لحن ثبت‌شده آماده و در بررسی محتوا تأیید شده است.';
  return explanations[String(value)] || 'توضیح فارسی این علت هنوز ثبت نشده است؛ جزئیات فنی باید بررسی شود.';
}

const values: Record<string, Record<string, string>> = {
  payment_mode: { free: 'رایگان', gift: 'هدیه', sponsored: 'رایگان با هزینهٔ سرویس', wallet: 'کیف پول', gateway: 'درگاه بانکی', card: 'کارت‌به‌کارت', demo: 'آزمایشی', zarinpal: 'زرین‌پال' },
  category: {"appreciation": "تشکر و قدردانی", "encouragement": "دلگرمی و تشویق", "congratulations": "تبریک و شادی", "body": "بهداشت فردی", "breath": "بهداشت دهان", "noise": "آرامش و صدا", "shared_space": "فضای مشترک", "punctuality": "خوش‌قولی", "listening": "خوب گوش‌دادن", "conversation": "ادب در گفت‌وگو", "personal_space": "حریم شخصی", "phone_etiquette": "استفاده از تلفن", "neighbor": "حقوق همسایه", "parking": "پارک خودرو", "teamwork": "همکاری گروهی", "apology": "عذرخواهی", "good_wishes": "آرزوی روز خوب", "environment": "مراقبت از محیط", "custom": "متن دلخواه"},
  provider: { kavenegar: 'کاوه‌نگار', zarinpal: 'زرین‌پال', console: 'ثبت آزمایشی', demo: 'آزمایشی', gapgpt: 'گپ‌جی‌پی‌تی', ollama: 'مدل محلی', template: 'متن آماده' },
  environment: { demo: 'آزمایشی', live: 'واقعی', sandbox: 'آزمایشی درگاه', production: 'واقعی' },
  action: { suspend: 'تعلیق کاربر', unsuspend: 'رفع تعلیق', tone: 'تغییر لحن', free_sending: 'تغییر ارسال رایگان', account_limits: 'تغییر سقف کاربر', halt: 'توقف ارسال', resume: 'ازسرگیری ارسال', message_texts: 'مشاهدهٔ متن پیام', attempt_texts: 'مشاهدهٔ متن درخواست', blacklist_viewed: 'مشاهدهٔ لیست سیاه', account_phones_viewed: 'مشاهدهٔ شمارهٔ کاربران', user_activity_viewed: 'مشاهدهٔ فعالیت کاربر', review: 'بررسی گزارش', close_report: 'بستن گزارش', hold_report: 'نگهداری گزارش', ack_alert: 'ثبت بررسی هشدار', confirm_refund: 'ثبت بازپرداخت', grant_package: 'فعال‌سازی بسته', approve_card: 'تأیید رسید', reject_card: 'رد رسید' },
};

Object.assign(values.payment_mode, { credit_demo: 'اعتبار بستهٔ آزمایشی', credit_live: 'اعتبار بستهٔ واقعی' });
Object.assign(values.action, {
  message_text_viewed: 'مشاهدهٔ متن پیام', message_attempt_text_viewed: 'مشاهدهٔ متن تلاش ساخت پیام', report_viewed: 'مشاهدهٔ پروندهٔ گزارش',
  approve_manual_payment: 'تأیید واریز بانکی', reject_manual_payment: 'رد رسید بانکی', update_site_limits: 'ویرایش محدودیت‌های سایت',
  configure_site_limits: 'پیکربندی محدودیت‌های سایت', update_ai_configuration: 'ویرایش تنظیمات هوش مصنوعی', update_message_package: 'ویرایش بستهٔ پیام',
  account_send_options: 'ویرایش گزینه‌های ارسال کاربر', account_delete_requested: 'ثبت درخواست حذف حساب', archive_unknown_outbox: 'بایگانی مورد نامعلوم صف',
  automatic_cost_halt: 'توقف خودکار به‌علت هزینه', bot_integration_disabled: 'غیرفعال‌کردن اتصال ربات', bot_integration_key_issued: 'صدور کلید اتصال ربات',
  invitation_reward: 'اعطای جایزهٔ دعوت', manual_payment_settings: 'ویرایش تنظیمات رسید بانکی', reset_demo_limits: 'بازنشانی سقف‌های آزمایشی',
  support_close: 'بستن گفت‌وگوی پشتیبانی', support_reply: 'پاسخ پشتیبانی', save_message_groups: 'ذخیرهٔ دستهٔ پیام نمونه', save_message_examples: 'ذخیرهٔ پیام نمونه',
  delete_message_groups: 'حذف دستهٔ پیام نمونه', delete_message_examples: 'حذف پیام نمونه',
});

export function managementDisplayValue(field: string, value: unknown): unknown {
  field = field.split('__').at(-1) || field;
  if (['reason_code', 'last_error_code', 'code'].includes(field)) return value ? managementExplanation(value) : '—';
  if (!values[field] || value === null || value === undefined || value === '') return value;
  return values[field][String(value)] || ({category:'موضوع ثبت‌شده',provider:'سرویس ثبت‌شده',environment:'محیط ثبت‌شده',payment_mode:'روش پرداخت ثبت‌شده',action:'اقدام مدیریتی ثبت‌شده'}[field] ?? value);
}
