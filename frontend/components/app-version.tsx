import { version } from "../package.json";

export function AppVersion() {
  return <small className="app-version" aria-label="نسخهٔ نرم‌افزار">
    نسخه <bdi dir="ltr">{version}</bdi>{process.env.NODE_ENV === "development" ? " · توسعه" : ""}
  </small>;
}
