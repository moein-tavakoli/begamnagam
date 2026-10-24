"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, errorMessage, type Bootstrap } from "@/lib/api";

type AppContextValue = {
  data: Bootstrap | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  authenticate: (phone: string) => void;
};
const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api<Bootstrap>("/bootstrap"));
    } catch (error) {
      setData(null);
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);
  const authenticate = (phone: string) =>
    setData((current) =>
      current
        ? { ...current, authenticated: true, phone_masked: phone }
        : current,
    );
  return (
    <AppContext.Provider value={{ data, loading, error, reload, authenticate }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be inside AppProvider");
  return context;
}

export function EnvironmentBanner() {
  const { data, loading } = useApp();
  return (
    <div className={`environment-banner ${data?.demo_mode ? "is-demo" : ""}`}>
      <span className="status-dot" />
      {data?.demo_mode
        ? "نسخه آزمایشی محلی؛ هیچ پیامک واقعی یا برداشت وجهی انجام نمی‌شود."
        : loading
          ? "در حال بررسی اتصال به سرویس…"
          : !data
            ? "ارتباط با سرویس برقرار نیست. امکان ارسال فعلاً غیرفعال است."
            : "پیش از ارسال، متن نهایی و هزینه را بررسی کنید."}
    </div>
  );
}
