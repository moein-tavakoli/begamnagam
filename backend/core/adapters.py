"""Provider boundaries for local development. Intentionally contains no HTTP SDK."""
from dataclasses import dataclass
from uuid import UUID


class AdapterDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterResult:
    reference: str
    status: str
    environment: str = "demo"


class DemoPaymentAdapter:
    def verify(self, *, attempt_id: UUID, amount_toman: int) -> AdapterResult:
        if amount_toman <= 0:
            raise ValueError("amount_toman must be positive")
        return AdapterResult(reference=f"demo-payment-{attempt_id}", status="verified")


class DemoSMSAdapter:
    def submit(self, *, submission_id: UUID) -> AdapterResult:
        # No phone or private body belongs in the queue/adapter result.
        return AdapterResult(reference=f"demo-message-{submission_id}", status="delivered_demo")


def payment_adapter(name: str):
    if name != "demo":
        raise AdapterDisabled("Only the demo payment adapter is available")
    return DemoPaymentAdapter()


def sms_adapter(name: str):
    if name != "demo":
        raise AdapterDisabled("Only the demo SMS adapter is available")
    return DemoSMSAdapter()
