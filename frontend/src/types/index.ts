export interface SourceChunk {
  document: string;
  source: string;
  relevance: number;
  distance: number;
}

export interface QueryRequest {
  question: string;
  k?: number;
}

export interface QueryResponse {
  question: string;
  answer: string;
  sources: SourceChunk[];
  retrieval_time_ms: number;
  context_chunks: number;
  model_used: string;
  created_at: string;
}

export interface DocumentOut {
  paper_id: string;
  source_name: string;
  title: string | null;
  retrieval_time: string | null;
  file_name: string | null;
  vectorization_status: "pending" | "vectorized" | "failed";
  chunk_count: number | null;
  vectorized_at: string | null;
  created_at: string;
}

export interface DocumentStats {
  total: number;
  vectorized: number;
  pending: number;
  failed: number;
  by_source: Record<string, number>;
}

export interface IngestResponse {
  run_id: number;
  status: string;
  message: string;
}

export interface IngestionRunOut {
  id: number;
  triggered_by: "scheduler" | "manual";
  started_at: string;
  completed_at: string | null;
  status: "running" | "completed" | "failed";
  articles_fetched: number;
  articles_vectorized: number;
  error_message: string | null;
}

export interface HealthService {
  postgres: string;
  chromadb: string;
  gemini_api: string;
}

export interface HealthResponse {
  status: string;
  services: HealthService;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  retrieval_time_ms?: number;
  context_chunks?: number;
  model_used?: string;
  created_at: string;
  loading?: boolean;
}

export interface ResearchPaper {
  paper_id: string;
  file_name: string;
  title: string | null;
  chunk_count: number | null;
  vectorization_status: string;
  created_at: string;
}

export interface ResearchUploadResponse {
  paper_id: string;
  file_name: string;
  chunk_count: number;
  message: string;
}

export interface ResearchQueryRequest {
  question: string;
  paper_id?: string | null;
  k?: number;
}

export interface ResearchQueryResponse {
  question: string;
  answer: string;
  sources: SourceChunk[];
  retrieval_time_ms: number;
  context_chunks: number;
  model_used: string | null;
  created_at: string;
}