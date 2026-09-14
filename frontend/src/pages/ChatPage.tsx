import { useCallback, useRef, useState } from "react";
import TopBar from "@/components/Layout/TopBar";
import MessageBubble from "@/components/Chat/MessageBubble";
import ChatInput from "@/components/Chat/ChatInput";
import { postQuery, triggerIngest } from "@/api/client";
import type { ChatMessage } from "@/types";

let msgId = 0;
const nextId = () => String(++msgId);

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [pullingNews, setPullingNews] = useState(false);
  const [pullMessage, setPullMessage] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  const handlePullNews = async () => {
    try {
      setPullingNews(true);
      setPullMessage("Fetching & vectorizing latest news…");
      const resp = await triggerIngest();
      setPullMessage(resp.message || "News ingestion triggered successfully!");
      setTimeout(() => setPullMessage(null), 6000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to pull news";
      setPullMessage(msg);
      setTimeout(() => setPullMessage(null), 5000);
    } finally {
      setPullingNews(false);
    }
  };

  const sendQuestion = useCallback(async (question: string) => {
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
      const result = await postQuery({ question, k: 5 });

      const assistantMsg: ChatMessage = {
        id: loadingMsg.id,
        role: "assistant",
        content: result.answer,
        sources: result.sources,
        retrieval_time_ms: result.retrieval_time_ms,
        context_chunks: result.context_chunks,
        model_used: result.model_used,
        created_at: result.created_at,
        loading: false,
      };

      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? assistantMsg : m))
      );
    } catch (err: unknown) {
      let errMsg = "An error occurred. Please try again.";
      if (err && typeof err === "object") {
        const axiosErr = err as {
          response?: { data?: { error?: string; detail?: string } };
          message?: string;
        };
        errMsg =
          axiosErr.response?.data?.error ||
          axiosErr.response?.data?.detail ||
          axiosErr.message ||
          errMsg;
      } else if (err instanceof Error) {
        errMsg = err.message;
      }
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
  }, []);

  const isEmpty = messages.length === 0;

  return (
    <>
      <TopBar
        title="Chat"
        subtitle="Ask questions about recent news"
        badge="RAG + Gemini"
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {pullMessage && (
              <span style={{ fontSize: 12, color: "var(--teal)" }}>
                {pullMessage}
              </span>
            )}
            <button
              className="btn btn-secondary btn-sm"
              onClick={handlePullNews}
              disabled={pullingNews}
            >
              {pullingNews ? (
                <>
                  <span className="spin">⟳</span> Pulling News…
                </>
              ) : (
                <>Pull Latest News</>
              )}
            </button>
          </div>
        }
      />

      <div className="chat-page">
        {isEmpty ? (
          <div className="chat-messages">
            <div className="chat-empty">
              <h2 className="chat-empty-title">Ask anything about recent news</h2>
              <p style={{ fontSize: 13, color: "var(--text-muted)", maxWidth: 460 }}>
                Your questions are answered using articles continuously fetched from live news feeds and stored in ChromaDB.
              </p>
              <button
                className="btn btn-primary btn-sm"
                style={{ marginTop: 16 }}
                onClick={handlePullNews}
                disabled={pullingNews}
              >
                {pullingNews ? (
                  <>
                    <span className="spin">⟳</span> Pulling News…
                  </>
                ) : (
                  <>Pull Latest News Now</>
                )}
              </button>
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

        <ChatInput onSend={sendQuestion} loading={loading} />
      </div>
    </>
  );
}
