export type Theme = "light" | "dark";
export const THEME_STORAGE_KEY = "begamnagam.theme";
export const THEME_COLORS = { light: "#f2eeff", dark: "#15111d" };

export function storedTheme(value: string | null): Theme | null {
  return value === "light" || value === "dark" ? value : null;
}

// Static, nonced code runs during HTML parsing, before React or the first paint.
export const THEME_INIT_SCRIPT = `(()=>{let t;try{t=localStorage.getItem('${THEME_STORAGE_KEY}')}catch{}if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.theme=t;const m=document.getElementById('app-theme-color')||document.head.appendChild(document.createElement('meta'));m.id='app-theme-color';m.name='theme-color';m.content=t==='dark'?'${THEME_COLORS.dark}':'${THEME_COLORS.light}'})()`;
