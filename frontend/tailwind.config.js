/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: 'var(--accent)',
          rgb: 'var(--accent-rgb)',
        },
        page: 'var(--page)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        line: 'var(--line)',
      },
      borderRadius: {
        'card': '18px',
        'control': '10px',
        'button': '9px',
        'lg': '12px',
      },
      boxShadow: {
        'card': '0 10px 30px rgba(20,20,30,.05)',
        'card-dark': '0 18px 42px rgba(0,0,0,.35)',
        'glass': '0 4px 24px rgba(0,0,0,0.04)',
        'glass-dark': '0 8px 32px rgba(0,0,0,0.16)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'sans-serif'],
      },
      backdropBlur: {
        'glass': '12px',
      },
      spacing: {
        '18': '4.5rem',
      },
    },
  },
  plugins: [],
}
