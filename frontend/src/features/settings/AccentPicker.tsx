import { useTheme } from '../../theme/ThemeProvider';
import { currentUser } from '../../api/client';
import { loadPermissions, getDefaultPermissions, type Permission } from '../../config/permissions';

const CURATED_COLORS = [
  { hex: '#df3b32', name: 'Lovely Red' },
  { hex: '#2563eb', name: 'Blue' },
  { hex: '#16a34a', name: 'Green' },
  { hex: '#9333ea', name: 'Purple' },
  { hex: '#ea580c', name: 'Orange' },
  { hex: '#0891b2', name: 'Cyan' },
];

export function AccentPicker() {
  const { accent, setAccent } = useTheme();
  const user = currentUser();
  const isAdmin = (user?.role ?? '').toUpperCase() === 'ADMIN';
  const role = isAdmin ? 'ADMIN' : 'CASHIER';
  const perms: Permission[] = loadPermissions()[role] ?? getDefaultPermissions(role);
  const canChange = isAdmin || perms.includes('theme.accent.change');

  if (!canChange) {
    return (
      <div className="glass-panel settings-card">
        <div className="settings-card-title">
          <div>
            <h3>Accent color</h3>
            <p className="muted">Change the primary accent color of the UI.</p>
          </div>
          <span className="settings-symbol">✦</span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem',
            background: 'var(--surface-2)',
            borderRadius: 10,
            border: '1px solid var(--line)',
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: accent,
              boxShadow: '0 0 0 3px var(--surface), 0 0 0 4px var(--line)',
              flexShrink: 0,
            }}
          />
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
              {accent.toUpperCase()}
            </div>
            <div className="muted" style={{ fontSize: '0.75rem' }}>
              Only admin can change accent color
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel settings-card">
      <div className="settings-card-title">
        <div>
          <h3>Accent color</h3>
          <p className="muted">Choose the primary accent used across the app.</p>
        </div>
        <span className="settings-symbol">✦</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '0.5rem',
          marginBottom: '1rem',
        }}
      >
        {CURATED_COLORS.map((c) => {
          const isActive = accent.toLowerCase() === c.hex.toLowerCase();
          return (
            <button
              key={c.hex}
              type="button"
              onClick={() => setAccent(c.hex)}
              title={c.name}
              aria-label={`Set accent to ${c.name}`}
              aria-pressed={isActive}
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: c.hex,
                border: 'none',
                cursor: 'pointer',
                boxShadow: isActive
                  ? '0 0 0 3px var(--surface), 0 0 0 5px var(--accent)'
                  : '0 0 0 3px var(--surface), 0 0 0 4px var(--line)',
                transition: 'box-shadow 0.15s',
                display: 'grid',
                placeItems: 'center',
                color: '#fff',
                fontSize: '1rem',
                fontWeight: 700,
                justifySelf: 'center',
              }}
            >
              {isActive ? '✓' : ''}
            </button>
          );
        })}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.75rem',
          background: 'var(--surface-2)',
          borderRadius: 10,
          border: '1px solid var(--line)',
          marginBottom: '0.75rem',
        }}
      >
        <input
          type="color"
          value={accent}
          onChange={(e) => setAccent(e.target.value)}
          aria-label="Custom accent color"
          style={{
            width: 44,
            height: 44,
            border: '1px solid var(--line)',
            borderRadius: 8,
            cursor: 'pointer',
            background: 'transparent',
            padding: 2,
            flexShrink: 0,
          }}
        />
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
            Custom color
          </div>
          <div className="muted" style={{ fontSize: '0.75rem' }}>
            Pick any color using the color wheel
          </div>
        </div>
      </div>

      {/* Big obvious preview */}
      <div
        style={{
          padding: '0.85rem',
          background: 'var(--surface-2)',
          borderRadius: 10,
          border: '1px solid var(--line)',
        }}
      >
        <div
          className="muted"
          style={{
            fontSize: '0.7rem',
            marginBottom: '0.5rem',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            fontWeight: 600,
          }}
        >
          Live preview (click any swatch above)
        </div>

        {/* Large accent bar — biggest visual change indicator */}
        <div
          style={{
            height: 44,
            background: 'var(--accent)',
            borderRadius: 8,
            marginBottom: '0.75rem',
            display: 'grid',
            placeItems: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: '0.9rem',
            letterSpacing: '0.03em',
            transition: 'background 0.15s',
          }}
        >
          Current accent: {accent.toUpperCase()}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            style={{
              padding: '0.5rem 1rem',
              background: 'var(--accent)',
              color: '#fff',
              border: 0,
              borderRadius: 8,
              fontWeight: 600,
              cursor: 'pointer',
              fontSize: '0.85rem',
              transition: 'background 0.15s',
            }}
          >
            Primary Button
          </button>
          <span
            style={{
              padding: '2px 8px',
              background: 'rgba(var(--accent-rgb), 0.12)',
              color: 'var(--accent)',
              borderRadius: 999,
              fontSize: '0.75rem',
              fontWeight: 600,
              border: '1px solid rgba(var(--accent-rgb), 0.25)',
              transition: 'all 0.15s',
            }}
          >
            Badge
          </span>
          <a
            href="#"
            onClick={(e) => e.preventDefault()}
            style={{
              color: 'var(--accent)',
              fontSize: '0.85rem',
              fontWeight: 600,
              textDecoration: 'underline',
              transition: 'color 0.15s',
            }}
          >
            Link
          </a>
        </div>
      </div>
    </div>
  );
}

export default AccentPicker;