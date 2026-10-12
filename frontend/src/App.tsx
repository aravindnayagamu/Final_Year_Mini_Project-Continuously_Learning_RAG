import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "@/components/Layout/Sidebar";
import ChatPage from "@/pages/ChatPage";
import ResearchPage from "@/pages/ResearchPage";
import DashboardPage from "@/pages/DashboardPage";
import IngestPage from "@/pages/IngestPage";
import SummaryPage from "@/pages/SummaryPage";
import MetricsPage from "@/pages/MetricsPage";
import SourcesPage from "@/pages/SourcesPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/research" element={<ResearchPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/ingest" element={<IngestPage />} />
            <Route path="/summary" element={<SummaryPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/sources" element={<SourcesPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
