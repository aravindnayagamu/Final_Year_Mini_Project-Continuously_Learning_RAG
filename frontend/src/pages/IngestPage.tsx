import { useCallback, useEffect, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import RunsTable from "@/components/Ingest/RunsTable";
import { triggerIngest, getIngestionRuns } from "@/api/client";
import type { IngestionRunOut } from "@/types";

export default function IngestPage() {
  const [runs, setRuns] = useState<IngestionRunOut[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  const [hasRunning, setHasRunning] = useState(false);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await getIngestionRuns();
      setRuns(data);
      setHasRunning(data.some((r) => r.status === "running"));
    } catch {
      // ignore
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    // Poll every 5s if there's a running job
    const id = setInterval(() => {
      fetchRuns();
    }, 5_000);
    return () => clearInterval(id);
  }, [fetchRuns]);

  const handleTrigger = async () => {
    setTriggering(true);
    setLastMsg(null);
    try {
      const resp = await triggerIngest();
      setLastMsg(resp.message);
      // Refresh runs after short delay
      setTimeout(fetchRuns, 1500);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to trigger ingestion.";
      setLastMsg(`${msg}`);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <>
      <TopBar
        title="Ingestion"
        subtitle="Manage news fetching and vectorization jobs"
        badge={`Auto every 20 min`}
        actions={
          <button className="btn btn-ghost btn-sm" onClick={fetchRuns}>
            ↻ Refresh
          </button>
        }
      />

      <div className="page-body">
        <div className="ingest-trigger-card">
          <div className="ingest-info">
            <h2>Manual Ingestion</h2>
            <p>
              Fetch the latest articles from TOI, NDTV, and PIB India, then chunk, embed, and
              store them in ChromaDB. This usually takes 30–90 seconds depending on the number of
              new articles.
            </p>

            <div style={{ display: "flex", gap: 10, marginTop: 16, alignItems: "center" }}>
              <button
                id="trigger-ingest-btn"
                className="btn btn-primary"
                onClick={handleTrigger}
                disabled={triggering || hasRunning}
              >
                {triggering ? (
                  <>
                    <span className="spin">⟳</span> Starting…
                  </>
                ) : (
                  <>Run Now</>
                )}
              </button>

              {hasRunning && (
                <div className="ingest-running-msg">
                  <span className="spin">⟳</span>
                  A job is currently running…
                </div>
              )}
            </div>

            {lastMsg && !hasRunning && (
              <div className="ingest-running-msg" style={{ marginTop: 12, color: "var(--teal)" }}>
                ✓ {lastMsg}
              </div>
            )}
          </div>
        </div>

        {/* Info grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 12,
            marginBottom: 28,
          }}
        >
          {[
            { icon: "", label: "TOI Top Stories", url: "timesofindia.indiatimes.com" },
            { icon: "", label: "NDTV Top Stories", url: "feeds.feedburner.com" },
            { icon: "", label: "PIB India", url: "pib.gov.in" },
          ].map((src) => (
            <div
              key={src.label}
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                padding: "14px 16px",
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 22 }}>{src.icon}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                  {src.label}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  {src.url}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Runs table */}
        <div className="section-title">Run History</div>
        <RunsTable runs={runs} loading={loadingRuns} />
      </div>
    </>
  );
}
