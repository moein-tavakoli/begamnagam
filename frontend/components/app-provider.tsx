"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
} from "react";
import { api, ApiError, errorMessage, type Bootstrap } from "@/lib/api";
import { openSessionChannel } from "@/lib/browser-capabilities";
import { identitySettingsChanged } from "@/lib/identity-consent";
import { actionFromFragment } from "@/lib/recipient-links";

type AppContextValue = {
  data: Bootstrap | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  verifyOtp: (challenge: string, code: string, feedback: (result: { authenticated: boolean }) => Promise<void>) => Promise<void>;
};
const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const generation=useRef(0);
  const identity=useRef<string|undefined>(undefined);
  const messageVisibility=useRef<string|undefined>(undefined);
  const bootstrapRequest=useRef<AbortController | null>(null);
  const authenticationInFlight=useRef(false);
  const resumeAfterAuthentication=useRef(false);
  const [privacyEpoch,setPrivacyEpoch]=useState(0);
  const [privacyPending,setPrivacyPending]=useState(false);
  const [data, setData] = useState<Bootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loadBootstrap = useCallback(async ({ keepGuestOnFailure = false } = {}) => {
    const current=++generation.current;
    bootstrapRequest.current?.abort();
    const controller=new AbortController();
    bootstrapRequest.current=controller;
    if(!keepGuestOnFailure){setLoading(true);setError("");}
    try {
      const result=await api<Bootstrap>("/bootstrap", { signal: controller.signal });
      if(current===generation.current) {
        if(identity.current !== result.session_identity || messageVisibility.current !== result.message_visibility_revision) setPrivacyEpoch(v=>v+1);
        identity.current=result.session_identity;
        messageVisibility.current=result.message_visibility_revision;
        setData(result);
        setError("");
        if (!document.hidden) setPrivacyPending(false);
        return result;
      }
    } catch (error) {
      if(current===generation.current && !controller.signal.aborted){
        if(keepGuestOnFailure && !identity.current)return;
        identity.current=undefined;
        messageVisibility.current=undefined;
        setPrivacyEpoch(v=>v+1);
        setData(null);
        setPrivacyPending(false);
        setError(errorMessage(error));
      }
    } finally {
      if(current===generation.current) setLoading(false);
    }
  }, []);
  const reload=useCallback(async()=>{if(!authenticationInFlight.current)await loadBootstrap();},[loadBootstrap]);
  const verifyOtp=useCallback(async(challenge: string, code: string, feedback: (result: { authenticated: boolean }) => Promise<void>)=>{
    if(authenticationInFlight.current)return;
    authenticationInFlight.current=true;
    generation.current+=1;
    bootstrapRequest.current?.abort();
    setLoading(false);
    try {
      const verified=await api<{authenticated:boolean}>("/auth/verify-otp",{
        method:"POST",body:{challenge_id:challenge,code},beforeSessionReset:feedback,
      });
      if(!verified.authenticated)throw new ApiError("تأیید شماره انجام نشد؛ دوباره تلاش کن.","otp_unverified");
      // Install the fresh authenticated snapshot and its identity together.
      // Never unmount the OTP form into an empty/anonymous bootstrap in between.
      const session=await loadBootstrap();
      if(!session?.authenticated)throw new ApiError("کد تأیید شد، اما نشست ورود برقرار نشد؛ دوباره کد بگیر.","session_unconfirmed");
    } finally {
      authenticationInFlight.current=false;
      if(resumeAfterAuthentication.current && !document.hidden){
        resumeAfterAuthentication.current=false;
        await loadBootstrap();
      }
    }
  },[loadBootstrap]);
  useEffect(() => {
    void reload();
  }, [reload]);
  useEffect(()=>{
    const channel=openSessionChannel();
    let pendingReset: Promise<void> | undefined;
    const clear=()=>{pendingReset=undefined;generation.current+=1;bootstrapRequest.current?.abort();identity.current=undefined;messageVisibility.current=undefined;setData(null);setPrivacyEpoch(v=>v+1);void loadBootstrap();};
    const local=(event: Event)=>{
      channel?.postMessage('session-changed');
      const settled=(event as CustomEvent<{settled?: Promise<void>}>).detail?.settled;
      if(!settled){clear();return;}
      // Keep only this form alive for bounded OTP feedback; peers were notified above.
      const current=++generation.current;
      pendingReset=settled;
      void settled.then(()=>{
        if(pendingReset===settled && current===generation.current){
          pendingReset=undefined;
          if(!authenticationInFlight.current)void loadBootstrap();
        }
      });
    };
    const hiddenMessage=()=>{
      channel?.postMessage('message-hidden');
      // The initiating history removes its row; other retained views are reset
      // when the server's account-scoped revision arrives.
      void reload();
    };
    const recipientIdentityView=()=>{
      if(window.location.pathname !== '/r')return false;
      const route=actionFromFragment(window.location.hash.slice(1));
      return !!route && (!route.action || route.action==='identity');
    };
    const refreshIdentitySetting=()=>{
      if(!identity.current && !recipientIdentityView())return;
      // Remove a displayed number and abort pending reads on a change hint.
      // The server's next response decides whether the panel can reappear.
      setData(current=>current?.identity_requests_enabled ? {...current,identity_requests_enabled:false} : current);
      if(document.hidden || pendingReset || authenticationInFlight.current)return;
      if(identity.current)void reload();
      else void loadBootstrap({keepGuestOnFailure:true});
    };
    const identitySettingChanged=()=>{
      channel?.postMessage(identitySettingsChanged);
      refreshIdentitySetting();
    };
    const remote=(event:MessageEvent)=>{
      if(event.data==='session-changed' || event.data==='message-hidden')clear();
      else if(event.data===identitySettingsChanged)refreshIdentitySetting();
    };
    const restore=(event:PageTransitionEvent)=>{if(event.persisted)clear();};
    const focus=()=>{
      if(document.hidden)return;
      if(authenticationInFlight.current){resumeAfterAuthentication.current=true;return;}
      if(pendingReset)return;
      resumeAfterAuthentication.current=false;
      if(identity.current) setPrivacyPending(true);
      void reload();
    };
    const visibility=()=>{
      if(document.hidden){
        if(identity.current) setPrivacyPending(true);
        if(!authenticationInFlight.current && !pendingReset){
          generation.current+=1;
          bootstrapRequest.current?.abort();
        }
      } else focus();
    };
    // Refresh open SMS menus as well as verified sessions. A settings change
    // from another device cannot broadcast to this tab.
    const timer=setInterval(()=>{
      if(document.hidden || pendingReset || authenticationInFlight.current)return;
      if(identity.current)void reload();
      else if(recipientIdentityView())void loadBootstrap({keepGuestOnFailure:true});
    },30000);
    window.addEventListener('privacy-reset',local);
    window.addEventListener('message-visibility-changed',hiddenMessage);
    window.addEventListener(identitySettingsChanged,identitySettingChanged);
    window.addEventListener('pageshow',restore);
    window.addEventListener('focus',focus);
    document.addEventListener('visibilitychange',visibility);
    channel?.addEventListener('message',remote);
    return ()=>{pendingReset=undefined;clearInterval(timer);window.removeEventListener('privacy-reset',local);window.removeEventListener('message-visibility-changed',hiddenMessage);window.removeEventListener(identitySettingsChanged,identitySettingChanged);window.removeEventListener('pageshow',restore);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',visibility);channel?.close();};
  },[reload,loadBootstrap]);
  return (
    <AppContext.Provider value={{ data, loading, error, reload, verifyOtp }}>
      {privacyPending && <p role="status" className="service-loading">در حال بررسی دسترسی…</p>}
      <div key={privacyEpoch} className="app-shell" hidden={privacyPending}>{children}</div>
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
        ? data.otp_is_real
          ? "کد ورود واقعی است؛ پرداخت و ارسال پیام به گیرنده آزمایشی‌اند."
          : "نسخه آزمایشی محلی؛ هیچ پیامک واقعی یا برداشت وجهی انجام نمی‌شود."
        : loading
          ? "در حال بررسی اتصال به سرویس…"
          : !data
            ? "ارتباط با سرویس برقرار نیست. امکان ارسال فعلاً غیرفعال است."
            : "پیش از ارسال، متن نهایی و هزینه را بررسی کنید."}
    </div>
  );
}
