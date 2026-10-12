import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import TopBar from "@/components/Layout/TopBar";
import { generateSummary, getLatestSummary, getSummaryPreferences } from "@/api/client";
import type { NewsSummary, UserPreferences } from "@/types";

function renderInline(text: string, key: number) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <span key={key}>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p
      )}
    </span>
  );
}

function SummaryBody({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div style={{ lineHeight: 1.7, fontSize: 14 }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();
        if (!line.trim()) return <div key={i} style={{ height: 8 }} />;
        if (line.startsWith("### "))
          return <h4 key={i} style={{ margin: "14px 0 4px", color: "var(--teal)" }}>{renderInline(line.slice(4), i)}</h4>;
        if (line.startsWith("## "))
          return <h3 key={i} style={{ margin: "22px 0 6px" }}>{renderInline(line.slice(3), i)}</h3>;
        if (line.startsWith("# "))
          return <h2 key={i} style={{ margin: "22px 0 8px" }}>{renderInline(line.slice(2), i)}</h2>;
        if (/^\s*[-*]\s+/.test(line))
          return <div key={i} style={{ paddingLeft: 18 }}>• {renderInline(line.replace(/^\s*[-*]\s+/, ""), i)}</div>;
        return <div key={i}>{renderInline(line, i)}</div>;
      })}
    </div>
  );
}

export default function SummaryPage() {
  const [summary, setSummary] = useState<NewsSummary | null>(null);
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSummary(await getLatestSummary());
    } catch { /* ignore */ }
    try {
      setPrefs(await getSummaryPreferences());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await generateSummary());
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Failed to generate summary");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <TopBar
        title="News Digest"
        subtitle="Personalised summary of recent and historical news"
        badge={summary ? `Generated ${format(new Date(summary.generated_at), "dd MMM, HH:mm")}` : undefined}
        actions={
          <button className="btn btn-primary btn-sm" onClick={generate} disabled={loading}>
            {loading ? "Generating…" : "✦ Generate Summary"}
          </button>
        }
      />
      <div className="page-body">
        {prefs && (
          <div className="mb-7" style={{ fontSize: 13, opacity: 0.85 }}>
            Personalised for <strong>{prefs.user_name ?? "User"}</strong>
            {prefs.preferred_location ? ` · ${prefs.preferred_location}` : ""}
            {prefs.news_categories?.length ? ` · ${prefs.news_categories.join(", ")}` : ""}
          </div>
        )}
        {error && <div className="empty-state" style={{ color: "var(--red)" }}>{error}</div>}
        {loading && <div className="empty-state">Retrieving news and generating the digest — this can take a minute…</div>}
        {!loading && !summary && !error && (
          <div className="empty-state">No summary yet. Click “Generate Summary” to create one.</div>
        )}
        {!loading && summary && (
          <>
            <div className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
              Generated in {summary.generation_time_ms ? (summary.generation_time_ms / 1000).toFixed(1) : "—"}s
            </div>
            <SummaryBody text={summary.summary} />
          </>
        )}
      </div>
    </>
  );
}
