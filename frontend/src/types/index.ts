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
export interface NewsSource {
  source_name: string;
  group: string;
  url: string;
  document_count: number;
  last_fetched: string | null;
}

export interface SourcesResponse {
  total_sources: number;
  groups: Record<string, number>;
  sources: NewsSource[];
}

export interface RetrievalMetrics {
  updated_at: string | null;
  relevance: { total: number; relevant: number; relevance_score: number };
  "precision@6": { queries: number; total: number; relevant: number; precision_score: number | null };
  "recall@6": { queries: number; evaluated_queries: number; recall_score: number | null; status: string };
  contextual_precision: { queries: number; contextual_precision_score: number | null };
  recent_precision: { total: number; relevant: number; precision_score: number };
  historical_precision: { total: number; relevant: number; precision_score: number };
  temporal_assignment: { verified: number; correct: number; accuracy_score: number | null; unknown_timestamp_count: number };
  retrieval_latency_ms: { count: number; last: number | null; average: number | null; total: number };
  chunks_retrieved: { total: number; recent: number; historical: number; unknown_source: number };
  last_call: {
    query: string;
    source: string;
    retrieved: number;
    relevant_estimate: number;
    relevance_score: number;
    retrieval_time_ms: number | null;
  } | null;
  methodology: Record<string, string>;
}

export interface SeparationResult {
  historical_moved: number;
  unknown_moved: number;
  total_moved: number;
  recent_retained: number;
  ran_at: string;
}

export interface VectorStats {
  recent_chunks: number;
  historical_chunks: number;
}

export interface NewsSummary {
  summary: string;
  generated_at: string;
  generation_time_ms: number | null;
}

export interface UserPreferences {
  user_name?: string;
  news_categories?: string[];
  specific_interests?: string[];
  summary_detail?: string;
  topics_to_avoid?: string[];
}

