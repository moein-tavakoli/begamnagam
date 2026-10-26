export type Category = {
  id: string;
  label: string;
  description: string;
  example: string;
};
export type Bootstrap = {
  demo_mode: boolean;
  otp_is_real?: boolean;
  authenticated: boolean;
  phone_masked?: string;
  free_sends_remaining?: number;
  free_sends_total?: number;
  free_sends_earned_total?: number;
  price_toman: number;
  categories: Category[];
  rewrite_mode: string;
  payment_backend?: string;
  recent_auth?: boolean;
  support_contact?: string;
  session_identity?: string;
};
export type Preview = {
  is_free?: boolean;
  preview_id: string;
  terms_version?: string;
  rewritten_text: string;
  full_sms?: string;
  sms_segments?: number;
  price_toman: number;
  expires_at: string;
  moderation_mode: string;
};
export type Order = {
  is_free?: boolean;
  id: string;
  status: string;
  amount_toman: number;
  payment_mode?: string;
  financial_status?: string;
  delivery_status?: string;
  status_reason?: { code: string; message: string } | null;
};
export type Message = Order & {
  recipient_masked: string;
  text: string;
  created_at: string;
};

export class ApiError extends Error {
  code: string;
  fields?: Record<string, string | string[]>;
  constructor(
    message: string,
    code = "network_error",
    fields?: Record<string, string | string[]>,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.fields = fields;
  }
}

const requestUnavailable = "درخواست فعلاً انجام نشد؛ کمی بعد دوباره تلاش کن.";

// randomUUID is unavailable on a phone opening a local HTTP LAN address.
// getRandomValues remains available there and keeps retry keys unpredictable.
export function createIdempotencyKey(): string {
  if (typeof globalThis.crypto.randomUUID === "function")
    return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function csrfToken(): string {
  if (typeof document === "undefined") return "";
  return (
    document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")
      .slice(1)
      .join("=") || ""
  );
}

export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    idempotencyKey?: string;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const method = options.method || "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRFToken"] = decodeURIComponent(csrfToken());
  }
  if (options.idempotencyKey)
    headers["Idempotency-Key"] = options.idempotencyKey;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, path === '/messages/preview' ? 25000 : 15000);
  const cancel = () => controller.abort();
  if (options.signal?.aborted) cancel();
  options.signal?.addEventListener("abort", cancel, { once: true });
  try {
    const response = await fetch(`/api/v1${path}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers,
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        (response.status >= 500 ? requestUnavailable : data?.error?.message) ||
          "سرویس در دسترس نیست. چند لحظه دیگر دوباره تلاش کنید.",
        data?.error?.code || "service_error",
        response.status >= 500 ? undefined : data?.error?.fields,
      );
    }
    if (data === null)
      throw new ApiError(
        "پاسخ سرویس معتبر نیست. دوباره تلاش کنید.",
        "invalid_response",
      );
    if(["/auth/logout", "/auth/verify-otp"].includes(path) && typeof window !== "undefined") window.dispatchEvent(new Event("privacy-reset"));
    return data as T;
  } catch (error) {
    if (timedOut)
      throw new ApiError(
        "پاسخ سرویس بیش از حد طول کشید. چند لحظه دیگر دوباره تلاش کنید.",
        "request_timeout",
      );
    if (
      error instanceof ApiError ||
      (error instanceof DOMException && error.name === "AbortError")
    )
      throw error;
    throw new ApiError(
      "ارتباط با سرویس برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.",
    );
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", cancel);
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : requestUnavailable;
}


export function approvedPaymentRedirect(value: string, demo: boolean): string {
  const url = new URL(value);
  if (url.protocol === 'https:' && ['www.zarinpal.com', 'sandbox.zarinpal.com'].includes(url.hostname) && url.pathname.startsWith('/pg/StartPay/')) return url.href;
  if (demo && url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) && url.pathname.startsWith('/pg/StartPay/')) return url.href;
  throw new ApiError('نشانی درگاه معتبر نیست؛ از سابقه وضعیت را بررسی کن.', 'invalid_gateway');
}
