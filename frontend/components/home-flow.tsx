"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Composer } from "./composer";
import { Icon } from "./icons";
import { LetterFlight } from "./letter-flight";
import { HomeTrustMarks } from "./home-trust-marks";

export function HomeFlow() {
  const [composing, setComposing] = useState(false);
  const touch = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const sync = () => setComposing(window.location.hash === "#compose");
    const resize = () => {
      const viewport = window.visualViewport;
      if (viewport && Math.abs(viewport.scale - 1) > 0.01) return;
      document.documentElement.style.setProperty("--app-height", `${viewport?.height || window.innerHeight}px`);
      const keyboardInset = viewport ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop) : 0;
      document.documentElement.style.setProperty("--composer-keyboard-inset", `${keyboardInset}px`);
    };
    sync();
    resize();
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    window.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("scroll", resize);
    return () => {
      window.removeEventListener("hashchange", sync);
      window.removeEventListener("popstate", sync);
      window.removeEventListener("resize", resize);
      window.visualViewport?.removeEventListener("resize", resize);
      window.visualViewport?.removeEventListener("scroll", resize);
      document.documentElement.style.removeProperty("--app-height");
      document.documentElement.style.removeProperty("--composer-keyboard-inset");
    };
  }, []);

  useEffect(() => {
    document.getElementById(composing ? "compose-title" : "welcome-title")?.focus({ preventScroll: true });
  }, [composing]);

  function showComposer(value: boolean) {
    setComposing(value);
    const hash = value ? "#compose" : "";
    if (window.location.hash !== hash)
      window.history.pushState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
  }

  return (
    <div className="home-flow" aria-label="شروع و نوشتن پیام">
      <section
        className="home-slide hero wrap"
        aria-roledescription="اسلاید"
        aria-label="معرفی؛ صفحه اول"
        aria-labelledby="welcome-title"
        hidden={composing}
        onPointerDown={event => {
          touch.current = null;
          if (event.pointerType !== "touch" || !event.isPrimary || event.clientX < 24 ||
              event.clientX > window.innerWidth - 24 ||
              (event.target as HTMLElement).closest("a,button")) return;
          touch.current = { x: event.clientX, y: event.clientY };
        }}
        onPointerCancel={() => { touch.current = null; }}
        onPointerUp={event => {
          const start = touch.current;
          touch.current = null;
          if (start && event.clientX - start.x > 64 && Math.abs(event.clientY - start.y) < 40)
            showComposer(true);
        }}
      >
        <Link href="/profile" prefetch={false} className="home-profile-link">
          <Icon name="user" size={19} /> پروفایل
        </Link>
        <div className="hero-copy">
          <span className="hero-eyebrow"><Icon name="sparkle" size={18} /> حرف‌های کوچیک، حالِ بهتر</span>
          <h1 id="welcome-title" tabIndex={-1}>یه حرف خوب،<br />یه <span className="highlight-text">حال خوب‌تر.</span></h1>
          <p className="hero-description">تشکر، دلگرمی یا یه یادآوری دوستانه؛<br />حرفت رو با احترام برسون، بدون نمایش اسمت به گیرنده.</p>
          <button type="button" className="button primary hero-cta" onClick={() => showComposer(true)}>
            بعدی؛ حرفم رو بگم <Icon name="arrow" size={20} />
          </button>
          <Link href="/help" className="hero-help">اول ببینم چطوری کار می‌کنه</Link>
          <Link href="/invitations" prefetch={false} className="hero-help">دعوت دوستان <Icon name="heart" size={16} /></Link>
          <div className="slide-dots" aria-label="صفحه اول از دو صفحه">
            <span className="active" /><span />
          </div>
        </div>
        <div className="hero-art"><LetterFlight /><HomeTrustMarks /></div>
      </section>
      <div className="home-slide compose-slide" hidden={!composing} aria-roledescription="اسلاید" aria-label="نوشتن پیام؛ صفحه دوم">
        <Composer onExit={() => showComposer(false)} />
      </div>
    </div>
  );
}
