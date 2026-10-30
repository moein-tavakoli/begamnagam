"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";

export function ExampleFilters({ groups, value, onChange }: {
  groups: { id: number; label: string }[]; value: number | null; onChange: (id: number | null) => void;
}) {
  const rail = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ previous: false, next: false });
  const signature = groups.map(group => `${group.id}:${group.label}`).join("|");
  useEffect(() => {
    const element = rail.current;
    if (!element) return;
    const measure = () => {
      const bounds = element.getBoundingClientRect();
      const first = element.firstElementChild?.getBoundingClientRect(), last = element.lastElementChild?.getBoundingClientRect();
      const style = getComputedStyle(element), rtl = style.direction === "rtl";
      const left = bounds.left + parseFloat(style.paddingLeft), right = bounds.right - parseFloat(style.paddingRight);
      const previous = !!first && (rtl ? first.right > right + 2 : first.left < left - 2);
      const next = !!last && (rtl ? last.left < left - 2 : last.right > right + 2);
      setEdges(current => current.previous === previous && current.next === next ? current : { previous, next });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    for (const child of element.children) observer.observe(child);
    element.addEventListener("scroll", measure, { passive: true });
    measure();
    return () => { observer.disconnect(); element.removeEventListener("scroll", measure); };
  }, [signature]);

  function move(next: boolean) {
    const element = rail.current;
    if (!element) return;
    const direction = getComputedStyle(element).direction === "rtl" ? -1 : 1;
    element.scrollBy({ left: (next ? 1 : -1) * direction * element.clientWidth * .75,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }

  return <div className="example-carousel" role="group" aria-label="دسته‌بندی پیام‌های نمونه">
    <div className="example-carousel-row">
      <button type="button" className="example-scroll previous" aria-label="دسته‌های قبلی" disabled={!edges.previous} onClick={() => move(false)}><Icon name="arrow" size={15} /></button>
      <div className="example-filters" ref={rail} aria-label="فهرست دسته‌ها">
        <button type="button" aria-pressed={value === null} onClick={() => onChange(null)}>همه</button>
        {groups.map(group => <button key={group.id} type="button" aria-pressed={value === group.id} onClick={() => onChange(group.id)}>{group.label}</button>)}
      </div>
      <button type="button" className="example-scroll next" aria-label="دسته‌های بعدی" disabled={!edges.next} onClick={() => move(true)}><Icon name="arrow" size={15} /></button>
    </div>
    {(edges.previous || edges.next) && <span className="example-swipe-hint">برای دیدن دسته‌های بیشتر، بکش یا از فلش‌ها استفاده کن.</span>}
  </div>;
}
