import { createContext, useCallback, useContext, useRef, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { MASKS, type MaskName } from "../lib/format";

export const Spin = () => <span className="spin" aria-hidden="true" />;

export function Chip({ tone = "neutral", children }: { tone?: string; children: ReactNode }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}

export function Alert({ tone = "bad", children }: { tone?: "bad" | "warn" | "ok" | "info"; children: ReactNode }) {
  return (
    <div className={`alert ${tone}`} role={tone === "bad" ? "alert" : "status"}>
      {children}
    </div>
  );
}

type FieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> & {
  id: string;
  label: string;
  value: string;
  onValue: (v: string) => void;
  cls?: string;
  hint?: ReactNode;
  error?: string;
  mask?: MaskName;
};

export function Field({ id, label, value, onValue, cls = "c6", hint, error, mask, ...rest }: FieldProps) {
  return (
    <div className={`field ${cls}`}>
      <label htmlFor={id}>{label}</label>
      <input
        {...rest}
        id={id}
        className={`input ${error ? "invalid" : ""}`}
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        onChange={(e) => onValue(mask ? MASKS[mask](e.target.value) : e.target.value)}
      />
      {error ? (
        <span className="err" id={`${id}-err`}>
          {error}
        </span>
      ) : hint ? (
        <span className="hint" id={`${id}-hint`}>
          {hint}
        </span>
      ) : null}
    </div>
  );
}

export function Select({
  id, label, value, onValue, options, cls = "c3", error,
}: {
  id: string; label: string; value: string; onValue: (v: string) => void;
  options: (string | [string, string])[]; cls?: string; error?: string;
}) {
  return (
    <div className={`field ${cls}`}>
      <label htmlFor={id}>{label}</label>
      <select id={id} className={`input ${error ? "invalid" : ""}`} value={value} onChange={(e) => onValue(e.target.value)}>
        {options.map((o) => {
          const [v, t] = Array.isArray(o) ? o : [o, o];
          return (
            <option key={v} value={v}>
              {t}
            </option>
          );
        })}
      </select>
      {error && <span className="err">{error}</span>}
    </div>
  );
}

// ---- toast ----
const ToastCtx = createContext<(msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const t = useRef<number>();
  const show = useCallback((m: string) => {
    setMsg(m);
    window.clearTimeout(t.current);
    t.current = window.setTimeout(() => setMsg(null), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="toast" role="status" aria-live="polite" hidden={!msg}>
        {msg}
      </div>
    </ToastCtx.Provider>
  );
}

export const Hexa = ({ path, tone = "", size }: { path: ReactNode; tone?: string; size?: number }) => (
  <span className={`hx ${tone}`} style={size ? { width: size, height: size * 1.12 } : undefined} aria-hidden="true">
    <svg viewBox="0 0 24 24" style={size ? { width: size / 2.1, height: size / 2.1 } : undefined}>
      {path}
    </svg>
  </span>
);
export const ICON_ESTETOSCOPIO = (
  <>
    <path d="M6 3v6a4 4 0 0 0 8 0V3" />
    <path d="M10 13v3a5 5 0 0 0 10 0v-2" />
    <circle cx="20" cy="12" r="2" />
  </>
);
