(() => {
  const opaque = name => /^(id|username|password|password1|password2|old_password|new_password1|new_password2|csrfmiddlewaretoken|token|signature|authority|status|category|message_tone|source_mode|source)$|_(id|token|signature|key|hash|digest|cipher|version)$/i.test(name);
  const latin = value => value.replace(/[۰-۹٠-٩０-９]/g, digit => {
    const code = digit.charCodeAt(0);
    return String(code >= 65296 ? code - 65296 : code >= 1776 ? code - 1776 : code - 1632);
  });
  const seen = new WeakSet();
  function normalize(input) {
    if (input.disabled || input.readOnly || input.type === "password" || opaque(input.name)) return;
    const kind = input.dataset.digitInput;
    const convert = text => kind === "number" ? latin(text).replace(/[\s,٬]/g, "").replace(/٫/g, ".")
      : kind === "date" ? latin(text).replace(/\//g, "-").trim() : latin(text);
    const original = input.value, next = convert(original);
    if (next !== original) {
      const start = input.selectionStart, end = input.selectionEnd;
      input.value = next;
      if (start !== null && end !== null) input.setSelectionRange(convert(original.slice(0, start)).length, convert(original.slice(0, end)).length);
    }
    if (!kind) return;
    const probe = document.createElement("input");
    probe.type = kind;
    for (const key of ["min", "max", "step"]) if (input.hasAttribute(key)) probe.setAttribute(key, input.getAttribute(key));
    probe.required = input.required; probe.defaultValue = input.defaultValue; probe.value = next;
    const valid = probe.validity;
    input.setCustomValidity(!next && input.required ? "این مقدار را وارد کن."
      : next && !probe.value ? (kind === "date" ? "تاریخ معتبر به شکل سال-ماه-روز وارد کن." : "عدد معتبر وارد کن.")
      : valid.rangeUnderflow ? "مقدار از حداقل مجاز کمتر است."
      : valid.rangeOverflow ? "مقدار از حداکثر مجاز بیشتر است."
      : valid.stepMismatch ? "مقدار با گام مجاز هماهنگ نیست." : "");
  }
  function prepare(root) {
    const fields = root.matches?.("input,textarea") ? [root] : root.querySelectorAll?.("input,textarea") ?? [];
    for (const input of fields) {
      if (seen.has(input) || input.type === "password" || opaque(input.name)) continue;
      if (input.type === "number" || input.type === "date") {
        input.dataset.digitInput = input.type; input.type = "text"; input.inputMode = "numeric";
      }
      if (!["text", "tel", "search", "email", "url", "textarea"].includes(input.type)) continue;
      seen.add(input);
      if (input.dataset.digitInput) normalize(input);
      input.addEventListener("input", () => normalize(input));
      input.addEventListener("change", () => normalize(input));
    }
  }
  prepare(document);
  document.addEventListener("submit", event => { for (const field of event.target.querySelectorAll("input,textarea")) if (seen.has(field)) normalize(field); }, true);
  document.addEventListener("reset", event => queueMicrotask(() => { for (const field of event.target.querySelectorAll("input,textarea")) if (seen.has(field)) normalize(field); }));
  new MutationObserver(rows => { for (const row of rows) for (const node of row.addedNodes) if (node.nodeType === 1) prepare(node); }).observe(document.body, {childList: true, subtree: true});
})();
