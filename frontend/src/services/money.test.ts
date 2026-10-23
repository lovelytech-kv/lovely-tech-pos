import { describe, expect, it } from 'vitest';
import { money, moneyAdd, moneySub, moneyTimesQty, moneyEqual } from './money';

// Regression: moneyAdd/moneySub re-parsed an already-scaled integer as whole rupees, so every
// cart total was 100x too big (and compounded per line), blocking multi-line sales.
describe('money helpers', () => {
  it('adds without rescaling', () => {
    expect(moneyAdd('0.00', '45000.00')).toBe('45000.00');
    expect(moneyAdd('45000.00', '45000.00')).toBe('90000.00');
    expect(moneyAdd('10', '0.5', '')).toBe('10.50');
  });
  it('subtracts without rescaling', () => {
    expect(moneySub('45000.00', '0')).toBe('45000.00');
    expect(moneySub('100', '100.01')).toBe('-0.01');
  });
  it('cart total for several lines', () => {
    const lines = [['45000', '1', '0'], ['1200.50', '3', '100']];
    const total = lines.reduce((sum, [p, q, d]) => moneyAdd(sum, moneySub(moneyTimesQty(p, q), d)), '0.00');
    expect(total).toBe('48501.50');
    expect(moneyEqual(moneyAdd('48000', '501.5'), total)).toBe(true);
  });
  it('formats', () => { expect(money('45000')).toBe('45000.00'); });
});

describe('moneyTimesQty', () => {
  it('multiplies price by quantity to 2 decimals', () => {
    expect(moneyTimesQty('45000', '1')).toBe('45000.00');
    expect(moneyTimesQty('1200.50', '3')).toBe('3601.50');
    expect(moneyTimesQty('99.99', '0.5')).toBe('50.00'); // 49.995 rounds half up
    expect(moneyTimesQty('10', '0.333')).toBe('3.33');
  });
});
