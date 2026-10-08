const SCALE = 100n;
const QTY_SCALE = 1000n;

function scaled(value: string | number | null | undefined, scale: bigint): bigint {
  const raw = String(value ?? '').trim();
  if (!raw) return 0n;
  const sign = raw.startsWith('-') ? -1n : 1n;
  const unsigned = raw.replace(/^[+-]/, '');
  if (!/^\d+(\.\d+)?$/.test(unsigned)) throw new Error(`Invalid monetary value: ${value}`);
  const [whole, fraction = ''] = unsigned.split('.');
  const digits = fraction.padEnd(scale === SCALE ? 2 : 3, '0').slice(0, scale === SCALE ? 2 : 3);
  return sign * (BigInt(whole) * scale + BigInt(digits || '0'));
}

function formatScaled(value: bigint, scale: bigint, decimals: number): string {
  const sign = value < 0n ? '-' : '';
  const abs = value < 0n ? -value : value;
  const whole = abs / scale;
  const fraction = String(abs % scale).padStart(decimals, '0');
  return `${sign}${whole}.${fraction}`;
}

export function money(value: string | number | null | undefined): string {
  return formatScaled(scaled(value, SCALE), SCALE, 2);
}

export function moneyAdd(...values: Array<string | number | null | undefined>): string {
  return money(values.reduce((sum, value) => sum + scaled(value, SCALE), 0n).toString());
}

export function moneySub(a: string | number | null | undefined, b: string | number | null | undefined): string {
  return money((scaled(a, SCALE) - scaled(b, SCALE)).toString());
}

/** Price has 2 decimals and quantity has up to 3 decimals; result is rounded to 2 decimals. */
export function moneyTimesQty(price: string | number, quantity: string | number): string {
  const p = scaled(price, SCALE);
  const q = scaled(quantity, QTY_SCALE);
  const product = p * q;
  const divisor = SCALE * QTY_SCALE;
  const rounded = product >= 0n ? (product + divisor / 2n) / divisor : (product - divisor / 2n) / divisor;
  return formatScaled(rounded, SCALE, 2);
}

export function moneyPositive(value: string | number | null | undefined): boolean {
  return scaled(value, SCALE) > 0n;
}

export function moneyEqual(a: string | number, b: string | number): boolean {
  return scaled(a, SCALE) === scaled(b, SCALE);
}
