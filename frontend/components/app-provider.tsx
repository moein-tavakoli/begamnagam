"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
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
  const generation=useRef(0);
  const [privacyEpoch,setPrivacyEpoch]=useState(0);
  const [data, setData] = useState<Bootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    const current=++generation.current;
    setLoading(true);
    setError("");
    try {
      const result=await api<Bootstrap>("/bootstrap");
      if(current===generation.current) setData(result);
    } catch (error) {
      if(current===generation.current){setData(null);setError(errorMessage(error));}
    } finally {
      if(current===generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);
  useEffect(()=>{
    const clear=()=>{generation.current+=1;setData(null);setPrivacyEpoch(v=>v+1);};
    const restore=(event:PageTransitionEvent)=>{if(event.persisted){clear();void reload();}};
    window.addEventListener('privacy-reset',clear);
    window.addEventListener('pageshow',restore);
    return ()=>{window.removeEventListener('privacy-reset',clear);window.removeEventListener('pageshow',restore);};
  },[reload]);
  const authenticate = (phone: string) =>
    setData((current) =>
      current
        ? { ...current, authenticated: true, phone_masked: phone }
        : current,
    );
  return (
    <AppContext.Provider value={{ data, loading, error, reload, authenticate }}>
      <div key={privacyEpoch}>{children}</div>
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
