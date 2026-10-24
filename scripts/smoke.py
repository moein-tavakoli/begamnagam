#!/usr/bin/env python3
"""End-to-end demo check through the web proxy. Never calls a live provider."""
import http.cookiejar
import json
import os
import secrets
import time
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import uuid

local_values = {}
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            local_values[key.strip()] = value.strip().strip("\"'")
web_port = os.getenv("WEB_PORT", local_values.get("WEB_PORT", "3000"))
BASE = os.getenv("SMOKE_BASE_URL", f"http://localhost:{web_port}").rstrip("/")
parsed = urllib.parse.urlparse(BASE)
if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Smoke tests are restricted to loopback hosts.")


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, path, data=None, key=None, expected=200):
        headers = {"Accept": "application/json", "Origin": BASE}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["X-CSRFToken"] = next((c.value for c in self.jar if c.name == "csrftoken"), "")
        if key:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(
            BASE + "/api/v1" + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
        )
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read().decode()
        assert response.code == expected, f"{path}: HTTP {response.code}, expected {expected}: {raw[:300]}"
        return json.loads(raw)

    def login(self, phone):
        challenge = self.call("/auth/request-otp", {"phone": phone})
        code = challenge.get("debug_code")
        assert code, "Expected demo OTP; refusing live-mode authentication."
        result = self.call("/auth/verify-otp", {"challenge_id": challenge["challenge_id"], "code": code})
        assert result["authenticated"] is True


def main():
    sender = Client()
    bootstrap = sender.call("/bootstrap")
    assert bootstrap["demo_mode"] is True, "Smoke test refuses non-demo instances."
    assert bootstrap["price_toman"] > 0
    assert {"appreciation", "encouragement", "congratulations"}.issubset({item["id"] for item in bootstrap["categories"]})
    # These values exist only in the local demo database. No SMS adapter is live.
    suffix = str(secrets.randbelow(10**7)).zfill(7)
    sender_phone = "0991" + suffix
    recipient_phone = "0992" + suffix
    sender.login(sender_phone)
    preview = sender.call("/messages/preview", {"category": "encouragement", "text": "تلاش و همراهی شما ارزشمند است."})
    assert preview["rewritten_text"]
    key = str(uuid.uuid4())
    order = sender.call("/orders", {"preview_id": preview["preview_id"], "recipient_phone": recipient_phone}, key=key)
    repeated = sender.call("/orders", {"preview_id": preview["preview_id"], "recipient_phone": recipient_phone}, key=key)
    assert repeated["id"] == order["id"], "Duplicate checkout created a new order."
    sender.call(f"/orders/{order['id']}/pay-demo", {})
    for _ in range(25):
        result = sender.call(f"/orders/{order['id']}")
        if result["status"] in {"sent_demo", "delivered_demo", "simulated"}:
            break
        time.sleep(1)
    else:
        raise AssertionError(f"Worker did not process outbox: {result['status']}")
    history = sender.call("/messages")["results"]
    assert any(item["id"] == order["id"] for item in history)
    assert recipient_phone not in json.dumps(history), "History exposed a full recipient phone."
    receiver = Client()
    receiver.call("/bootstrap")
    receiver.login(recipient_phone)
    receiver.call("/preferences", {"blocked": True})
    assert receiver.call("/preferences")["blocked"] is True
    # A second session cannot inspect the sender's order.
    receiver.call(f"/orders/{order['id']}", expected=404)
    print(f"PASS at {BASE}: CSRF, OTP, preview, idempotent checkout, demo payment, message processing, history, opt-out, ownership.")


if __name__ == "__main__":
    main()
