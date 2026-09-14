import axios from "axios";
import type {
  QueryRequest,
  QueryResponse,
  DocumentOut,
  DocumentStats,
  IngestResponse,
  IngestionRunOut,
  HealthResponse,
  ResearchPaper,
  ResearchUploadResponse,
  ResearchQueryRequest,
  ResearchQueryResponse,
} from "@/types";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 120_000,
});

export const postQuery = (payload: QueryRequest): Promise<QueryResponse> =>
  api.post<QueryResponse>("/query", payload).then((r) => r.data);

export const getDocuments = (
  page = 1,
  pageSize = 20
): Promise<DocumentOut[]> =>
  api
    .get<DocumentOut[]>("/documents", { params: { page, page_size: pageSize } })
    .then((r) => r.data);

export const getDocumentStats = (): Promise<DocumentStats> =>
  api.get<DocumentStats>("/documents/stats").then((r) => r.data);

export const triggerIngest = (): Promise<IngestResponse> =>
  api.post<IngestResponse>("/ingest").then((r) => r.data);

export const getIngestionRuns = (): Promise<IngestionRunOut[]> =>
  api.get<IngestionRunOut[]>("/ingest/runs").then((r) => r.data);

export const getIngestionRun = (id: number): Promise<IngestionRunOut> =>
  api.get<IngestionRunOut>(`/ingest/runs/${id}`).then((r) => r.data);

export const getHealth = (): Promise<HealthResponse> =>
  api.get<HealthResponse>("/health").then((r) => r.data);

export const uploadResearchPaper = (file: File): Promise<ResearchUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  return api
    .post<ResearchUploadResponse>("/research/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 180_000,
    })
    .then((r) => r.data);
};

export const getResearchPapers = (): Promise<ResearchPaper[]> =>
  api.get<ResearchPaper[]>("/research/papers").then((r) => r.data);

export const queryResearchPaper = (
  payload: ResearchQueryRequest
): Promise<ResearchQueryResponse> =>
  api.post<ResearchQueryResponse>("/research/query", payload).then((r) => r.data);

export const deleteResearchPaper = (paperId: string): Promise<{ status: string }> =>
  api.delete<{ status: string }>(`/research/papers/${paperId}`).then((r) => r.data);
