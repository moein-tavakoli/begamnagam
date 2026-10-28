import { Icon } from "@/components/icons";
import { StructuredData } from "@/components/structured-data";
import { pageJsonLd, publicMetadata } from "@/lib/seo";
import styles from "./page.module.css";

export const metadata = publicMetadata("/links");

const links = [
  { name: "سایت بگم نگم", handle: "begamnagam.ir", href: "https://begamnagam.ir", symbol: "web" },
  { name: "اینستاگرام", handle: "@begamnagam.ir", href: "https://www.instagram.com/begamnagam.ir/", symbol: "camera" },
  { name: "تلگرام", handle: "@begamnagam", href: "https://t.me/begamnagam", symbol: "send" },
  { name: "بله", handle: "@begamnagam", href: "https://ble.ir/begamnagam", symbol: "ب" },
  { name: "سروش", handle: "@begamnagam", href: "https://splus.ir/begamnagam", symbol: "س" },
  { name: "گپ", handle: "@begamnagam", href: "https://gap.im/begamnagam", symbol: "گ" },
] as const;

function LinkSymbol({ symbol }: { symbol: typeof links[number]["symbol"] }) {
  if (symbol === "ب" || symbol === "س" || symbol === "گ") return <span>{symbol}</span>;
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round">
      {symbol === "web" ? <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" /></>
        : symbol === "camera" ? <><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><path d="M17.5 6.5h.01" /></>
          : <><path d="m21 3-7 18-4-7-7-4L21 3Z" /><path d="m10 14 6-6" /></>}
    </svg>
  );
}

export default function LinksPage() {
  return (
    <div className={styles.page}>
      <StructuredData data={pageJsonLd("/links")} />
      <header className={styles.intro}>
        <span className={styles.mark} aria-hidden="true"><Icon name="chat" size={32} /></span>
        <h1>بگم نگم<span>.</span></h1>
        <p>حرف‌های کوچیک، حالِ بهتر.</p>
      </header>
      <nav className={styles.links} aria-label="سایت و شبکه‌های اجتماعی بگم نگم">
        <p className={styles.caption}>هر جا راحت‌تری، کنار همیم</p>
        <ul>
          {links.map((link, index) => (
            <li key={link.href}>
              <a href={link.href} target="_blank" rel="noopener noreferrer" aria-describedby="links-new-tab" className={`${styles.card} ${index === 0 ? styles.primary : ""}`}>
                <span className={styles.symbol} aria-hidden="true"><LinkSymbol symbol={link.symbol} /></span>
                <span className={styles.label}><strong>{link.name}</strong><bdi dir="ltr" className={styles.handle}>{link.handle}</bdi></span>
                <span className={styles.arrow} aria-hidden="true"><Icon name="arrow" size={19} /></span>
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <p id="links-new-tab" className="sr-only">در زبانهٔ جدید باز می‌شود.</p>
      <footer className={styles.note}><Icon name="heart" size={16} /> با احترام، برای بهتر شدن</footer>
    </div>
  );
}
