import type { InputHTMLAttributes } from 'react';

/**
 * Money input: 2 decimal places max, no default value, no wheel, no spinner,
 * no negative. Returns spread-ready props.
 */
export function moneyInputProps(
  value: string,
  onChange: (v: string) => void,
): InputHTMLAttributes<HTMLInputElement> {
  return {
    type: 'text',
    inputMode: 'decimal',
    value,
    onChange: (e) => {
      const v = e.target.value;
      if (v === '' || /^\d*\.?\d{0,2}$/.test(v)) onChange(v);
    },
    onWheel: (e) => (e.target as HTMLInputElement).blur(),
  };
}

/**
 * Integer input: whole numbers only (default min=1). Empty becomes min.
 * No wheel, no spinner, no negative, no decimals.
 */
export function intInputProps(
  value: string,
  onChange: (v: string) => void,
  min: number = 1,
): InputHTMLAttributes<HTMLInputElement> {
  return {
    type: 'text',
    inputMode: 'numeric',
    value,
    onChange: (e) => {
      const v = e.target.value;
      if (v === '') { onChange(String(min)); return; }
      if (!/^\d+$/.test(v)) return;
      const n = parseInt(v, 10);
      onChange(String(Math.max(min, n)));
    },
    onWheel: (e) => (e.target as HTMLInputElement).blur(),
  };
}

/**
 * Signed integer (for +/- stock adjustments): allows negative values.
 * Accepts '', '-', or any integer (positive or negative). No wheel, no spinner.
 */
export function signedIntInputProps(
  value: string,
  onChange: (v: string) => void,
): InputHTMLAttributes<HTMLInputElement> {
  return {
    type: 'text',
    inputMode: 'numeric',
    value,
    onChange: (e) => {
      const v = e.target.value;
      if (v === '' || v === '-' || /^-?\d+$/.test(v)) onChange(v);
    },
    onWheel: (e) => (e.target as HTMLInputElement).blur(),
  };
}