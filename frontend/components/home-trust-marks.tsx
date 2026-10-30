import { Icon } from "./icons";

/** Reserved slots. Replace the placeholder with each domain's official badge. */
export function HomeTrustMarks() {
  return (
    <aside className="home-trust-marks" aria-label="جایگاه نمادها و درگاه پرداخت">
      <div className="home-trust-slot" data-mark="enamad" data-home-enter="trust-first">
        <span className="home-trust-slot-frame" aria-hidden="true">
          <span className="home-trust-slot-monogram">e</span>
        </span>
        <strong>اینماد</strong>
        <span className="home-trust-slot-caption">جایگاه لوگو</span>
      </div>
      <div className="home-trust-slot" data-mark="zarinpal" data-home-enter="trust-last">
        <span className="home-trust-slot-frame" aria-hidden="true">
          <Icon name="shield" size={24} />
        </span>
        <strong>درگاه بانکی</strong>
        <span className="home-trust-slot-caption">جایگاه لوگو</span>
      </div>
    </aside>
  );
}
