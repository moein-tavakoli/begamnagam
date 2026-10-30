"use client";

import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useApp } from "./app-provider";
import { ErrorBox } from "./feedback";
import { Icon } from "./icons";

export function HomeLogout() {
  const { data, reload } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!data?.authenticated) return null;
  async function logout() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api("/auth/logout", { method: "POST", body: {} });
      await reload();
    } catch (e) { setError(errorMessage(e)); setBusy(false); }
  }
  return <>
    {error && <div className="home-logout-error"><ErrorBox message={error} /></div>}
    <button type="button" className="home-logout" data-home-enter="logout" onClick={() => void logout()} disabled={busy}
      aria-label="خروج از حساب" aria-busy={busy} title="خروج از حساب">
      {busy ? <span className="spinner" aria-hidden="true" /> : <Icon name="logout" size={21} />}
    </button>
  </>;
}
