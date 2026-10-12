import { useCallback, useEffect, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import StatCard from "@/components/Dashboard/StatCard";
import { getMetrics, resetMetrics, getVectorStats } from "@/api/client";
import type { RetrievalMetrics, VectorStats } from "@/types";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(1)}%`);

export default function MetricsPage() {
  const [m, setM] = useState<RetrievalMetrics | null>(null);
  const [vs, setVs] = useState<VectorStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setM(await getMetrics()); } catch { /* ignore */ }
    try { setVs(await getVectorStats()); } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const reset = async () => {
    if (!window.confirm("Reset all retrieval metrics?")) return;
    setM(await resetMetrics());
  };

  const v = (x: string | number | null | undefined) => (loading ? "—" : x ?? "—");

  return (
    <>
      <TopBar
        title="Retrieval Metrics"
        subtitle="Heuristic quality and latency metrics for recent & historical retrieval"
        actions={
          <>
            <button className="btn btn-ghost btn-sm" onClick={load}>↻ Refresh</button>
            <button className="btn btn-ghost btn-sm" onClick={reset}>Reset</button>
          </>
        }
      />
      <div className="page-body">
        <div className="stats-grid">
          <StatCard label="Relevance" value={v(m && pct(m.relevance.relevance_score))} sub={`${m?.relevance.relevant ?? 0}/${m?.relevance.total ?? 0} chunks`} color="blue" />
          <StatCard label="Precision@6" value={v(m && pct(m["precision@6"].precision_score))} sub={`${m?.["precision@6"].queries ?? 0} queries`} color="green" />
          <StatCard label="Contextual Precision" value={v(m && pct(m.contextual_precision.contextual_precision_score))} sub="ranking-aware" color="teal" />
          <StatCard label="Recall@6" value={v(m && pct(m["recall@6"].recall_score))} sub={m?.["recall@6"].recall_score == null ? "needs ground truth" : "vs ground truth"} color="amber" />
        </div>

        <div className="stats-grid">
          <StatCard label="Recent Precision" value={v(m && pct(m.recent_precision.precision_score))} sub={`${m?.recent_precision.total ?? 0} chunks`} color="green" />
          <StatCard label="Historical Precision" value={v(m && pct(m.historical_precision.precision_score))} sub={`${m?.historical_precision.total ?? 0} chunks`} color="blue" />
          <StatCard label="Temporal Accuracy" value={v(m && pct(m.temporal_assignment.accuracy_score))} sub={`${m?.temporal_assignment.unknown_timestamp_count ?? 0} unknown timestamps`} color="teal" />
          <StatCard label="Avg Latency" value={v(m?.retrieval_latency_ms.average != null ? `${m.retrieval_latency_ms.average} ms` : "—")} sub={`last: ${m?.retrieval_latency_ms.last ?? "—"} ms · ${m?.retrieval_latency_ms.count ?? 0} calls`} color="amber" />
        </div>

        <div className="stats-grid">
          <StatCard label="Chunks Retrieved" value={v(m?.chunks_retrieved.total)} sub={`${m?.chunks_retrieved.recent ?? 0} recent · ${m?.chunks_retrieved.historical ?? 0} historical`} color="blue" />
          <StatCard label="Recent Store" value={v(vs?.recent_chunks)} sub="chunks in recent_news_docs" color="green" />
          <StatCard label="Historical Store" value={v(vs?.historical_chunks)} sub="chunks in historical_news_docs" color="teal" />
        </div>

        {m?.last_call && (
          <div className="mb-7">
            <div className="section-title">Last Retrieval</div>
            <div className="table-wrapper">
              <table>
                <tbody>
                  <tr><th>Query</th><td>{m.last_call.query}</td></tr>
                  <tr><th>Retrieved</th><td className="td-mono">{m.last_call.retrieved} ({m.last_call.relevant_estimate} relevant est.)</td></tr>
                  <tr><th>Relevance</th><td className="td-mono">{pct(m.last_call.relevance_score)}</td></tr>
                  <tr><th>Latency</th><td className="td-mono">{m.last_call.retrieval_time_ms ?? "—"} ms</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {m?.methodology && (
          <div className="mb-7">
            <div className="section-title">Methodology</div>
            <div className="table-wrapper">
              <table>
                <tbody>
                  {Object.entries(m.methodology).map(([k, text]) => (
                    <tr key={k}><th>{k}</th><td>{text}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
