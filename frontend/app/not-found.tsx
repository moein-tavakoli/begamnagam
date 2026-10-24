import Link from "next/link";
import { Icon } from "@/components/icons";
export default function NotFound() {
  return (
    <div className="not-found wrap">
      <Icon name="leaf" size={60} />
      <span className="eyebrow">۴۰۴</span>
      <h1>این صفحه اینجا نیست.</h1>
      <p>می‌تونی از صفحه اصلی، دوباره شروع کنی.</p>
      <Link href="/" className="button primary">
        بازگشت به خانه <Icon name="arrow" size={18} />
      </Link>
    </div>
  );
}
