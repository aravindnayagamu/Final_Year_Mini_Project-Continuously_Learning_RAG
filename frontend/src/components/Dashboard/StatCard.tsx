interface Props {
  label: string;
  value: number | string;
  sub?: string;
  color?: "blue" | "teal" | "amber" | "red" | "green";
  icon?: string;
}

export default function StatCard({
  label,
  value,
  sub,
  color = "blue",
  icon,
}: Props) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="flex items-center gap-2" style={{ justifyContent: "space-between" }}>
        <span className="stat-label">{label}</span>
        {icon && <span style={{ fontSize: 18, opacity: 0.6 }}>{icon}</span>}
      </div>
      <span className="stat-value">{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}
