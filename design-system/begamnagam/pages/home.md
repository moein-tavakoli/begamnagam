# Home override — version0.8.9

The user requested a full-screen mobile flow through seven browser annotations.
Keep MASTER colors, illustration, local font and pill actions.

- Home contains an intro slide and a composer slide, with explicit Next/Back controls.
- Hide the home header, environment banner, promise strip and mobile bottom nav.
- Hide the shared footer below700px; retain navigation on other routes and desktop footer.
- Lock document scrolling only on the mobile home route. Keep each portrait screen within
  the viewport. Use the form panel as an overflow fallback for keyboard/landscape/zoom.
- Use two composer steps: writing, then recipient and final review with consent/payment.
- Keep the recipient input on the final review screen. Prepare a bound preview there;
  changing the normalized number invalidates that preview and consent before sending.
- The final review contains the recipient, full reviewed text, price/segments,
  required consent and send action together. Do not add another confirmation screen.
- Show remaining one-time free credits in the draft and account history. Label a
  free quote and its confirmation as free; demo free actions retain the demo label.
- Free checkout has no gateway step. A stale free quote must be reviewed afresh;
  never turn it into a paid action automatically. Preserve the mobile panel fallback.
- If payment fails, retry the same created order; disable edits once that order exists.
- Hide the authenticated sender badge in the recipient form, retaining authentication.
- Convert Persian/Arabic digits on input in all phone/OTP fields; keep leading zeroes
  and the existing normalization immediately before sending to the API.
- Verify the sender before drafting, preserving existing cross-account privacy resets.
- Selecting any topic immediately replaces the textarea with that topic example;
  retain editing and remove the separate example button. Do not auto-open the keyboard.
- Keep the character counter below the textarea at its existing edge. Show privacy
  and respectful-writing tips in a separate inline warning below it, associated with
  the textarea. Use note semantics for persistent guidance, not an interrupting alert.
- Remove the draft rewrite-mode strip and the old recipient-stage teaser sentence.
- Keep provider names and AI-generation wording out of composer copy; preserve the
  privacy tip and final-text review. While preparing a custom rewrite, show the
  modal loading state with «ممکن است تا ۲۰ ثانیه طول بکشد». Close on completion or
  failure, retain error focus and prevent duplicate preview submissions.
- Identify demo checkout in the send button and receipt; omit the separate demo explanation box on final review as requested. Keep the OTP disclosure.
- Preserve browser Back/hash deep links, focus, reduced motion and pinch zoom.
- Desktop at1024px and above reserves two compact badge slots below the hero
  illustration for eNAMAD and Zarinpal. Until official domain-specific badges are
  supplied, label both as logo placeholders; do not imply an issued certificate
  or active payment gateway. Keep them out of the composer and mobile intro.
- No automatic slide advance or new carousel dependency. Touch gestures are supplemental
  to the visible buttons; physical-device gesture testing remains pending.
