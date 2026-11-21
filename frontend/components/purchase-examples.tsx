"use client";

import Link from "next/link";
import { purchaseExamples } from "@/lib/purchase-examples";
import { useId, useState } from "react";
import { useApp } from "./app-provider";
import styles from "./purchase-examples.module.css";

export function PurchaseExamples() {
  const { data } = useApp();
  const [selected, setSelected] = useState(0);
  const group = useId();
  if (!data || data.conversion_experiment?.show_examples === false) return null;
  const example = purchaseExamples[selected];

  return <section id="message-examples" className={styles.examples} aria-labelledby={`${group}-heading`}>
    <h2 id={`${group}-heading`}>گیرنده چه پیامکی می‌بینه؟</h2>
    <fieldset className={styles.choices}>
      <legend>یک موقعیت رو انتخاب کن</legend>
      <div className={styles.options}>
        {purchaseExamples.map((item, index) => <label key={item.title}>
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
    <p className={styles.note}>این یک نمونهٔ ثابت با قالب پیش‌فرض پیامک است. می‌توانی همین متن اولیه را ویرایش کنی و نتیجهٔ بازبینی را ببینی.</p>
    <Link href={`/try-message?example=${example.id}`} prefetch={false} className="button ghost">این متن را امتحان کنم</Link>
  </section>;
}
