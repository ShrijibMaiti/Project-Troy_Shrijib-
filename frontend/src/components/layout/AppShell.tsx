import { Link, NavLink, Outlet } from 'react-router-dom';

const NAV = [
  { to: '/fleet', label: 'FLEET' },
  { to: '/evidence', label: 'EVIDENCE' },
  { to: '/methodology', label: 'METHODOLOGY' },
  { to: '/register', label: 'REGISTER' },
  { to: '/compare', label: 'COMPARE' },
  { to: '/settings', label: 'SETTINGS' },
];

export default function AppShell() {
  return (
    <div className="min-h-screen bg-ink">
      <nav className="sticky top-0 z-[60] flex h-14 items-center justify-between border-b border-line bg-ink/90 px-7 backdrop-blur-md">
        <div className="flex items-center gap-[26px]">
          <Link to="/" className="font-mono text-sm font-semibold tracking-[.18em]">
            TROY
          </Link>
          <div className="flex gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) =>
                  `rounded-sm px-3 py-2 font-mono text-[10.5px] tracking-[.12em] transition-colors hover:text-fg ${
                    isActive ? 'bg-navactive text-fg' : 'text-mute'
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-[7px]">
            <span className="h-1.5 w-1.5 animate-blink rounded-full bg-risk-green" />
            <span className="font-mono text-[10px] tracking-[.1em] text-dim">DEV · AUTH BYPASS</span>
          </div>
          <span className="rounded-sm border border-line-2 px-2.5 py-[5px] font-mono text-[10px] tracking-[.1em] text-mute">
            MERIDIAN GRC
          </span>
        </div>
      </nav>
      <Outlet />
    </div>
  );
}