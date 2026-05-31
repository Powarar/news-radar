import type { CSSProperties } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_LINKS = [
  { to: "/feed", label: "Лента" },
  { to: "/preferences", label: "Темы" },
  { to: "/sources", label: "Источники" },
  { to: "/profile", label: "Профиль" },
];

function RadarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="4" cy="16" r="1.8" fill="currentColor" />
      <path d="M4 16 Q4 4 16 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M4 16 Q4 9 11 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export default function NavBar() {
  const { pathname } = useLocation();
  return (
    <nav style={s.nav}>
      <Link to="/feed" style={s.navLogo}>
        <span style={s.navLogoMark}><RadarIcon /></span> News Radar
      </Link>
      <div style={s.navLinks}>
        {NAV_LINKS.map(({ to, label }) => {
          const active = pathname === to || (to !== "/feed" && pathname.startsWith(to));
          return (
            <Link key={to} to={to} style={{ ...s.navLink, ...(active ? s.navLinkActive : {}) }}>
              {label}
              {active && <span style={s.navLinkDot} />}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

const s: Record<string, CSSProperties> = {
  nav: {
    position: "sticky",
    top: 0,
    zIndex: 100,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    height: 54,
    background: "rgba(13,13,12,0.85)",
    backdropFilter: "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderBottom: "1px solid var(--border)",
  },
  navLogo: {
    display: "flex",
    alignItems: "center",
    gap: 7,
    fontSize: 16,
    fontWeight: 700,
    color: "var(--text)",
    textDecoration: "none",
    letterSpacing: "-0.01em",
  },
  navLogoMark: { color: "var(--accent)", fontSize: 18 },
  navLinks: { display: "flex", gap: 4 },
  navLink: {
    position: "relative",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    padding: "6px 12px",
    color: "var(--text-muted)",
    textDecoration: "none",
    fontSize: 13,
    fontWeight: 500,
    borderRadius: "var(--radius-sm)",
    transition: "color 150ms ease",
  },
  navLinkActive: { color: "var(--text)" },
  navLinkDot: {
    position: "absolute",
    bottom: 0,
    left: "50%",
    transform: "translateX(-50%)",
    width: 4,
    height: 4,
    borderRadius: "50%",
    background: "var(--accent)",
  },
};
