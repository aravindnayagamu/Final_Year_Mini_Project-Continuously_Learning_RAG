import { useCallback, useEffect, useRef, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import MessageBubble from "@/components/Chat/MessageBubble";
import ChatInput from "@/components/Chat/ChatInput";
import {
  getResearchPapers,
  uploadResearchPaper,
  queryResearchPaper,
  deleteResearchPaper,
} from "@/api/client";
import type { ChatMessage, ResearchPaper } from "@/types";

let msgId = 0;
const nextId = () => String(++msgId);

export default function ResearchPage() {
  const [papers, setPapers] = useState<ResearchPaper[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [loadingPapers, setLoadingPapers] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPapers = useCallback(async () => {
    try {
      setLoadingPapers(true);
      const data = await getResearchPapers();
      setPapers(data);
    } catch {
      setPapers([]);
    } finally {
      setLoadingPapers(false);
    }
  }, []);

  useEffect(() => {
    fetchPapers();
  }, [fetchPapers]);

  const scrollToBottom = () => {
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  const handleFileSelect = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadStatus("Only PDF documents are supported.");
      return;
    }
    try {
      setUploading(true);
      setUploadStatus(`Parsing and embedding ${file.name}…`);
      const resp = await uploadResearchPaper(file);
      setUploadStatus(`Indexed ${file.name} (${resp.chunk_count} chunks).`);
      await fetchPapers();
      setSelectedPaperId(resp.paper_id);
      setTimeout(() => setUploadStatus(null), 6000);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to upload and index document.";
      setUploadStatus(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (e: React.MouseEvent, paperId: string) => {
    e.stopPropagation();
    try {
      await deleteResearchPaper(paperId);
      if (selectedPaperId === paperId) {
        setSelectedPaperId(null);
      }
      await fetchPapers();
    } catch {
      await fetchPapers();
    }
  };

  const sendQuestion = useCallback(
    async (question: string) => {
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: question,
        created_at: new Date().toISOString(),
      };

      const loadingMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: "",
        loading: true,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, loadingMsg]);
      setLoading(true);
      scrollToBottom();

      try {
        const result = await queryResearchPaper({
          question,
          paper_id: selectedPaperId,
          k: 6,
        });

        const assistantMsg: ChatMessage = {
          id: loadingMsg.id,
          role: "assistant",
          content: result.answer,
          sources: result.sources,
          retrieval_time_ms: result.retrieval_time_ms,
          context_chunks: result.context_chunks,
          model_used: result.model_used ?? undefined,
          created_at: result.created_at,
          loading: false,
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === loadingMsg.id ? assistantMsg : m))
        );
      } catch (err: unknown) {
        const errMsg =
          err instanceof Error
            ? err.message
            : "An error occurred querying the research assistant.";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === loadingMsg.id
              ? { ...m, loading: false, content: `⚠️ ${errMsg}` }
              : m
          )
        );
      } finally {
        setLoading(false);
        scrollToBottom();
      }
    },
    [selectedPaperId]
  );

  const selectedPaper = papers.find((p) => p.paper_id === selectedPaperId);
  const subtitleText = selectedPaper
    ? `Scoped to: ${selectedPaper.file_name}`
    : "Searching across all uploaded research papers";

  return (
    <>
      <TopBar
        title="Research Assistant"
        subtitle={subtitleText}
        badge={selectedPaper ? "Paper Focused" : "All Papers"}
        actions={
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <>
                <span className="spin">⟳</span> Uploading…
              </>
            ) : (
              <>+ Upload Paper</>
            )}
          </button>
        }
      />

      <div className="research-page-layout">
        <div className="research-sidebar-panel">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            accept=".pdf"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileSelect(e.target.files[0]);
              }
            }}
          />

          <div
            className={`research-dropzone ${dragActive ? "drag-active" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <div className="dropzone-title">
              {uploading ? "Processing PDF…" : "Upload Research Paper"}
            </div>
            <div className="dropzone-sub">
              Drag and drop PDF or click to browse
            </div>
          </div>

          {uploadStatus && (
            <div className="research-status-pill">{uploadStatus}</div>
          )}

          <div className="research-papers-section">
            <div className="research-papers-header">
              <span>Uploaded Papers ({papers.length})</span>
            </div>

            <button
              className={`paper-item-btn ${selectedPaperId === null ? "active" : ""}`}
              onClick={() => setSelectedPaperId(null)}
            >
              <div className="paper-item-name">All Uploaded Papers</div>
              <div className="paper-item-sub">Cross-paper synthesis</div>
            </button>

            {loadingPapers ? (
              <div className="empty-subtext">Loading library…</div>
            ) : papers.length === 0 ? (
              <div className="empty-subtext">
                No research papers uploaded yet. Upload a PDF above to begin.
              </div>
            ) : (
              papers.map((paper) => (
                <div
                  key={paper.paper_id}
                  className={`paper-item-btn ${
                    selectedPaperId === paper.paper_id ? "active" : ""
                  }`}
                  onClick={() => setSelectedPaperId(paper.paper_id)}
                >
                  <div className="paper-item-info">
                    <div className="paper-item-name" title={paper.file_name}>
                      {paper.file_name}
                    </div>
                    <div className="paper-item-sub">
                      {paper.chunk_count ?? 0} chunks · {new Date(paper.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    className="paper-del-btn"
                    title="Remove paper"
                    onClick={(e) => handleDelete(e, paper.paper_id)}
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="research-chat-panel">
          {messages.length === 0 ? (
            <div className="chat-messages">
              <div className="chat-empty">
                <h2 className="chat-empty-title">Research Document Assistant</h2>
                <p style={{ fontSize: 13, color: "var(--text-muted)", maxWidth: 500 }}>
                  Upload a research paper PDF to query theoretical foundations, methodologies, mathematical formulas, datasets, and experimental findings with verbatim citations.
                </p>
                {papers.length === 0 && (
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ marginTop: 16 }}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                  >
                    Upload Your First Paper
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="chat-messages">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}

          <ChatInput
            onSend={sendQuestion}
            loading={loading}
            placeholder={
              selectedPaper
                ? `Ask anything about ${selectedPaper.file_name}…`
                : "Ask about your uploaded research papers…"
            }
          />
        </div>
      </div>
    </>
  );
}
