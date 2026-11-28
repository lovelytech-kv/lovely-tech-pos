import { Icon, type IconName } from '../components/Icon';
import { useTheme, type Theme } from './ThemeProvider';
import type { KeyboardEvent } from 'react';

type ThemeOption = { value: Theme; label: string; icon: IconName };

const THEME_OPTIONS: readonly ThemeOption[] = [
  { value: 'light', label: 'Light', icon: 'sun' },
  { value: 'system', label: 'Auto', icon: 'sun-moon' },
  { value: 'dark', label: 'Dark', icon: 'moon' },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const activeIndex = Math.max(0, THEME_OPTIONS.findIndex((option) => option.value === theme));

  function moveTo(index: number, container: HTMLDivElement) {
    const next = (index + THEME_OPTIONS.length) % THEME_OPTIONS.length;
    setTheme(THEME_OPTIONS[next].value);
    container.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const key = event.key;
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(key)) return;
    event.preventDefault();
    if (key === 'Home') return moveTo(0, event.currentTarget);
    if (key === 'End') return moveTo(THEME_OPTIONS.length - 1, event.currentTarget);
    const step = key === 'ArrowLeft' || key === 'ArrowUp' ? -1 : 1;
    moveTo(activeIndex + step, event.currentTarget);
  }

  return (
    <div
      className="theme-segmented"
      role="radiogroup"
      aria-label="Color theme"
      onKeyDown={onKeyDown}
    >
      <span
        className="theme-segmented-thumb"
        aria-hidden="true"
        style={{ transform: `translateX(calc(${activeIndex} * (100% + 2px)))` }}
      />
      {THEME_OPTIONS.map((option) => {
        const selected = theme === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`Theme: ${option.label}`}
            title={`Theme: ${option.label}`}
            tabIndex={selected ? 0 : -1}
            className={`theme-segmented-option${selected ? ' is-active' : ''}`}
            onClick={() => setTheme(option.value)}
          >
            <Icon name={option.icon} size={16} />
            <span className="sr-only">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default ThemeToggle;
