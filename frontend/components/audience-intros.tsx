"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "./icons";
import styles from "./home-intro.module.css";

const audiences = [
  {
    id: "family-friends",
    icon: "heart",
    title: "برای خانواده و دوستان",
    description: "یکی از نزدیکانت روز سختی کنارت بود؟ براش یک پیام تشکر بنویس. اگر دوست داری حرف‌های بقیه رو هم بشنوی، لینک یا QR شخصی خودت رو در گروه خانوادگی یا جمع دوستات بذار.",
    sendLabel: "نوشتن پیام برای یک آشنا",
    shareText: "برای کسی که کنارمون بوده می‌تونیم یک پیامک تشکر بفرستیم. هر کسی هم که دوست داره از جمعمون پیام بگیره، می‌تونه لینک شخصی خودش رو بسازه.",
  },
  {
    id: "neighbors",
    icon: "space",
    title: "برای همسایه‌ها",
    description: "برای رعایت ساعت استراحت یا باز موندن راهرو، یک یادآوری کوتاه و خصوصی برای همسایه‌ات بنویس. اگر می‌خوای خودت پیشنهادهای همسایه‌ها رو بگیری، لینک شخصی‌ات رو در گروه ساختمان بذار.",
    sendLabel: "نوشتن یادآوری برای همسایه",
    shareText: "اگه دربارهٔ آرامش ساختمان یا رفت‌وآمد توی راهرو حرفی داریم، می‌تونیم برای یک همسایه پیامک محترمانه بنویسیم. هر کس هم که مایله پیشنهاد بگیره، می‌تونه لینک شخصی خودش رو به گروه بده.",
  },
] as const satisfies readonly { id: string; icon: IconName; title: string; description: string; sendLabel: string; shareText: string }[];

function CopyIntroduction({ id, text }: { id: string; text: string }) {
  const [notice, setNotice] = useState("");
  const [manualCopy, setManualCopy] = useState("");
  const field = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (manualCopy) {
      field.current?.focus();
      field.current?.select();
    }
  }, [manualCopy]);

  async function copy() {
    const url = new URL(`/about#${id}`, window.location.origin);
    const content = `${text}\n${url.href}`;
    try {
      await navigator.clipboard.writeText(content);
      setManualCopy("");
      setNotice("متن معرفی و لینک عمومی این بخش کپی شد.");
    } catch {
      setManualCopy(content);
      setNotice("متن و لینک آماده است. آن را از کادر زیر کپی کن.");
    }
  }

  return <div className={styles.shareCopy}>
    <button type="button" className="text-button" onClick={copy}>کپی متن معرفی برای گروه</button>
    <p role="status">{notice}</p>
    {manualCopy && <textarea ref={field} readOnly rows={4} aria-label="متن و لینک عمومی معرفی" value={manualCopy} onFocus={event => event.currentTarget.select()} />}
  </div>;
}

export function AudienceIntros() {
  return <div className={styles.audienceGrid}>
    {audiences.map(audience => <section className={styles.audienceCard} key={audience.id} id={audience.id} aria-labelledby={`${audience.id}-title`}>
      <Icon name={audience.icon} size={24} />
      <h2 id={`${audience.id}-title`}>{audience.title}</h2>
      <p>{audience.description}</p>
      <div className={styles.actions}>
        <Link className="button primary" href="/#compose">{audience.sendLabel}</Link>
        <Link className="button ghost" href="/profile/share" prefetch={false}>ساخت لینک دریافت پیام</Link>
      </div>
      <CopyIntroduction id={audience.id} text={audience.shareText} />
    </section>)}
  </div>;
}
