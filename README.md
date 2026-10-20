# Continual RAG: Continuously Learning News Intelligence & Research Assistant

Continual RAG is an end-to-end Retrieval-Augmented Generation platform designed for real-time news monitoring, automated multi-source ingestion, personalized news generation, temporal knowledge separation, and research document synthesis.

The system continuously acquires unstructured news articles across 30+ regional, national, and global RSS streams, parses and splits document contents, generates dense vector representations using Sentence Transformers, and indexes them into partitioned vector databases. Queries and personalized summaries are generated using Google Gemini models grounded strictly in retrieved context.

---

## Architectural Overview

The application is structured into decoupled frontend, backend, database, and background processing layers.

```mermaid
flowchart TD
    subgraph ClientLayer [Frontend React + Vite]
        UI[Web UI]
        Auth[Clerk Auth Gate]
        Pages[Chat / Summary / Research / Ingestion / Metrics / Sources / Dashboard]
    end

    subgraph GatewayLayer [API Gateway]
        ViteProxy[Vite Dev Server Proxy]
        FastAPI[FastAPI Server :8000]
        Limiter[SlowAPI Rate Limiter]
    end

    subgraph WorkerLayer [Background Processing]
        APSched[APScheduler In-Process]
        RedisQueue[Redis Message Broker]
        CeleryWorker[Celery Worker -P solo]
    end

    subgraph StorageLayer [Persistence & Indices]
        Postgres[(PostgreSQL Metadata DB)]
        RecentChroma[(ChromaDB: recent_news_docs)]
        HistChroma[(ChromaDB: historical_news_docs)]
        RSSStore[(File System PDF Archive)]
        Tracker[(SQLite URL Deduplication Tracker)]
    end

    subgraph ModelLayer [AI & Embeddings]
        ST[sentence-transformers/all-MiniLM-L6-v2]
        Gemini[Google Gemini API]
    end

    UI --> Auth
    Auth --> Pages
    Pages --> ViteProxy
    ViteProxy --> FastAPI
    FastAPI --> Limiter
    FastAPI --> Postgres
    FastAPI --> RecentChroma
    FastAPI --> HistChroma
    FastAPI --> Gemini
    FastAPI --> APSched

    APSched --> RedisQueue
    RedisQueue --> CeleryWorker
    CeleryWorker --> RSSStore
    CeleryWorker --> Tracker
    CeleryWorker --> ST
    ST --> RecentChroma
    CeleryWorker --> Postgres
```

---

## Key Features

### 1. Dual Vector Store & Continual Separation

To prevent stale news from diluting breaking developments, the platform separates vector embeddings into two distinct ChromaDB collections backed by SQLite (`chroma.sqlite3`) as the vector storage engine:

- `recent_news_docs`: Contains articles published or ingested within the active retention window (24 hours to 3 days) stored in `app/vector_db/chroma.sqlite3`.
- `historical_news_docs`: Contains archived news beyond 24 hours stored in `app/historical_vector_db/chroma.sqlite3`.
  An automated separation pipeline migrates older embeddings from the active collection to the historical archive, maintaining high retrieval precision for current events while preserving historical context.

### 2. Automated RSS Ingestion Pipeline

Background ingestion runs every 20 minutes (or on manual trigger):

- Fetches articles from verified news sources including National, State, Politics, World, Technology, Business, Sports, and Entertainment feeds.
- Deduplicates article URLs using SHA-256 hashes in `tracker.db` (SQLite).
- Formats article texts into structured PDF documents using ReportLab.
- Extracts text via PyPDF and splits it into semantic chunks with LangChain RecursiveCharacterTextSplitter.
- Embeds chunks with `sentence-transformers/all-MiniLM-L6-v2` and commits them to ChromaDB SQLite vector storage.
- Stores document metadata, chunk counts, timestamps, and ingestion run stats in PostgreSQL.

### 3. Personal News Feed Generation

The Personal News Feed synthesizes customized multi-category digests:

- Uses stored user preferences (preferred categories, specific keyword interests, summary detail level).
- Pulls top readable candidates per category with automatic fallback across all available sources.
- Filters corrupted character encodings and non-readable blocks.
- Prompts Google Gemini to deliver concise headlines, factual bullet summaries, and key takeaways without placeholders or empty sections.

### 4. Interactive RAG Chat

- Grounded question-answering with citation tracking.
- Dynamic selection between Recent, Historical, or Combined knowledge bases.
- Measures retrieval latency, context relevance scores, and stores complete query logs in PostgreSQL.

### 5. Research Assistant

- Upload and inspect academic papers and arbitrary PDF documents.
- Dedicated vector indexing per paper ID.
- Isolated question-answering against user-uploaded documents.

### 6. Retrieval Metrics & Recall@K Benchmarking

