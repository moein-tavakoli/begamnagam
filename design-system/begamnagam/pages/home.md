# Home override — version0.8

The user requested a full-screen mobile flow through seven browser annotations.
Keep MASTER colors, illustration, local font and pill actions.

- Home contains an intro slide and a composer slide, with explicit Next/Back controls.
- Hide the home header, environment banner, promise strip and mobile bottom nav.
- Hide the shared footer below700px; retain navigation on other routes and desktop footer.
- Lock document scrolling only on the mobile home route. Keep each portrait screen within
  the viewport. Use the form panel as an overflow fallback for keyboard/landscape/zoom.
- Split writing, recipient, final preview and consent/payment into consecutive views.
- Verify the sender before drafting, preserving existing cross-account privacy resets.
- Selecting any topic immediately replaces the textarea with that topic example;
  retain editing and remove the separate example button. Do not auto-open the keyboard.
- Keep explicit demo disclosure in OTP, checkout and receipt.
- Preserve browser Back/hash deep links, focus, reduced motion and pinch zoom.
- No automatic slide advance or new carousel dependency. Touch gestures are supplemental
  to the visible buttons; physical-device gesture testing remains pending.
