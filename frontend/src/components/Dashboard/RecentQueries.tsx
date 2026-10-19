import { format } from "date-fns";

interface RecentQuery {
  id: number;
  question: string;
  answer: string | null;
  context_chunks: number | null;
  retrieval_time_ms: number | null;
  model_used: string | null;
  created_at: string;
}

interface Props {
  queries: RecentQuery[];
  loading: boolean;
}

export default function RecentQueries({ queries, loading }: Props) {
  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="skeleton"
            style={{ height: 54, borderRadius: 8 }}
          />
        ))}
      </div>
    );
  }

  if (!queries.length) {
    return (
      <div className="empty-state" style={{ padding: "32px 16px" }}>
        <span className="empty-state-icon">🔍</span>
        <span>No queries yet. Ask something in the Chat.</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {queries.map((q) => (
        <div
          key={q.id}
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-subtle)",
            borderRadius: 8,
            padding: "10px 14px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 12,
            }}
          >
            <p
              style={{
                fontSize: 13,
                color: "var(--text-primary)",
                flex: 1,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={q.question}
            >
              {q.question}
            </p>
            <span
              style={{
                fontSize: 11,
                color: "var(--text-muted)",
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {format(new Date(q.created_at), "HH:mm")}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              gap: 12,
              marginTop: 4,
              fontSize: 11,
              color: "var(--text-muted)",
            }}
          >
            {q.retrieval_time_ms != null && (
              <span>{q.retrieval_time_ms.toFixed(0)} ms</span>
            )}
            {q.context_chunks != null && <span>{q.context_chunks} chunks</span>}
            {q.model_used && (
              <span className="text-mono">{q.model_used}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
