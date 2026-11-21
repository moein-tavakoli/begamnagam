"use client";

import { useId, useState } from "react";
import { useApp } from "./app-provider";
import styles from "./purchase-examples.module.css";

// The example bodies come from the corresponding reviewed DIRECT_TEMPLATES.
// The last line stands in for the single recipient-only URL in a first SMS.
const examples = [
  {
    title: "تشکر از همکار شیفت",
    input: "دیروز آخر شیفت موندی و کمکم کردی. مرسی که وقت گذاشتی.",
    body: "کمک و همراهی شما ارزشمند بود؛ ممنونم که وقت گذاشتید و کمک کردید.",
  },
  {
    title: "دلگرمی بعد از تمرین",
    input: "تمرین امروز سخت بود. تلاشت رو دیدم، ادامه بده و به خودت استراحت هم بده.",
    body: "تلاشتان دیده می‌شود. کارتان ارزش دارد؛ ادامه بدهید و به خودتان فرصت استراحت هم بدهید.",
  },
  {
    title: "یادآوری به همسایه",
    input: "میشه وقت استراحت سر و صدا کمتر باشه و وسایل رو کنار در ورودی نذاریم؟",
    body: "لطفاً در ساعت استراحت همسایه‌ها صدای کمتری ایجاد کنید و وسایل را در مسیر راهرو و ورودی نگذارید.",
  },
] as const;

export function PurchaseExamples() {
  const { data } = useApp();
  const [selected, setSelected] = useState(0);
  const group = useId();
  if (!data || data.conversion_experiment?.show_examples === false) return null;
  const example = examples[selected];

  return <section id="message-examples" className={styles.examples} aria-labelledby={`${group}-heading`}>
    <h2 id={`${group}-heading`}>گیرنده چه پیامکی می‌بینه؟</h2>
    <fieldset className={styles.choices}>
      <legend>یک موقعیت رو انتخاب کن</legend>
      <div className={styles.options}>
        {examples.map((item, index) => <label key={item.title}>
          <input type="radio" name={group} checked={index === selected} onChange={() => setSelected(index)} />
          {item.title}
        </label>)}
      </div>
    </fieldset>
    <div className={styles.comparison} aria-live="polite" aria-atomic="true">
      <div className={styles.input}>
        <h3>متن اولیهٔ فرستنده</h3>
        <p>{example.input}</p>
      </div>
      <div className={styles.sms}>
        <h3>نمونهٔ پیامک گیرنده</h3>
        <p>نمیدونم بهت بگم یا نگم؟<br />{example.body}<br />پاسخ یا لغو: [لینک خصوصی گیرنده]</p>
      </div>
    </div>
    <p className={styles.note}>این نمونه‌ها با متن‌های بررسی‌شده و قالب پیش‌فرض ساخته شده‌اند. در پیش‌نمایش پیام خودت، متن نهایی رو قبل از تأیید می‌بینی.</p>
  </section>;
}
