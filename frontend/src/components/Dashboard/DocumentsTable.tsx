import { format } from "date-fns";
import type { DocumentOut } from "@/types";

interface Props {
  documents: DocumentOut[];
  loading: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  vectorized: "vectorized",
  pending: "pending",
  failed: "failed",
};

export default function DocumentsTable({ documents, loading }: Props) {
  if (loading) {
    return (
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {["Source", "Title", "Status", "Chunks", "Retrieved"].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>
                {Array.from({ length: 5 }).map((_, j) => (
                  <td key={j}>
                    <div
                      className="skeleton"
                      style={{ height: 14, width: j === 1 ? 200 : 80 }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!documents.length) {
    return (
      <div className="empty-state">
        <span className="empty-state-icon"></span>
        <span>No documents ingested yet. Run an ingestion job to populate this table.</span>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Title / File</th>
            <th>Status</th>
            <th>Chunks</th>
            <th>Retrieved</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.paper_id}>
              <td>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--teal)",
                    background: "var(--teal-dim)",
                    padding: "2px 8px",
                    borderRadius: 99,
                  }}
                >
                  {doc.source_name.replace(/_/g, " ")}
                </span>
              </td>
              <td className="truncate" style={{ maxWidth: 260 }}>
                <span title={doc.title ?? doc.file_name ?? "—"}>
                  {doc.title ?? doc.file_name ?? <span className="text-muted">—</span>}
                </span>
              </td>
              <td>
                <span className={`badge ${doc.vectorization_status}`}>
                  <span className="badge-dot" />
                  {STATUS_LABEL[doc.vectorization_status] ?? doc.vectorization_status}
                </span>
              </td>
              <td className="td-mono">{doc.chunk_count ?? "—"}</td>
              <td className="td-mono">
                {doc.retrieval_time
                  ? format(new Date(doc.retrieval_time), "dd MMM, HH:mm")
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
