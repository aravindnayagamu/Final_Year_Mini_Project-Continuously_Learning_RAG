import { useCallback, useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import TopBar from "@/components/Layout/TopBar";
import StatCard from "@/components/Dashboard/StatCard";
import { getSources, separateRecentData } from "@/api/client";
import type { SeparationResult, SourcesResponse } from "@/types";

export default function SourcesPage() {
  const [data, setData] = useState<SourcesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [group, setGroup] = useState<string>("ALL");
  const [sep, setSep] = useState<SeparationResult | null>(null);
  const [sepBusy, setSepBusy] = useState(false);
  const [sepError, setSepError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await getSources()); } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const rows = useMemo(
    () => (data?.sources ?? []).filter((s) => group === "ALL" || s.group === group),
    [data, group]
  );

  const runSeparation = async () => {
    setSepBusy(true);
    setSepError(null);
    try { setSep(await separateRecentData()); }
    catch (e: any) { setSepError(e?.response?.data?.detail ?? e?.message ?? "Failed"); }
    finally { setSepBusy(false); }
  };

  const totalDocs = (data?.sources ?? []).reduce((a, s) => a + s.document_count, 0);

  return (
    <>
      <TopBar
        title="News Sources"
        subtitle="All configured RSS feeds and archive maintenance"
        actions={<button className="btn btn-ghost btn-sm" onClick={load}>↻ Refresh</button>}
      />
      <div className="page-body">
        <div className="stats-grid">
          <StatCard label="Sources" value={loading ? "—" : data?.total_sources ?? 0} sub="configured RSS feeds" color="blue" />
          <StatCard label="Publishers" value={loading ? "—" : Object.keys(data?.groups ?? {}).length} sub={Object.keys(data?.groups ?? {}).join(" · ")} color="teal" />
          <StatCard label="Articles" value={loading ? "—" : totalDocs} sub="ingested across all sources" color="green" />
        </div>

        <div className="mb-7">
          <div className="section-title">Archive Maintenance</div>
          <p className="text-muted" style={{ fontSize: 13, margin: "0 0 10px" }}>
            Moves chunks older than 24 hours from the recent vector store to the historical store.
            This also runs automatically after every ingestion.
          </p>
          <button className="btn btn-primary btn-sm" onClick={runSeparation} disabled={sepBusy}>
            {sepBusy ? "Running…" : "Separate Recent / Historical Data"}
          </button>
          {sepError && <div style={{ color: "var(--red)", marginTop: 8, fontSize: 13 }}>{sepError}</div>}
          {sep && (
            <div className="stats-grid" style={{ marginTop: 14 }}>
              <StatCard label="Moved to Historical" value={sep.total_moved} sub={`${sep.historical_moved} aged · ${sep.unknown_moved} unknown time`} color="amber" />
              <StatCard label="Recent Retained" value={sep.recent_retained} sub={`ran ${format(new Date(sep.ran_at), "HH:mm:ss")}`} color="green" />
            </div>
          )}
        </div>

        <div className="mb-7">
          <div className="section-title">Feeds</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {["ALL", ...Object.keys(data?.groups ?? {})].map((g) => (
              <button key={g} className={`btn btn-sm ${group === g ? "btn-primary" : "btn-ghost"}`} onClick={() => setGroup(g)}>
                {g}{g !== "ALL" && data ? ` (${data.groups[g]})` : ""}
              </button>
            ))}
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Source</th><th>Feed URL</th><th>Articles</th><th>Last Fetched</th></tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.source_name}>
                    <td>{s.source_name.replace(/_/g, " ")}</td>
                    <td className="truncate" style={{ maxWidth: 360 }}><a href={s.url} target="_blank" rel="noreferrer">{s.url}</a></td>
                    <td className="td-mono">{s.document_count}</td>
                    <td className="td-mono">{s.last_fetched ? format(new Date(s.last_fetched), "dd MMM, HH:mm") : "—"}</td>
                  </tr>
                ))}
                {!rows.length && !loading && (
                  <tr><td colSpan={4} className="text-muted">No sources found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
