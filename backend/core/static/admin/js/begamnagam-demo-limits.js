document.querySelectorAll("[data-normalize-digits]").forEach(input => {
  input.addEventListener("input", () => {
    const start = input.selectionStart;
    const end = input.selectionEnd;
    input.value = input.value.replace(/[۰-۹٠-٩]/g, digit =>
      String(digit.charCodeAt(0) - (digit >= "۰" ? 0x06f0 : 0x0660)));
    if (start !== null && end !== null) input.setSelectionRange(start, end);
  });
});
