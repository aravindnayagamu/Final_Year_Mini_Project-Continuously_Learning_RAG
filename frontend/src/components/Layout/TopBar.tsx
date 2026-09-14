interface TopBarProps {
  title: string;
  subtitle?: string;
  badge?: string;
  actions?: React.ReactNode;
}

export default function TopBar({ title, subtitle, badge, actions }: TopBarProps) {
  return (
    <header className="topbar">
      <div>
        <div className="topbar-title">{title}</div>
        {subtitle && <div className="topbar-subtitle">{subtitle}</div>}
      </div>
      <div className="topbar-spacer" />
      {badge && <span className="topbar-badge">{badge}</span>}
      {actions}
    </header>
  );
}
