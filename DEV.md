# Local Development Guide

## Prerequisites

- Python 3.12+
- Node.js 22+ and npm
- Podman (or Docker)
- Google Cloud CLI (`gcloud`) — for Vertex AI authentication
- PostgreSQL client (`psql`) — for ad-hoc queries

## 1. Quick Start

```bash
cp .env.template .env           # fill in your credentials
cp pipeline_types.yaml.example pipeline_types.yaml  # configure your pipeline types
pip install -e '.[dev]'         # install Python dependencies
./scripts/deploy_local.sh       # start containers, run migrations, load config
```

The deploy script handles everything: starts PostgreSQL + MinIO containers, waits
for them to be healthy, runs database migrations, and loads your pipeline type
definitions from `pipeline_types.yaml`.

### Required credentials in `.env`

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://dfd:dfd@localhost:5432/dfd` |
| `KUBEARCHIVE_URL` | KubeArchive API base URL | — |
| `KUBEARCHIVE_TOKEN` | KubeArchive bearer token (`sha256~...`) | — |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI | — |
| `GOOGLE_CLOUD_REGION` | Vertex AI region | `us-east5` |
| `CLAUDE_MODEL` | Claude model ID | `claude-sonnet-4-6` |
| `S3_ENDPOINT_URL` | MinIO endpoint | `http://localhost:9000` |
| `S3_BUCKET` | S3 bucket name | `dfd` |
| `AWS_ACCESS_KEY_ID` | MinIO access key | `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | MinIO secret key | `minioadmin` |
| `COLLECT_INTERVAL_HOURS` | Collector polling interval | `24` |
| `COLLECT_HOURS_BACK` | How far back to look for runs | `48` |

Authenticate with Google Cloud (required for Claude/Vertex AI):

```bash
gcloud auth application-default login
```

## 2. Running the Services

The deploy script starts all three services in the background automatically.
Logs are in `logs/api.log`, `logs/dashboard.log`, and `logs/collector.log`.

```bash
tail -f logs/*.log          # tail all logs
kill $(cat logs/*.pid)      # stop all services
```

To run services manually instead (e.g., for debugging):

```bash
source .env
uvicorn dfd.api.main:app --host 0.0.0.0 --port 8080 --reload  # API (port 8080)
cd src/dfd/dashboard && npm run dev                             # Dashboard (port 5173)
source .env && python -m dfd.collector.main                     # Collector
```

Open <http://localhost:5173> for the dashboard with hot-reload.

## 3. Common Workflows

### Run collector once with custom time window

```bash
source .env
COLLECT_HOURS_BACK=24 python -m dfd.collector.main
# Ctrl+C after the first run completes (before the next poll cycle)
```

### Rebuild dashboard for static serving

The API on port 8080 serves pre-built static files. To update them:

```bash
cd src/dfd/dashboard
npm run build    # outputs to src/dfd/api/static/
```

### Reset the database

```bash
source .env
psql "$DATABASE_URL" -c "
TRUNCATE TABLE
  investigation_board, cost_entries, artifacts, analyses,
  re_analysis_queue, rule_proposals, conversation_logs,
  chat_messages, chat_sessions, collect_requests,
  pipeline_runs, analysis_runs, taxonomy_rules
CASCADE;
"
```

Pipeline types are preserved (separate table). To fully reset, drop and re-run migrations:

```bash
psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
python scripts/migrate.py
```

### Check MinIO contents

Console: <http://localhost:9001> (login: `minioadmin`/`minioadmin`)

CLI:

```bash
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
  aws --endpoint-url http://localhost:9000 s3 ls s3://dfd/ --recursive
```

## 4. Testing and Linting

```bash
pytest                     # run all tests
ruff check src/ tests/     # lint
ruff format src/ tests/    # auto-format
```

## 5. Architecture

```
KubeArchive API          Google Vertex AI (Claude)
     |                          |
     v                          v
 Collector  ──────────>  Analyzer (multi-agent)
     |                          |
     v                          v
 PostgreSQL  <──────────────────┘
     |
     v
 FastAPI (port 8080)  ──>  MinIO (conversation logs)
     |
     v
 React Dashboard (port 5173 dev / 8080 static)
```

**Pipeline types**: `build`, `integration_test`, `enterprise_contract`, `release`

The collector fetches pipeline runs from KubeArchive, stores them in PostgreSQL,
and triggers multi-agent analysis (via Claude) for failures. The API serves the
dashboard and provides REST endpoints for runs, analyses, taxonomy, and chat.

## 6. Gotchas

- **Port 8080 vs 5173**: Port 8080 serves pre-built static files — no hot-reload.
  Use port 5173 (Vite dev server) during frontend development. Vite proxies
  `/api` requests to port 8080 automatically.

- **Vite proxy changes require restart**: Editing `vite.config.ts` proxy settings
  does not hot-reload. Stop and restart `npm run dev`.

- **Never commit `.env` or `credentials.json`**: Both contain live credentials
  and are in `.gitignore`. Use `.env.template` as the reference.

- **Collector runs continuously**: It polls every `COLLECT_POLL_INTERVAL_SECONDS`
  (default 30s). For one-shot runs, Ctrl+C after the first analysis completes.

- **KubeArchive token expiry**: If the collector logs `401`/`403`, refresh your
  KubeArchive token and update `.env`.
