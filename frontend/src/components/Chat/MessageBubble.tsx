import ReactMarkdown from "react-markdown";
import { format } from "date-fns";
import type { ChatMessage } from "@/types";
import SourceCard from "@/components/Chat/SourceCard";

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message ${message.role}`}>
      <span className="message-role">{isUser ? "You" : "Assistant"}</span>

      <div className="message-bubble">
        {message.loading ? (
          <div className="typing-dot">
            <span />
            <span />
            <span />
          </div>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>

      {!message.loading && (
        <>
          {message.sources && message.sources.length > 0 && (
            <div className="source-chips">
              <span className="source-chips-label">Sources:</span>
              {message.sources.map((src, idx) => (
                <SourceCard key={idx} source={src} />
              ))}
            </div>
          )}

          <div className="message-meta">
            <span>{format(new Date(message.created_at), "HH:mm:ss")}</span>
            {!isUser && message.retrieval_time_ms != null && (
              <>
                <span>·</span>
                <span>{message.retrieval_time_ms.toFixed(0)} ms</span>
              </>
            )}
            {!isUser && message.context_chunks != null && (
              <>
                <span>·</span>
                <span>{message.context_chunks} chunks</span>
              </>
            )}
            {!isUser && message.model_used && (
              <>
                <span>·</span>
                <span className="text-mono">{message.model_used}</span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
