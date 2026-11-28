import { Icon, type IconName } from '../components/Icon';
import { useTheme, type Theme } from './ThemeProvider';

const THEME_LABELS: Record<Theme, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
};

const THEME_ICONS: Record<Theme, IconName> = {
  light: 'sun',
  dark: 'moon',
  system: 'sun-moon',
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
      <span aria-hidden='true'><Icon name={THEME_ICONS[theme]} size={18} /></span>
    </button>
  );
}

export default ThemeToggle;