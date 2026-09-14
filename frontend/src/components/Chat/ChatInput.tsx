import { useRef, useState } from "react";

interface Props {
  onSend: (question: string) => void;
  loading: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, loading, placeholder }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setText("");
    if (ref.current) {
      ref.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${ref.current.scrollHeight}px`;
    }
  };

  return (
    <div className="chat-input-area">
      <div className="chat-input-box">
        <textarea
          ref={ref}
          className="chat-textarea"
          placeholder={placeholder || "Ask anything about recent news…"}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!text.trim() || loading}
          aria-label="Send message"
        >
          {loading ? (
            <span className="spin" style={{ fontSize: 14 }}>⟳</span>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
      <p className="chat-hint">
        Press <kbd style={{ background: "var(--bg-elevated)", padding: "1px 5px", borderRadius: 3, fontSize: 11, border: "1px solid var(--border)" }}>Enter</kbd> to send · <kbd style={{ background: "var(--bg-elevated)", padding: "1px 5px", borderRadius: 3, fontSize: 11, border: "1px solid var(--border)" }}>Shift+Enter</kbd> for newline
      </p>
    </div>
  );
}
