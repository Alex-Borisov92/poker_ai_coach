import type { ReactNode } from "react";

export const navItems = ["AI Coach", "Leak Finder", "Study Plan", "Settings"] as const;

export type NavItem = (typeof navItems)[number];

type AppShellProps = {
  children: ReactNode;
  activeItem: NavItem;
  onNavigate: (item: NavItem) => void;
};

export function AppShell({ children, activeItem, onNavigate }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">PC</span>
          <div>
            <div className="brand-title">Poker AI Coach</div>
            <div className="brand-subtitle">Post-session</div>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              className={item === activeItem ? "nav-item active" : "nav-item"}
              key={item}
              onClick={() => onNavigate(item)}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="topbar-spacer" aria-hidden="true" />
      </header>
      <main className="main-content">{children}</main>
    </div>
  );
}
