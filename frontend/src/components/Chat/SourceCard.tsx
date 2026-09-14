import type { SourceChunk } from "@/types";

interface Props {
  source: SourceChunk;
}

export default function SourceCard({ source }: Props) {
  const fileName = source.source.replace(/^.*[\\/]/, "");
  const score = (source.relevance * 100).toFixed(0);

  return (
    <span
      className="source-chip"
      title={source.document.slice(0, 200)}
    >
      {fileName}
      <span className="source-chip-score">{score}%</span>
    </span>
  );
}
