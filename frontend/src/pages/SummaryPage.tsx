import { useCallback, useEffect, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import {
  generateSummary,
  getLatestSummary,
  getSummaryPreferences,
  updateSummaryPreferences,
} from "@/api/client";
import type { NewsSummary, UserPreferences } from "@/types";

const ALL_CATEGORY_OPTIONS = [
  "National news",
  "State / district news",
  "Sports",
  "Financial / Business news",
  "Political news",
];

const DETAIL_OPTIONS = ["Quick", "Balanced", "In-depth"];

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

  const [userName, setUserName] = useState("");
  const [location, setLocation] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [interestsText, setInterestsText] = useState("");
  const [summaryDetail, setSummaryDetail] = useState("Balanced");
  const [language, setLanguage] = useState("English");
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showConfig, setShowConfig] = useState(true);

  const syncFormFromPrefs = (p: UserPreferences) => {
    setUserName(p.user_name ?? "User");
    setLocation(p.preferred_location ?? "");
    setCategories(p.news_categories ?? []);
    setInterestsText((p.specific_interests ?? []).join(", "));
    setSummaryDetail(p.summary_detail ?? "Balanced");
    setLanguage(p.preferred_language ?? "English");
  };

  const load = useCallback(async () => {
    try {
      setSummary(await getLatestSummary());
    } catch { /* ignore */ }
    try {
      const p = await getSummaryPreferences();
      setPrefs(p);
      syncFormFromPrefs(p);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggleCategory = (cat: string) => {
    if (categories.includes(cat)) {
      setCategories(categories.filter((c) => c !== cat));
    } else {
      setCategories([...categories, cat]);
    }
  };

  const handleSavePreferences = async () => {
    setSavingPrefs(true);
    setSaveSuccess(false);
    setError(null);
    try {
      const parsedInterests = interestsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const updated: UserPreferences = {
        user_name: userName.trim() || "User",
        preferred_location: location.trim(),
        news_categories: categories,
        specific_interests: parsedInterests,
        summary_detail: summaryDetail,
        preferred_language: language.trim() || "English",
        topics_to_avoid: prefs?.topics_to_avoid ?? [],
      };
      const saved = await updateSummaryPreferences(updated);
      setPrefs(saved);
      syncFormFromPrefs(saved);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Failed to save preferences");
    } finally {
      setSavingPrefs(false);
    }
  };

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      await handleSavePreferences();
      setSummary(await generateSummary());
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Failed to generate personal news");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <TopBar
        title="Personal News Feed"
        subtitle="Personalized news fetched and curated based on your preferences"
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowConfig(!showConfig)}
            >
              {showConfig ? "Hide Preferences" : "⚙ Edit Preferences"}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={generate}
              disabled={loading}
            >
              {loading ? "Fetching…" : "✦ Fetch Personal News"}
            </button>
          </div>
        }
      />
      <div className="page-body">
        {showConfig && (
          <div
            className="card mb-7"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: "20px 24px",
              marginBottom: 24,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <div>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)" }}>
                  Personalization Preferences
                </h3>
                <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                  Set your location, favorite topics, and interests to tailor your news feed
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {saveSuccess && (
                  <span style={{ fontSize: 12, color: "var(--green)", fontWeight: 500 }}>
                    ✓ Saved successfully
                  </span>
                )}
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleSavePreferences}
                  disabled={savingPrefs}
                >
                  {savingPrefs ? "Saving…" : "Save Preferences"}
                </button>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: 16,
                marginBottom: 16,
              }}
            >
              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                  User Name
                </label>
                <input
                  type="text"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="e.g. John Doe"
                  style={{
                    width: "100%",
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    padding: "8px 12px",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                  Preferred Location
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. Tamil Nadu, India"
                  style={{
                    width: "100%",
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    padding: "8px 12px",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                  Summary Detail Level
                </label>
                <select
                  value={summaryDetail}
                  onChange={(e) => setSummaryDetail(e.target.value)}
                  style={{
                    width: "100%",
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    padding: "8px 12px",
                    fontSize: 13,
                    outline: "none",
                  }}
                >
                  {DETAIL_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                  Preferred Language
                </label>
                <input
                  type="text"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  placeholder="e.g. English"
                  style={{
                    width: "100%",
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    padding: "8px 12px",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
                News Categories
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {ALL_CATEGORY_OPTIONS.map((cat) => {
                  const active = categories.includes(cat);
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => handleToggleCategory(cat)}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "99px",
                        fontSize: 12,
                        cursor: "pointer",
                        border: active ? "1px solid var(--accent)" : "1px solid var(--border)",
                        background: active ? "var(--accent-dim)" : "var(--bg-elevated)",
                        color: active ? "var(--text-accent)" : "var(--text-secondary)",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {active ? "✓ " : "+ "}
                      {cat}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
                Specific Interests & Keywords (comma separated)
              </label>
              <input
                type="text"
                value={interestsText}
                onChange={(e) => setInterestsText(e.target.value)}
                placeholder="e.g. Artificial intelligence, Software engineering, Indian cricket"
                style={{
                  width: "100%",
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--text-primary)",
                  padding: "8px 12px",
                  fontSize: 13,
                  outline: "none",
                }}
              />
            </div>
          </div>
        )}

        {prefs && !showConfig && (
          <div
            className="mb-7"
            style={{
              fontSize: 13,
              opacity: 0.9,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 16px",
              background: "var(--bg-card)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border)",
              marginBottom: 20,
            }}
          >
            <div>
              Personalised for <strong>{prefs.user_name ?? "User"}</strong>
              {prefs.preferred_location ? ` · ${prefs.preferred_location}` : ""}
              {prefs.news_categories?.length ? ` · ${prefs.news_categories.join(", ")}` : ""}
            </div>
            <button
              className="btn btn-ghost btn-sm"
              style={{ fontSize: 11, padding: "3px 8px" }}
              onClick={() => setShowConfig(true)}
            >
              Edit
            </button>
          </div>
        )}

        {error && <div className="empty-state" style={{ color: "var(--red)" }}>{error}</div>}
        {loading && <div className="empty-state">Fetching personalized news and generating your feed — this can take a minute…</div>}
        {!loading && !summary && !error && (
          <div className="empty-state">No news feed generated yet. Click “Fetch Personal News” to retrieve latest news based on your preferences.</div>
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