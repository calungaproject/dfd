#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!!]${NC} $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── 1. Check .env ──────────────────────────────────────────────────────
echo "=== DFD3 Local Deployment ==="
echo

if [ ! -f .env ]; then
    fail ".env not found. Copy .env.template to .env and fill in your credentials."
fi
# shellcheck disable=SC1091
source .env

REQUIRED_VARS=(DATABASE_URL KUBEARCHIVE_URL KUBEARCHIVE_TOKEN GOOGLE_CLOUD_PROJECT)
missing=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        missing+=("$var")
    fi
done
if [ ${#missing[@]} -gt 0 ]; then
    fail "Missing required env vars in .env: ${missing[*]}"
fi
info "Environment variables loaded"

# ── 2. Check pipeline_types.yaml ───────────────────────────────────────
if [ ! -f pipeline_types.yaml ]; then
    fail "pipeline_types.yaml not found. Copy pipeline_types.yaml.example and edit it."
fi
info "pipeline_types.yaml found"

# ── 3. Check required tools ────────────────────────────────────────────
for cmd in python psql; do
    command -v "$cmd" >/dev/null 2>&1 || fail "'$cmd' not found in PATH."
done

COMPOSE_CMD=""
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    COMPOSE_CMD="podman compose"
else
    fail "No compose tool found. Install podman-compose or docker-compose."
fi
info "Using compose tool: $COMPOSE_CMD"

# ── 4. Start containers ───────────────────────────────────────────────
echo
echo "Starting containers..."
$COMPOSE_CMD up -d

# ── 5. Wait for PostgreSQL ─────────────────────────────────────────────
echo -n "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if pg_isready -h localhost -p 5432 -U dfd >/dev/null 2>&1; then
        echo ""
        info "PostgreSQL is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo ""
        fail "PostgreSQL did not become ready within 30 seconds"
    fi
    echo -n "."
    sleep 1
done

# ── 6. Wait for MinIO ─────────────────────────────────────────────────
echo -n "Waiting for MinIO..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; then
        echo ""
        info "MinIO is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo ""
        warn "MinIO health check timed out (non-fatal, may still be initializing)"
        break
    fi
    echo -n "."
    sleep 1
done

# ── 7. Run migrations ─────────────────────────────────────────────────
echo
echo "Running database migrations..."
python scripts/migrate.py

# ── 8. Load pipeline types ─────────────────────────────────────────────
echo
echo "Loading pipeline types..."
python scripts/load_pipeline_types.py

# ── 9. Install dashboard dependencies ─────────────────────────────────
echo
echo "Installing dashboard dependencies..."
(cd src/dfd/dashboard && npm install --silent)
info "Dashboard dependencies installed"

# ── 10. Start services ────────────────────────────────────────────────
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

start_service() {
    local name="$1"; shift
    local logfile="$LOG_DIR/$name.log"
    local pidfile="$LOG_DIR/$name.pid"

    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        warn "$name already running (PID $(cat "$pidfile")), skipping"
        return
    fi

    "$@" > "$logfile" 2>&1 &
    echo $! > "$pidfile"
    info "$name started (PID $!, log: logs/$name.log)"
}

echo
echo "Starting services..."
start_service api uvicorn dfd.api.main:app --host 0.0.0.0 --port 8080 --reload
start_service dashboard sh -c "cd $PROJECT_DIR/src/dfd/dashboard && npx vite --host"
start_service collector python -m dfd.collector.main

sleep 2

for svc in api dashboard collector; do
    pidfile="$LOG_DIR/$svc.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        :
    else
        warn "$svc may have failed to start — check logs/$svc.log"
    fi
done

# ── 11. Summary ───────────────────────────────────────────────────────
echo
echo "=== Deployment complete ==="
echo
echo "Pipeline types in database:"
psql "$DATABASE_URL" -c "SELECT id, namespace, description FROM pipeline_types ORDER BY id" 2>/dev/null
echo
echo "Services running:"
echo "  API:        http://localhost:8080  (log: logs/api.log)"
echo "  Dashboard:  http://localhost:5173  (log: logs/dashboard.log)"
echo "  Collector:  running in background  (log: logs/collector.log)"
echo
echo "Tail all logs:  tail -f logs/*.log"
echo "Stop services:  kill \$(cat logs/*.pid)"
echo
echo "Dashboard: http://localhost:5173"
