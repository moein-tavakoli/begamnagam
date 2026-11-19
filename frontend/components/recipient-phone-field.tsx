import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { getContactPicker, pickRecipientNumbers } from "@/lib/contact-picker";
import styles from "./recipient-phone-field.module.css";

type PickerState =
  | { kind: "pending" | "filled" }
  | { kind: "choices"; numbers: string[] }
  | { kind: "notice"; message: string };

export function RecipientPhoneField({ value, onChange, active, disabled, readOnly, error }: {
  value: string;
  onChange: (number: string) => void;
  active: boolean;
  disabled: boolean;
  readOnly: boolean;
  error?: string;
}) {
  const [supportsPicker, setSupportsPicker] = useState(false);
  const [pickerState, setPickerState] = useState<PickerState | null>(null);
  const pendingRequest = useRef<symbol | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const editable = active && !disabled && !readOnly;
  const picking = pickerState?.kind === "pending";
  const choices = editable && pickerState?.kind === "choices" ? pickerState.numbers : null;

  useEffect(() => {
    setSupportsPicker(getContactPicker() !== null && typeof window.HTMLDialogElement?.prototype.showModal === "function");
  }, []);

  useLayoutEffect(() => {
    if (!editable) setPickerState(null);
    return () => { pendingRequest.current = null; };
  }, [editable]);

  useLayoutEffect(() => {
    if (!choices || !dialog.current) return;
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, [choices]);

  function editNumber(number: string) {
    pendingRequest.current = null;
    setPickerState(null);
    onChange(number);
  }

  function closeChoices() {
    dialog.current?.close();
    setPickerState(null);
    trigger.current?.focus({ preventScroll: true });
  }

  function useNumber(number: string) {
    setPickerState({ kind: "filled" });
    onChange(number);
  }

  async function openPicker() {
    if (!editable || pendingRequest.current) return;
    const picker = getContactPicker();
    if (!picker) return;

    const request = Symbol();
    pendingRequest.current = request;
    setPickerState({ kind: "pending" });
    try {
      const numbers = await pickRecipientNumbers(picker);
      if (pendingRequest.current !== request) return;
      if (numbers === null) setPickerState(null);
      else if (numbers.length === 1) useNumber(numbers[0]);
      else if (numbers.length > 1) setPickerState({ kind: "choices", numbers });
      else setPickerState({
        kind: "notice",
        message: "شمارهٔ موبایل معتبر از این مخاطب دریافت نشد. می‌تونی شماره رو دستی وارد کنی.",
      });
    } catch (error) {
      if (pendingRequest.current !== request) return;
      setPickerState(error instanceof DOMException && error.name === "AbortError" ? null : {
        kind: "notice",
        message: "مخاطبین باز نشد. دوباره تلاش کن یا شماره رو دستی وارد کن.",
      });
    } finally {
      if (pendingRequest.current === request) pendingRequest.current = null;
    }
  }

  return (
    <>
      <label htmlFor="quote-recipient">شماره موبایل گیرنده</label>
      <div className={styles.row}>
        <input id="quote-recipient" className="phone-number-input" type="tel" inputMode="numeric" dir="ltr"
          maxLength={11} minLength={11} pattern="09[0-9]{9}"
          value={value}
          onChange={event => editNumber(event.target.value)}
          onPaste={event => {
            const input = event.currentTarget;
            if (input.readOnly || input.disabled) return;
            if (input.selectionStart === 0 && input.selectionEnd === input.value.length) {
              event.preventDefault();
              editNumber(event.clipboardData.getData("text"));
            }
          }}
          autoComplete="off" placeholder="09123456789" disabled={disabled}
          readOnly={readOnly}
          aria-invalid={!!error}
          aria-describedby={error ? "quote-recipient-error" : undefined} />
        {supportsPicker && !readOnly && (
          <button ref={trigger} type="button" className={`button ghost ${styles.trigger}`}
            aria-haspopup="dialog" aria-busy={picking || undefined} aria-disabled={picking || undefined}
            disabled={disabled} onClick={openPicker}>
            انتخاب از مخاطبین
          </button>
        )}
      </div>
      {error && <p className="field-error" id="quote-recipient-error">{error}</p>}
      <div role="status">
        {pickerState?.kind === "notice" && <p className="field-error">{pickerState.message}</p>}
        {pickerState?.kind === "filled" && <span className="sr-only">شمارهٔ مقصد وارد شد.</span>}
      </div>
      {choices && (
        <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId}
          onCancel={event => { event.preventDefault(); closeChoices(); }}>
          <h2 id={titleId}>انتخاب شمارهٔ موبایل</h2>
          <div className={styles.choices}>
            {choices.map(number => (
              <button key={number} type="button" className={`button ghost ${styles.number}`} dir="ltr"
                onClick={() => { closeChoices(); useNumber(number); }}>
                {number}
              </button>
            ))}
            <button type="button" className="text-button" onClick={closeChoices}>انصراف</button>
          </div>
        </dialog>
      )}
    </>
  );
}
