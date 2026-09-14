import { useCallback, useEffect, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import StatCard from "@/components/Dashboard/StatCard";
import DocumentsTable from "@/components/Dashboard/DocumentsTable";
import { getDocuments, getDocumentStats } from "@/api/client";
import type { DocumentOut, DocumentStats } from "@/types";

const PAGE_SIZE = 20;

export default function DashboardPage() {
  const [stats, setStats] = useState<DocumentStats | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [page, setPage] = useState(1);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      setLoadingStats(true);
      const s = await getDocumentStats();
      setStats(s);
    } catch {
      // ignore
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const fetchDocs = useCallback(async (p: number) => {
    try {
      setLoadingDocs(true);
      const docs = await getDocuments(p, PAGE_SIZE);
      setDocuments(docs);
    } catch {
      // ignore
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchDocs(1);
  }, [fetchStats, fetchDocs]);

  useEffect(() => {
    fetchDocs(page);
  }, [page, fetchDocs]);

  const totalPages = Math.ceil((stats?.total ?? 0) / PAGE_SIZE);

  return (
    <>
      <TopBar
        title="Dashboard"
        subtitle="Pipeline overview and document inventory"
        badge={new Date().toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}
        actions={
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { fetchStats(); fetchDocs(page); }}
          >
            ↻ Refresh
          </button>
        }
      />

      <div className="page-body">
        {/* Stats row */}
        <div className="stats-grid">
          <StatCard
            label="Total Articles"
            value={loadingStats ? "—" : (stats?.total ?? 0)}
            sub="ingested from all RSS sources"
            color="blue"
            icon=""
          />
          <StatCard
            label="Vectorized"
            value={loadingStats ? "—" : (stats?.vectorized ?? 0)}
            sub="embedded in ChromaDB"
            color="green"
            icon=""
          />
          <StatCard
            label="Pending"
            value={loadingStats ? "—" : (stats?.pending ?? 0)}
            sub="awaiting vectorization"
            color="amber"
            icon=""
          />
          <StatCard
            label="Failed"
            value={loadingStats ? "—" : (stats?.failed ?? 0)}
            sub="errors during embedding"
            color="red"
            icon=""
          />
        </div>

        {/* Documents table */}
        <div className="mb-7">
          <div className="section-title">Ingested Documents</div>
          <DocumentsTable documents={documents} loading={loadingDocs} />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <span className="pagination-info">
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                ← Prev
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
