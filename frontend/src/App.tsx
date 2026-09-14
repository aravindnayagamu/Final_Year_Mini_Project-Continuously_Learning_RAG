import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "@/components/Layout/Sidebar";
import ChatPage from "@/pages/ChatPage";
import ResearchPage from "@/pages/ResearchPage";
import DashboardPage from "@/pages/DashboardPage";
import IngestPage from "@/pages/IngestPage";

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
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
