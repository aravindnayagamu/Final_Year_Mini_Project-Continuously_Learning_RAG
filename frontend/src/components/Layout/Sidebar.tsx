import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { getHealth } from "@/api/client";
import type { HealthResponse } from "@/types";

const NAV_ITEMS = [
  { to: "/chat",      icon: "", label: "Chat" },
  { to: "/research",  icon: "", label: "Research Assistant" },
  { to: "/dashboard", icon: "", label: "Dashboard" },
  { to: "/ingest",    icon: "", label: "Ingestion" },
];

export default function Sidebar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth(h);
      } catch {
        if (!cancelled) setHealth(null);
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const dotClass =
    health === null
      ? "loading"
      : health.status === "ok"
      ? "ok"
      : health.status === "degraded"
      ? "degraded"
      : "error";

  const healthLabel =
    health === null
      ? "Checking…"
      : health.status === "ok"
      ? "All systems operational"
      : "Service degraded";

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
        <div className="health-indicator">
          <span className={`health-dot ${dotClass}`} />
          <span>{healthLabel}</span>
        </div>
      </div>
    </aside>
  );
}
