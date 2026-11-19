"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { Composer } from "./composer";
import { ErrorBox, ServiceState } from "./feedback";
import styles from "./personal-share.module.css";

type Selection = { token: string; maskedPhone?: string; error?: string };

export function SharedMessage() {
  const { data } = useApp();
  const router = useRouter();
  const [token, setToken] = useState<string | null>();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const readToken = () => {
      const value = window.location.hash.slice(1);
      setToken(value.length === 32 && /^[0-9a-f]{32}$/.test(value) ? value : null);
    };
    readToken();
    window.addEventListener("hashchange", readToken);
    return () => window.removeEventListener("hashchange", readToken);
  }, []);

  useEffect(() => {
    if (!data?.authenticated || !token) return;
    const controller = new AbortController();
    void api<{ recipient_masked: string }>("/personal-share/resolve", {
      method: "POST", body: { share_token: token }, signal: controller.signal,
    }).then(result => {
      if (!controller.signal.aborted) setSelection({ token, maskedPhone: result.recipient_masked });
    }).catch(err => {
      if (!controller.signal.aborted) setSelection({ token, error: errorMessage(err) });
    });
    return () => controller.abort();
  }, [data?.authenticated, token, attempt]);

  const chosen = token && selection?.token === token ? selection : null;
  if (data?.authenticated && chosen?.maskedPhone) {
    return <Composer key={chosen.token} sharedRecipient={{ token: chosen.token, maskedPhone: chosen.maskedPhone }}
      onExit={() => router.push("/")} />;
  }

  return (
    <div className={`account-page wrap ${styles.page}`}>
      <div className="account-heading">
        <h1>برای صاحب این لینک پیام بنویس</h1>
        <p>شمارهٔ خودت رو تأیید کن تا مقصد پیام خودکار انتخاب بشه.</p>
      </div>
      <div className="account-card">
        <ServiceState />
        {token && data && !data.authenticated && <AuthGate purpose="با شمارهٔ خودت وارد شو." />}
        {token && data?.authenticated && !chosen && <p className="service-loading" role="status">در حال انتخاب مقصد پیام…</p>}
        {chosen?.error && <ErrorBox message={chosen.error}>
          <button type="button" className="text-button" onClick={() => { setSelection(null); setAttempt(value => value + 1); }}>تلاش دوباره</button>
        </ErrorBox>}
        {token === null && <ErrorBox message="لینک ناقص است. آدرس کامل را از صاحب لینک بگیر." />}
        <Link href="/" className={`text-button ${styles.back}`}>صفحهٔ اصلی</Link>
      </div>
    </div>
  );
}
