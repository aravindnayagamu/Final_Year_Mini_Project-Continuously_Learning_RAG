import axios from "axios";
import type {
  QueryRequest,
  QueryResponse,
  DocumentOut,
  DocumentStats,
  IngestResponse,
  IngestionRunOut,
  HealthResponse,
} from "@/types";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
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
