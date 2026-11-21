/**
 * Business-date helpers.
 *
 * M11 — `new Date().toISOString().slice(0, 10)` returns the UTC date, which is
 * one day behind for Sri Lanka (UTC+5:30) between 00:00 and 05:29 local.
 * Business date fields must use the shop's local calendar date.
 */
export function todayLocal(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
