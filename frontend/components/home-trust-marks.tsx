import { Icon } from "./icons";

// Keep the official, static embed verbatim, including its referrer policies.
const enamadBadge = {
  __html: "<a referrerpolicy='origin' target='_blank' href='https://trustseal.enamad.ir/?id=8406583&Code=cr266t1ffs6ZtJuurvP5qq86lSY8HlrK'><img referrerpolicy='origin' src='https://trustseal.enamad.ir/logo.aspx?id=8406583&Code=cr266t1ffs6ZtJuurvP5qq86lSY8HlrK' alt='' style='cursor:pointer' code='cr266t1ffs6ZtJuurvP5qq86lSY8HlrK'></a>",
};

export function HomeTrustMarks() {
  return (
    <aside className="home-trust-marks" aria-label="جایگاه نمادها و درگاه پرداخت">
      <div className="home-trust-slot" data-mark="enamad" data-home-enter="trust-first">
        <div className="home-enamad-badge" aria-label="نماد اعتماد الکترونیکی" dangerouslySetInnerHTML={enamadBadge} />
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
