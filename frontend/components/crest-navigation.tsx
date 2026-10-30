"use client";

import Link from "next/link";
import { useLayoutEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./icons";
import styles from "./crest-navigation.module.css";
import { useComposeView } from "@/lib/use-compose-view";

const destinations: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "خونه", icon: "home" },
  { href: "/#compose", label: "نوشتن پیام", icon: "chat" },
  { href: "/history", label: "پیام‌های من", icon: "receipt" },
  { href: "/invitations", label: "دعوت دوستان", icon: "heart" },
  { href: "/profile", label: "پروفایل", icon: "user" },
];

function activeDestination(path: string) {
  if (path === "/") return 0;
  if (path === "/history" || path.startsWith("/orders/")) return 2;
  if (path === "/invitations") return 3;
  if (["/profile", "/preferences", "/wallet", "/credits"].includes(path)) return 4;
  return -1;
}

function crestMotion(nav: HTMLElement, path: SVGPathElement, droplet: SVGCircleElement, links: HTMLAnchorElement[]) {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  let centers: number[] = [], iconBottoms: number[] = [], width = 0, barHeight = 0, pitch = 0;
  let selected = links.findIndex(link => link.hasAttribute("aria-current"));
  const initialSelection = selected;
  let pendingSelection = false;
  let x = 0, velocity = 0, height = 0, heightVelocity = 0;
  let frame = 0, previous = 0, ready = false, disposed = false;
  let phase: "idle" | "travel" | "drop" | "fill" = "idle";
  let phaseStarted = 0;
  const fills = links.map(() => 0);
  const maximum = 13;
  const dropDuration = 280, fillDuration = 220;
  const clamp = (value: number) => Math.max(0, Math.min(1, value));
  const ease = (value: number) => value * value * (3 - 2 * value);

  function draw(now = 0) {
    // Longer jumps gain speed, leaving a wider tail and leaning into the move.
    const speed = Math.max(-1, Math.min(1, velocity / 1400));
    const stretch = Math.abs(speed) * .5;
    const left = pitch * .4 * (1 + stretch + speed * .3);
    const right = pitch * .4 * (1 + stretch - speed * .3);
    const peak = x + speed * 9;
    const bottom = barHeight + 1;
    path.setAttribute("d", `M ${x - left} ${bottom} C ${x - left * .45} ${bottom} ${peak - left * .32} ${bottom - height} ${peak} ${bottom - height} C ${peak + right * .32} ${bottom - height} ${x + right * .45} ${bottom} ${x + right} ${bottom} Z`);
    links.forEach((link, index) => {
      link.style.setProperty("--crest-fill-level", fills[index].toFixed(3));
    });
    if (phase === "drop" && selected >= 0) {
      const progress = clamp((now - phaseStarted) / dropDuration);
      const start = bottom - maximum + 1;
      droplet.setAttribute("cx", String(centers[selected]));
      droplet.setAttribute("cy", String(start + (iconBottoms[selected] - start) * ease(progress)));
      droplet.setAttribute("r", String(3.4 * (1 - clamp((progress - .8) / .2))));
      droplet.setAttribute("opacity", "1");
    } else {
      droplet.setAttribute("opacity", "0");
    }
  }

  function tick(now: number) {
    frame = 0;
    if (disposed) return;
    const dt = previous ? Math.min((now - previous) / 1000, 1 / 30) : 1 / 60;
    previous = now;
    const target = selected >= 0 ? centers[selected] : x;
    velocity += ((target - x) * 420 - velocity * 33) * dt;
    x += velocity * dt;
    const targetHeight = selected < 0 ? 0 : maximum * (1 - clamp(Math.abs(velocity) / 1100) * .84);
    heightVelocity += ((targetHeight - height) * 250 - heightVelocity * 25) * dt;
    height += heightVelocity * dt;
    fills.forEach((fill, index) => {
      if (index !== selected || phase === "travel") fills[index] = Math.max(0, fill - dt / .16);
    });
    if (phase === "travel" && selected >= 0 && Math.abs(target - x) < .8 && Math.abs(velocity) < 35 && height > maximum * .65) {
      phase = "drop"; phaseStarted = now;
    } else if (phase === "drop" && now - phaseStarted >= dropDuration) {
      phase = "fill"; phaseStarted = now;
    }
    if (phase === "fill" && selected >= 0) {
      const progress = clamp((now - phaseStarted) / fillDuration);
      fills[selected] = ease(progress);
      if (progress === 1) phase = "idle";
    }
    const atRest = Math.abs(target - x) < .05 && Math.abs(velocity) < .12 && Math.abs(targetHeight - height) < .04 && Math.abs(heightVelocity) < .12;
    if (atRest) {
      x = target; velocity = 0; height = selected < 0 ? 0 : maximum; heightVelocity = 0;
      if (selected < 0) phase = "idle";
    }
    draw(now);
    if (!atRest || phase !== "idle" || fills.some((fill, index) => index !== selected && fill > 0)) frame = requestAnimationFrame(tick);
  }

  function select(index: number) {
    const changed = selected !== index;
    selected = index;
    if (!ready) { pendingSelection = pendingSelection || changed; return; }
    if (media.matches) {
      cancelAnimationFrame(frame); frame = 0;
      x = selected >= 0 ? centers[selected] : x;
      velocity = heightVelocity = 0; height = selected < 0 ? 0 : maximum;
      phase = "idle";
      fills.forEach((_, index) => { fills[index] = index === selected ? 1 : 0; });
      draw(); return;
    }
    if (!changed) return;
    phase = "travel";
    if (!frame) { previous = 0; frame = requestAnimationFrame(tick); }
  }

  function measure() {
    if (disposed) return;
    const bounds = nav.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const previousWidth = width;
    width = bounds.width; barHeight = bounds.height;
    centers = links.map(link => { const rect = link.getBoundingClientRect(); return rect.left - bounds.left + rect.width / 2; });
    iconBottoms = links.map(link => (link.querySelector("svg")?.getBoundingClientRect().bottom ?? bounds.top + 31) - bounds.top);
    pitch = links.length > 1 ? Math.abs(centers[1] - centers[0]) : width;
    path.ownerSVGElement?.setAttribute("viewBox", `0 0 ${width} ${barHeight}`);
    if (!ready) {
      const animate = pendingSelection && !media.matches;
      const from = animate ? initialSelection : selected;
      x = from >= 0 ? centers[from] : width / 2;
      height = from < 0 ? 0 : maximum;
      fills.forEach((_, index) => { fills[index] = index === from ? 1 : 0; });
      phase = animate ? "travel" : "idle";
      ready = true;
      draw();
      if (animate) frame = requestAnimationFrame(tick);
      return;
    }
    // ResizeObserver also fires when a hidden dock reappears. Preserve the
    // in-flight travel/drop/fill sequence instead of snapping to the new route.
    if (phase === "idle") {
      x = selected >= 0 ? centers[selected] : width / 2;
      velocity = heightVelocity = 0; height = selected < 0 ? 0 : maximum;
    } else if (previousWidth) {
      x *= width / previousWidth;
      velocity *= width / previousWidth;
    }
    draw(performance.now());
  }

  measure();
  const observer = new ResizeObserver(measure);
  observer.observe(nav);
  void document.fonts.ready.then(measure);
  const preferenceChanged = () => select(selected);
  media.addEventListener("change", preferenceChanged);
  return { select, dispose() { disposed = true; observer.disconnect(); cancelAnimationFrame(frame); media.removeEventListener("change", preferenceChanged); } };
}

