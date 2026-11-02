import { useTheme, type Theme } from './ThemeProvider';

const THEME_LABELS: Record<Theme, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
};

const THEME_GLYPHS: Record<Theme, string> = {
  light: '☀',
  dark: '☾',
  system: '◐',
};

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const label = THEME_LABELS[theme];

  return (
    <button
      type='button'
      className='icon-button'
      onClick={toggleTheme}
      title={`Theme: ${label} (click to change)`}
      aria-label={`Theme: ${label}. Click to change theme.`}
    >
      <span aria-hidden='true'>{THEME_GLYPHS[theme]}</span>
    </button>
  );
}

export default ThemeToggle;