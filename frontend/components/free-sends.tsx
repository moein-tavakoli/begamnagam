"use client";

import { useApp } from "./app-provider";
import { Icon } from "./icons";

export function FreeSendsBalance({ compact = false }: { compact?: boolean } = {}) {
  const { data } = useApp();
  if (!data?.authenticated || data.free_sends_remaining === undefined) return null;
  const number = new Intl.NumberFormat("fa-IR");
  return (
    <p className={`free-sends-balance small${compact ? " is-compact" : ""}`} role="status">
      {!compact && <Icon name="sparkle" size={17} />}
      {compact ? "باقیمانده:" : "ارسال رایگان باقی‌مانده:"} {number.format(data.free_sends_remaining)} از {number.format(data.free_sends_total ?? 3)}
    </p>
  );
}