export function CrestNavigation({ mode, hidden = false }: { mode: "desktop" | "mobile"; hidden?: boolean }) {
  const currentPath = usePathname();
  const composing = useComposeView();
  const selected = composing ? 1 : activeDestination(currentPath);
  const nav = useRef<HTMLElement>(null);
  const crest = useRef<SVGPathElement>(null);
  const droplet = useRef<SVGCircleElement>(null);
  const motion = useRef<ReturnType<typeof crestMotion> | null>(null);

  useLayoutEffect(() => {
    if (!nav.current || !crest.current || !droplet.current) return;
    motion.current = crestMotion(nav.current, crest.current, droplet.current, Array.from(nav.current.querySelectorAll("a")));
    return () => { motion.current?.dispose(); motion.current = null; };
  }, []);
  useLayoutEffect(() => { motion.current?.select(selected); }, [selected]);

  return (
    <div hidden={hidden} className={`${styles.dock} ${styles[mode]}${mode === "mobile" ? " mobile-nav" : ""}`}>
    <nav ref={nav} className={styles.nav} aria-label={mode === "mobile" ? "دسترسی سریع موبایل" : "منوی اصلی"}>
      <svg className={styles.surface} aria-hidden="true" preserveAspectRatio="none"><path ref={crest} /><circle ref={droplet} r="0" opacity="0" /></svg>
      <div className={styles.links}>
        {destinations.map((item, index) => (
          <Link key={item.href} href={item.href} prefetch={false} className={styles.link} title={item.label}
            aria-current={selected === index ? (!composing && currentPath === item.href ? "page" : "location") : undefined}>
            <span className={styles.icon} aria-hidden="true">
              <Icon name={item.icon} size={23} />
              <span className={styles.flood}><Icon name={item.icon} size={23} /></span>
            </span>
            <span className={styles.label}>{item.label}</span>
          </Link>
        ))}
      </div>
    </nav>
    </div>
  );
}
