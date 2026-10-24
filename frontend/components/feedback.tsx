"use client";

import { useEffect, useRef } from "react";
import { Icon } from "./icons";
import { useApp } from "./app-provider";

export function ErrorBox({
  message,
  children,
  focus = true,
}: {
  message: string;
  children?: React.ReactNode;
  focus?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (message && focus) ref.current?.focus();
  }, [message, focus]);
  if (!message) return null;
  return (
    <div className="error-box" role="alert" ref={ref} tabIndex={-1}>
      <Icon name="info" size={20} />
      <div>
        <p>{message}</p>
        {children}
      </div>
    </div>
  );
}

export function ServiceState() {
  const { loading, error, reload } = useApp();
  if (loading)
    return (
      <p className="service-loading" role="status">
        <span className="spinner" /> در حال اتصال به سرویس…
      </p>
    );
  if (!error) return null;
  return (
    <ErrorBox message={error} focus={false}>
      <button
        className="text-button"
        type="button"
        onClick={() => void reload()}
      >
        <Icon name="refresh" size={16} /> تلاش دوباره
      </button>
    </ErrorBox>
  );
}

export function BusyButton({
  busy,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
    >
      {busy && <span className="spinner" />}
      {children}
    </button>
  );
}
