import { format, formatDistanceToNow } from "date-fns";
import type { IngestionRunOut } from "@/types";

interface Props {
  runs: IngestionRunOut[];
  loading: boolean;
}

function duration(run: IngestionRunOut): string {
  if (!run.completed_at) return "—";
  const ms =
    new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function RunsTable({ runs, loading }: Props) {
  if (loading) {
    return (
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {["#", "Triggered", "Status", "Fetched", "Vectorized", "Duration", "Started"].map(
                (h) => <th key={h}>{h}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 4 }).map((_, i) => (
              <tr key={i}>
                {Array.from({ length: 7 }).map((_, j) => (
                  <td key={j}>
                    <div className="skeleton" style={{ height: 13, width: 60 }} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!runs.length) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon"></span>
        <span>No ingestion runs yet. Trigger one above.</span>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Triggered by</th>
            <th>Status</th>
            <th>Fetched</th>
            <th>Vectorized</th>
            <th>Duration</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td className="td-mono">{run.id}</td>
              <td>
                <span className={`badge ${run.triggered_by}`}>
                  {run.triggered_by === "manual" ? "⚡ Manual" : "🕐 Scheduler"}
                </span>
              </td>
              <td>
                <span className={`badge ${run.status}`}>
                  <span className="badge-dot" />
                  {run.status}
                </span>
              </td>
              <td className="td-mono">{run.articles_fetched}</td>
              <td className="td-mono">{run.articles_vectorized}</td>
              <td className="td-mono">{duration(run)}</td>
              <td className="td-mono" title={format(new Date(run.started_at), "PPpp")}>
                {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
