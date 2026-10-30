"use client";

import { createPortal } from "react-dom";
import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { gsap } from "gsap";
import type { SendFeedback } from "@/lib/send-feedback";
import styles from "./paper-dart-button.module.css";

export type PaperDartHandle = { start: () => void; settle: (result: SendFeedback) => Promise<void> };
type Phase = "idle" | "folding" | "flying" | "waiting" | SendFeedback;
type Bounds = { left: number; top: number; width: number; height: number };
type Props = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode };

export const PaperDartButton = forwardRef<PaperDartHandle, Props>(function PaperDartButton({ children, disabled, className = "", ...props }, ref) {
  const button = useRef<HTMLButtonElement>(null), layer = useRef<HTMLDivElement>(null);
  const [bounds, setBounds] = useState<Bounds | null>(null), [phase, setPhase] = useState<Phase>("idle");
  const active = useRef(false), reduced = useRef(false), timeline = useRef<gsap.core.Timeline | null>(null);
  const flight = useRef<Promise<void>>(Promise.resolve()), resolveFlight = useRef<() => void>(() => {});
  const feedback = useRef<() => void>(() => {}), feedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);
  const start = () => {
    if (active.current || !button.current) return;
    active.current = true;
    reduced.current = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rect = button.current.getBoundingClientRect();
    flight.current = new Promise(resolve => { resolveFlight.current = resolve; });
    setBounds({ left: rect.left, top: rect.top, width: rect.width, height: rect.height });
    setPhase(reduced.current ? "waiting" : "folding");
    if (reduced.current) resolveFlight.current();
  };
  const settle = async (result: SendFeedback) => {
    if (!active.current || !mounted.current) return;
    // Rejected/uncertain responses stop the takeoff; they never show the check.
    if (result !== "accepted") { timeline.current?.kill(); resolveFlight.current(); }
    await flight.current;
    if (!mounted.current) return;
    setPhase(result);
    await new Promise<void>(resolve => {
      feedback.current = resolve;
      feedbackTimer.current = setTimeout(resolve, reduced.current ? 0 : result === "rejected" ? 300 : 820);
    });
    if (!mounted.current) return;
    feedback.current = () => {};
    active.current = false; setPhase("idle"); setBounds(null);
  };
  useImperativeHandle(ref, () => ({ start, settle }));

  useEffect(() => {
    mounted.current = true;
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => {
      reduced.current = media.matches;
      if (media.matches && active.current) {
        if (timeline.current?.isActive()) timeline.current.progress(1);
        resolveFlight.current();
        if (feedbackTimer.current) { clearTimeout(feedbackTimer.current); feedback.current(); }
      }
    };
    media.addEventListener("change", change);
    return () => { mounted.current = false; timeline.current?.kill(); resolveFlight.current(); if (feedbackTimer.current) clearTimeout(feedbackTimer.current); feedback.current(); media.removeEventListener("change", change); };
  }, []);

  useLayoutEffect(() => {
    if (!bounds || reduced.current || !layer.current) return;
    const root = layer.current, select = gsap.utils.selector(root);
    const { width: w, height: h, left } = bounds, cx = w / 2, cy = h / 2;
    const rw = Math.min(w * .88, 210), rh = rw * .46, by = cy + rh / 2, ty = cy - rh / 2;
    const s = Math.min(112, w * .55) / 112;
    const point = (x: number, y: number) => `${cx + x * s},${cy + y * s}`;
    const roof = [
      `${cx-rw/2},${by} ${cx},${ty} ${cx-rw*.18},${by}`,
      `${cx-rw*.18},${by} ${cx},${ty} ${cx},${by}`,
      `${cx},${by} ${cx},${ty} ${cx+rw*.18},${by}`,
      `${cx+rw*.18},${by} ${cx},${ty} ${cx+rw/2},${by}`,
    ];
    const dart = [
      `${point(-50,-18)} ${point(58,-28)} ${point(-16,1)}`,
      `${point(-16,1)} ${point(58,-28)} ${point(-50,26)}`,
      `${point(-50,26)} ${point(58,-28)} ${point(-5,21)}`,
      `${point(-5,21)} ${point(58,-28)} ${point(15,18)}`,
    ];
    const context = gsap.context(() => {
      gsap.set(select("[data-carrier]"), { transformOrigin: `${cx}px ${cy}px`, transformPerspective: 700 });
      const tl = gsap.timeline({ onComplete: () => { if (mounted.current) setPhase("waiting"); resolveFlight.current(); } });
      timeline.current = tl;
      tl.to(select("[data-base]"), { opacity: 0, duration: .15 }, .12)
        .to(select("[data-face]"), { opacity: 1, duration: .12, stagger: .018 }, .1);
      select("[data-face]").forEach((face, index) => {
        tl.to(face, { attr: { points: roof[index] }, duration: .3, ease: "power2.inOut" }, .12 + index * .015)
          .to(face, { attr: { points: dart[index] }, duration: .38, ease: "power2.inOut" }, .52 + index * .018);
      });
      tl.to(select("[data-carrier]"), { scale: .92, rotationX: 18, duration: .16, ease: "power2.out" }, .05)
        .to(select("[data-carrier]"), { scale: 1, rotationX: 0, duration: .2 }, .3)
        .to(select("[data-carrier]"), { rotationY: 105, rotation: -30, duration: .16, ease: "power2.inOut" }, .56)
        .to(select("[data-carrier]"), { rotationY: 0, rotation: 12, duration: .21, ease: "power2.out" }, .72)
        .to(select("[data-carrier]"), { x: -18, y: 7, rotation: 0, duration: .16, ease: "sine.inOut" }, .94)
        .call(() => { if (mounted.current) setPhase("flying"); }, [], 1.1)
        .to(select("[data-carrier]"), { x: innerWidth - left - cx + 140, y: -Math.min(240, innerHeight * .35), rotation: -7, scale: .84, duration: .44, ease: "power3.in" }, 1.1)
        .fromTo(select("[data-trail]"), { opacity: 0, strokeDashoffset: 1 }, { opacity: .65, strokeDashoffset: 0, duration: .22, stagger: .045 }, 1.1)
        .to(select("[data-trail]"), { opacity: 0, duration: .17 }, 1.39)
        .to(select("[data-carrier]"), { opacity: 0, duration: .07 }, 1.49);
    }, root);
    return () => { context.revert(); timeline.current = null; resolveFlight.current(); };
  }, [bounds]);

  const animating = phase !== "idle", sending = ["folding", "flying", "waiting"].includes(phase);
  const status = phase === "accepted" ? "ثبت شد" : phase === "uncertain" ? "نتیجه در حال بررسی است" : phase === "rejected" ? "ثبت نشد" : phase === "waiting" ? "در حال ثبت درخواست…" : "در حال ارسال درخواست…";
  return <>
    <button {...props} ref={button} type="submit" className={`${className} ${styles.button}`} disabled={disabled || animating}
      data-send-phase={phase} aria-busy={sending || undefined} aria-label={animating ? status : undefined}
      style={animating ? { height: bounds?.height, minHeight: bounds?.height, maxHeight: bounds?.height, background: "transparent", borderColor: "transparent", boxShadow: "none", opacity: 1 } : undefined}>
      <span className={styles.label} style={{ opacity: animating ? 0 : 1 }}>{children}</span>
      {animating && <span className={styles.feedback} data-result={phase} aria-hidden="true">
        {phase === "accepted" && <svg width="18" height="18" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>}
        {phase === "rejected" && <span>×</span>}
        {phase === "uncertain" && <span>◷</span>}
        {(phase === "waiting" || phase === "accepted" || phase === "rejected" || phase === "uncertain") && status}
      </span>}
    </button>
    <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">{animating ? status : ""}</span>
    {bounds && !reduced.current && createPortal(<div className={styles.viewport} aria-hidden="true"><div ref={layer} className={styles.anchor} style={bounds} data-dart-overlay="true" data-phase={phase}>
      <div data-carrier="true">
      <svg className={styles.paper} width={bounds.width} height={bounds.height} viewBox={`0 0 ${bounds.width} ${bounds.height}`}>
          <g className={styles.trails}><path data-trail="true" pathLength="1" d={`M ${bounds.width/2-100} ${bounds.height/2+43} l 70 -29`} /><path data-trail="true" pathLength="1" d={`M ${bounds.width/2-90} ${bounds.height/2+59} l 55 -24`} /></g>
          <rect data-base="true" width={bounds.width} height={bounds.height} rx="16" className={styles.base} />
          {[
            `0,0 ${bounds.width/2},0 0,${bounds.height}`,
            `0,${bounds.height} ${bounds.width/2},0 ${bounds.width/2},${bounds.height}`,
            `${bounds.width/2},${bounds.height} ${bounds.width/2},0 ${bounds.width},${bounds.height}`,
            `${bounds.width},${bounds.height} ${bounds.width/2},0 ${bounds.width},0`,
          ].map((points,index)=><polygon key={index} data-face="true" points={points} className={`${styles.face} ${styles[`face${index}`]}`} />)}
      </svg>
      </div>
    </div></div>, document.body)}
  </>;
});
