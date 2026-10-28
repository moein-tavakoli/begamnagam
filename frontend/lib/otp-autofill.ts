// A convenience only: verification still goes through the session-bound API.
// Unsupported/denied WebOTP must leave typing, paste and keyboard autofill usable.
export function listenForSmsCode(onCode: (code: string) => void): () => void {
  const noop = () => {};
  try {
    if (typeof window === "undefined" || !window.isSecureContext ||
        !("OTPCredential" in window) || typeof navigator.credentials?.get !== "function") return noop;

    const controller = new AbortController();
    const stop = () => {
      controller.abort();
      window.clearTimeout(timeout);
      window.removeEventListener("pagehide", stop);
    };
    const timeout = window.setTimeout(stop, 60_000);
    window.addEventListener("pagehide", stop, { once: true });
    try {
      const options: CredentialRequestOptions & { otp: { transport: ["sms"] } } = {
        otp: { transport: ["sms"] }, signal: controller.signal,
      };
      void navigator.credentials.get(options).then(credential => {
        if (controller.signal.aborted) return;
        const code = (credential as (Credential & { code?: unknown }) | null)?.code;
        stop();
        if (typeof code === "string" && /^[0-9]{6}$/.test(code)) onCode(code);
      }).catch(stop);
    } catch {
      stop();
    }
    return stop;
  } catch {
    return noop;
  }
}
