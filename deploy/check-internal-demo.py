"""Run through stdin in the CT backend. Synthetic OTP only; no provider network."""
import json
import os
import secrets
import time
import uuid

import django
django.setup()

from django.conf import settings
from django.test import Client, override_settings
from core.models import PaymentAttempt, SpendReservation

assert settings.DEMO_MODE and settings.INTERNAL_DEMO_HOST
assert settings.SMS_BACKEND == "console" and settings.PAYMENT_BACKEND == "demo"
assert settings.PROVIDER_NETWORK_MODE == "disabled"
before_otp = SpendReservation.objects.filter(kind="otp").count()
before_payment = PaymentAttempt.objects.count()
host = settings.INTERNAL_DEMO_HOST
sender = Client(enforce_csrf_checks=True, HTTP_HOST=host, HTTP_ORIGIN=settings.APP_BASE_URL)
receiver = Client(enforce_csrf_checks=True, HTTP_HOST=host, HTTP_ORIGIN=settings.APP_BASE_URL)


def call(client, path, data=None, key=None, expected=200):
    url = "/api/v1" + path
    if data is None:
        response = client.get(url, secure=True)
    else:
        headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
        if key:
            headers["HTTP_IDEMPOTENCY_KEY"] = key
        response = client.post(url, data=json.dumps(data), content_type="application/json", secure=True, **headers)
    assert response.status_code == expected, (path, response.status_code)
    return response.json()


def login(client, phone):
    # This override applies only to this diagnostic process, never to the service.
    with override_settings(OTP_BACKEND="demo", LOCAL_REAL_OTP_ENABLED=False):
        call(client, "/bootstrap")
        challenge = call(client, "/auth/request-otp", {"phone": phone})
        call(client, "/auth/verify-otp", {"challenge_id": challenge["challenge_id"], "code": challenge["debug_code"]})


suffix = str(secrets.randbelow(10**7)).zfill(7)
login(sender, "0991" + suffix)
assert call(sender, "/bootstrap")["free_sends_remaining"] == 3
preview = call(sender, "/messages/preview", {"category": "appreciation", "text": "از مهربانی و همراهی شما سپاسگزارم.", "recipient_phone": "0992" + suffix})
key = str(uuid.uuid4())
payload = {"preview_id": preview["preview_id"], "recipient_phone": "0992" + suffix,
           "consent": True, "terms_version": preview["terms_version"]}
order = call(sender, "/orders", payload, key)
assert order["is_free"] and order["amount_toman"] == 0
assert call(sender, "/orders", payload, key)["id"] == order["id"]
call(sender, f"/orders/{order['id']}/confirm-free", {})
for _ in range(45):
    result = call(sender, f"/orders/{order['id']}")
    if result["status"] == "delivered_demo":
        break
    time.sleep(1)
else:
    raise RuntimeError("Worker did not finish synthetic demo delivery")
assert call(sender, "/bootstrap")["free_sends_remaining"] == 2
assert any(item["id"] == order["id"] for item in call(sender, "/messages")["results"])
login(receiver, "0992" + suffix)
call(receiver, "/preferences", {"blocked": True})
assert call(receiver, "/preferences")["blocked"]
call(receiver, f"/orders/{order['id']}", expected=404)
assert SpendReservation.objects.filter(kind="otp").count() == before_otp
assert PaymentAttempt.objects.count() == before_payment
print(json.dumps({"result": "PASS", "checks": ["CSRF", "synthetic OTP", "3 free sends", "idempotency",
    "RabbitMQ/Celery delivery", "history", "opt-out", "ownership"], "delivery": "delivered_demo",
    "real_sms_requests": 0, "payment_attempts_created": 0}))
