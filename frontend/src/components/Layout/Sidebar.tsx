import { NavLink } from "react-router-dom";
import { UserButton, useUser } from "@clerk/clerk-react";

const NAV_ITEMS = [
  { to: "/chat",      icon: "", label: "Chat" },
  { to: "/research",  icon: "", label: "Research Assistant" },
  { to: "/dashboard", icon: "", label: "Dashboard" },
  { to: "/ingest",    icon: "", label: "Ingestion" },
  { to: "/summary",   icon: "", label: "Personal News Feed" },
  { to: "/sources",   icon: "", label: "Sources" },
  { to: "/metrics",   icon: "", label: "Metrics" },
];

export default function Sidebar() {
  const { user, isLoaded } = useUser();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon"></div>
        <div className="sidebar-logo-text">
          <span className="sidebar-logo-name">Continual RAG</span>
          <span className="sidebar-logo-sub">News Intelligence</span>
          <span className="sidebar-logo-sub">Research Assistant</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="nav-section-label">Navigation</span>
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              ["nav-link", isActive ? "active" : ""].filter(Boolean).join(" ")
            }
          >
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        {isLoaded && user && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 10px",
              background: "var(--bg-card)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
            }}
          >
            <UserButton afterSignOutUrl="/" />
            <div style={{ overflow: "hidden", flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {user.fullName || user.username || "User"}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: "var(--text-muted)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {user.primaryEmailAddress?.emailAddress ?? ""}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}