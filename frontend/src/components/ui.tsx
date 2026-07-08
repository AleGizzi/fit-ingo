import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./ui.css";

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "violet" | "ghost" | "soft" | "danger";
  block?: boolean;
};

/** Chunky pressable button with a bottom "lip" that compresses on :active. */
export function Button({ variant = "primary", block, className = "", ...rest }: BtnProps) {
  return (
    <button
      className={`btn btn-${variant} ${block ? "btn-block" : ""} ${className}`}
      {...rest}
    />
  );
}

export function Card({
  children,
  className = "",
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div className={`card ${className}`} onClick={onClick}>
      {children}
    </div>
  );
}

/** A selectable option tile used across onboarding and settings. */
export function OptionTile({
  selected,
  title,
  desc,
  icon,
  onClick,
}: {
  selected: boolean;
  title: string;
  desc?: string;
  icon?: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`opt ${selected ? "opt-on" : ""}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      {icon && <span className="opt-icon">{icon}</span>}
      <span className="opt-text">
        <span className="opt-title">{title}</span>
        {desc && <span className="opt-desc">{desc}</span>}
      </span>
      <span className="opt-check" aria-hidden>
        {selected ? "✓" : ""}
      </span>
    </button>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="seg" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          className={`seg-item ${value === o.value ? "seg-on" : ""}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Stepper({
  value,
  min,
  max,
  step = 1,
  suffix,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (v: number) => void;
}) {
  const clamp = (v: number) => Math.max(min, Math.min(max, v));
  return (
    <div className="stepper">
      <button aria-label="decrease" onClick={() => onChange(clamp(value - step))}>−</button>
      <span className="num stepper-val">
        {value}
        {suffix ? <span className="stepper-suffix">{suffix}</span> : null}
      </span>
      <button aria-label="increase" onClick={() => onChange(clamp(value + step))}>+</button>
    </div>
  );
}