- Tracks Precision@K, Recall@K, hit rate, and latency distribution.
- Includes an automated benchmark evaluation runner executing test queries against the live vector collection.

### 7. User Authentication & Profile Synchronization

- Clerk Authentication with Google Social Login and Email sign-in.
- Automatic backend sync endpoint updating PostgreSQL user records on login.

---

## Technology Stack

### Backend

- Framework: FastAPI, Uvicorn
- Asynchronous DB Engine: SQLAlchemy with AsyncPG
- Relational Database: PostgreSQL 14+
- Vector Database: ChromaDB (SQLite 3.35+ persistence engine + HNSW index)
- Local Tracking Database: SQLite 3 (`tracker.db`, `metadata.db`)
- Task Queue & Scheduler: Celery, Redis (Upstash or local), APScheduler
- Embedding Model: HuggingFace `sentence-transformers/all-MiniLM-L6-v2`
- Large Language Model: Google Gemini API (`google-genai` SDK)
- Document Processing: LangChain, PyPDF, ReportLab, Feedparser
- Rate Limiting: SlowAPI

### Frontend

- Framework: React 18, TypeScript, Vite
- Routing: React Router DOM v6
- Styling: Custom Vanilla CSS Design System (Dark mode, glassmorphic UI, responsive layouts)
- Authentication: Clerk React (`@clerk/clerk-react`, `@clerk/themes`)
- HTTP Client: Axios
- Markdown Rendering: React Markdown

---

## Directory Structure

```
Continual_RAG/
├── backend/
│   ├── alembic.ini
│   ├── docker-compose.yml
│   ├── metadata.db
│   ├── tracker.db
│   ├── requirements.txt
│   ├── .env
│   ├── .env.example
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   └── app/
│       ├── __init__.py
│       ├── fetch_news.py
│       ├── store_vector.py
│       ├── retrive.py
│       ├── separate_recent_data.py
│       ├── summary.py
│       ├── news_response.py
│       ├── record_metrics.py
│       ├── main.py
│       ├── latest_summary.json
│       ├── metrics.json
│       ├── user_preferences.json
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── documents.py
│       │       ├── health.py
│       │       ├── ingest.py
│       │       ├── pipeline.py
│       │       ├── query.py
│       │       ├── research.py
│       │       └── users.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── limiter.py
│       │   ├── logging.py
│       │   └── redis.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── session.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── documents.py
│       │   ├── health.py
│       │   ├── ingest.py
│       │   ├── query.py
│       │   └── research.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── ingest_service.py
│       │   ├── metadata_service.py
│       │   ├── pipeline_service.py
│       │   ├── query_service.py
│       │   └── research_service.py
│       ├── workers/
│       │   ├── __init__.py
│       │   ├── celery_app.py
│       │   ├── scheduler.py
│       │   └── tasks.py
│       ├── vector_db/
│       ├── historical_vector_db/
│       ├── news_database/
│       └── research_database/
└── frontend/
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── .env
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css
        ├── api/
        │   └── client.ts
        ├── components/
        │   ├── Auth/
        │   │   └── AuthGate.tsx
        │   └── Layout/
        │       ├── Sidebar.tsx
        │       └── TopBar.tsx
        ├── pages/
        │   ├── ChatPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── IngestPage.tsx
        │   ├── MetricsPage.tsx
        │   ├── ResearchPage.tsx
        │   ├── SourcesPage.tsx
        │   └── SummaryPage.tsx
        └── types/
            └── index.ts
```

---

## Environment Variables Configuration

### Backend Environment File: `backend/.env`

Create `backend/.env` with the following variables:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=continual_rag
POSTGRES_PORT=5432

DATABASE_URL=postgresql+asyncpg://postgres:your_postgres_password@localhost:5432/continual_rag
SQLITE_DB_URL=sqlite:///app/vector_db/chroma.sqlite3

REDIS_URL=rediss://default:your_redis_token@your_redis_host:6379

GEMINI_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash

APP_DIR=app
FETCH_INTERVAL_MINUTES=20
QUERY_RATE_LIMIT=5/minute
INGEST_RATE_LIMIT=2/minute

BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

USE_TF=0
TRANSFORMERS_NO_TF=1
USE_TORCH=1
TF_ENABLE_ONEDNN_OPTS=0

CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key
```

### Explanation of Backend Variables

| Variable                 | Description                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------- |
| `POSTGRES_USER`          | PostgreSQL superuser username.                                                         |
| `POSTGRES_PASSWORD`      | Password for PostgreSQL user.                                                          |
| `POSTGRES_DB`            | Name of the database for continual RAG metadata.                                       |
| `POSTGRES_PORT`          | Port exposed by PostgreSQL (default: 5432).                                            |
| `DATABASE_URL`           | Async connection string used by SQLAlchemy (`postgresql+asyncpg://...`).               |
| `SQLITE_DB_URL`          | Path to the active Chroma vector database (`sqlite:///app/vector_db/chroma.sqlite3`).  |
| `REDIS_URL`              | Redis URL for Celery message brokering. Supports `rediss://` for TLS connections.      |
| `GEMINI_API_KEY`         | Google AI Studio Gemini API Key.                                                       |
| `GEMINI_MODEL`           | Gemini model variant (e.g., `gemini-2.0-flash`, `gemini-3.5-flash-lite`).              |
| `APP_DIR`                | Name of the inner application directory (`app`).                                       |
| `FETCH_INTERVAL_MINUTES` | Frequency of scheduled background RSS ingestion runs.                                  |
| `QUERY_RATE_LIMIT`       | Per-client rate limit for query endpoints.                                             |
| `INGEST_RATE_LIMIT`      | Per-client rate limit for manual ingestion triggers.                                   |
| `BACKEND_CORS_ORIGINS`   | JSON array of allowed origins for browser CORS headers.                                |
| `USE_TORCH` / `USE_TF`   | Forces HuggingFace and Sentence Transformers to utilize PyTorch instead of TensorFlow. |
| `CLERK_PUBLISHABLE_KEY`  | Clerk frontend publishable authentication key.                                         |
| `CLERK_SECRET_KEY`       | Clerk backend API secret key for session and user verification.                        |

### Frontend Environment File: `frontend/.env`

Create `frontend/.env` with:

```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key
```

---

## Installation & Setup Instructions

### Prerequisites

1. Python 3.11, 3.12, or 3.13 installed.
2. Node.js 18.x or higher and npm installed.
3. PostgreSQL 14+ running locally or through Docker.
4. SQLite 3 (version 3.35.0 or higher) installed on the system (required as the underlying storage engine for ChromaDB vector databases `vector_db` and `historical_vector_db`, as well as URL tracking `tracker.db` and metadata cache `metadata.db`).
5. Redis instance running locally or via cloud provider (e.g., Upstash Redis).
6. A Google Gemini API Key from Google AI Studio.
7. A Clerk application configured with Google or Email authentication.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/aravindnayagamu/Final_Year_Mini_Project-Continuously_Learning_RAG.git
cd Final_Year_Mini_Project-Continuously_Learning_RAG
```

---

### Step 2: Database Setup

#### Option A: Using Docker Compose

If using Docker, start PostgreSQL using the provided Compose configuration:

```bash
cd backend
docker-compose up -d
cd ..
```

#### Option B: Using Local PostgreSQL

If using a native PostgreSQL installation:

1. Start the PostgreSQL service.
2. Open psql or pgAdmin and run:

```sql
CREATE DATABASE continual_rag;
```

---

### Step 3: Backend Setup

1. Open a terminal and enter the `backend` folder:

```bash
cd backend
```

2. Create and activate a Python virtual environment:

On Windows:

```cmd
python -m venv venv
venv\Scripts\activate
```

On Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install required Python packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. Verify that `backend/.env` is created with your valid credentials (`DATABASE_URL`, `GEMINI_API_KEY`, `REDIS_URL`, `CLERK_SECRET_KEY`, etc.).

5. Run database schema creation and launch the API server:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will automatically create all missing PostgreSQL tables on startup and will be accessible at:

- API Base: `http://127.0.0.1:8000/api/v1`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/v1/health`

---

### Step 4: Background Celery Worker Setup

In a separate terminal, activate the virtual environment and launch the Celery ingestion worker:

On Windows:

```cmd
cd backend
venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info -P solo
```

On Linux / macOS:

```bash
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info -P threads -c 4
```

The worker connects to Redis and executes async news fetching, vectorization, and maintenance separation tasks.

---

### Step 5: Frontend Setup

1. Open a separate terminal and navigate to the `frontend` folder:

```bash
cd frontend
```

2. Install Node dependencies:

```bash
npm install
```

3. Ensure `frontend/.env` contains your `VITE_CLERK_PUBLISHABLE_KEY`.

4. Start the Vite development server:

```bash
npm run dev
```

5. Open your browser and navigate to:

```
http://localhost:5173
```

---

## API Reference

All endpoints are prefixed with `/api/v1`.

### Health & System

| Method | Endpoint  | Description                                                                  |
| ------ | --------- | ---------------------------------------------------------------------------- |
| `GET`  | `/health` | Reports overall API, PostgreSQL, ChromaDB, Redis, Celery, and Gemini health. |

### Query & Chat

| Method | Endpoint | Description                                                                                                                  |
| ------ | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `POST` | `/query` | Executes RAG similarity retrieval and answers queries using Gemini. Accepts `timeframe` ("recent", "historical", or "both"). |

### Ingestion & Documents

| Method | Endpoint            | Description                                                               |
| ------ | ------------------- | ------------------------------------------------------------------------- |
| `POST` | `/ingest`           | Manually triggers an RSS fetching and vectorization run.                  |
| `GET`  | `/ingest/runs`      | Returns historical ingestion run records and status counts.               |
| `GET`  | `/ingest/runs/{id}` | Returns a single ingestion run details.                                   |
| `GET`  | `/documents`        | Paginated listing of stored document records in PostgreSQL.               |
| `GET`  | `/documents/stats`  | Aggregate counts of total documents, vectorization statuses, and sources. |
| `GET`  | `/sources`          | Detailed list of configured RSS sources and current document counts.      |

### News Summary & Personalization

| Method | Endpoint               | Description                                                             |
| ------ | ---------------------- | ----------------------------------------------------------------------- |
| `GET`  | `/summary`             | Retrieves the most recently generated news summary JSON.                |
| `POST` | `/summary`             | Generates a fresh personalized multi-category news digest using Gemini. |
| `GET`  | `/summary/preferences` | Fetches active user personalization preferences.                        |
| `POST` | `/summary/preferences` | Saves categories, interests, and detail level configurations.           |

### Maintenance & Continual Learning

| Method | Endpoint                       | Description                                                               |
| ------ | ------------------------------ | ------------------------------------------------------------------------- |
| `GET`  | `/maintenance/vector-stats`    | Returns chunk counts in `recent_store` and `historical_store`.            |
| `POST` | `/maintenance/separate-recent` | Moves documents older than 24 hours from recent collection to historical. |

### Retrieval Metrics & Evaluation

| Method | Endpoint             | Description                                                        |
| ------ | -------------------- | ------------------------------------------------------------------ |
| `GET`  | `/metrics`           | Fetches current Precision@K, query counts, and latency statistics. |
| `POST` | `/metrics/reset`     | Resets in-memory and persisted retrieval metrics counters.         |
| `POST` | `/metrics/benchmark` | Runs an automated Recall@K evaluation benchmark on sample queries. |

### Research Papers

| Method   | Endpoint                | Description                                                                |
| -------- | ----------------------- | -------------------------------------------------------------------------- |
| `POST`   | `/research/upload`      | Uploads a research paper PDF and chunks it into the research vector index. |
| `GET`    | `/research/papers`      | Lists uploaded research papers and chunk statistics.                       |
| `POST`   | `/research/query`       | Queries a specific uploaded research paper.                                |
| `DELETE` | `/research/papers/{id}` | Deletes a research paper and its vector index chunks.                      |

### User Authentication Sync

| Method | Endpoint      | Description                                                             |
| ------ | ------------- | ----------------------------------------------------------------------- |
| `POST` | `/users/sync` | Upserts authenticated Clerk user details into PostgreSQL `users` table. |

---

## Production Build & Deployment

### Building the Frontend

To create an optimized production build of the React frontend:

```bash
cd frontend
npm run build
```

The compiled assets will be written to `frontend/dist`. These can be served using Nginx, Cloudflare Pages, Vercel, or through FastAPI static files.

### Running Backend with Multiple Workers

In production environments on Linux:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Troubleshooting Guide

### 1. Vector Store Access Violation or 502 Error

- Ensure `SQLITE_DB_URL` in `backend/.env` points to `sqlite:///app/vector_db/chroma.sqlite3`.
- If an old collection was corrupted by concurrent process locks, remove the corrupt directory and re-run ingestion to populate fresh indices.

### 2. Celery Worker on Windows

- Windows does not support default Celery fork mechanisms. Always run the worker with the `-P solo` pool option:

```cmd
celery -A app.workers.celery_app worker --loglevel=info -P solo
```

### 3. Upstash Redis TLS Handshake

- Upstash URLs starting with `rediss://` enforce TLS.
- The Celery configuration in `app/workers/celery_app.py` automatically injects `ssl_cert_reqs=CERT_NONE` when `rediss://` is detected to ensure seamless connections across corporate or cloud networks.

### 4. Port 8000 Already in Use

- Check and terminate any stale Python or Uvicorn instances:

On Windows:

```powershell
Get-Process python | Stop-Process -Force
```

On Linux / macOS:

```bash
lsof -ti :8000 | xargs kill -9
```

### 5. Missing Gemini API Key

- Ensure `GEMINI_API_KEY` is present in `backend/.env`.
- Verify key validity at Google AI Studio. Without a valid key, query and summary endpoints will return an HTTP 500 error.

---

## Authors

- **Aravind Nayagam U**: [@aravindnayagamu](https://github.com/aravindnayagamu)
- **S Vishwajith**: [@VishwajithS2005](https://github.com/VishwajithS2005)
- **Kshitij S**: [@ksh-20](https://github.com/ksh-20)
