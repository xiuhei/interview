#!/usr/bin/env bash
# =============================================================================
# AI Interview Platform - staged deployment script
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }
stage()   { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

get_dotenv_value() {
    local key="$1"
    local env_file="$PROJECT_DIR/.env"
    if [ ! -f "$env_file" ]; then
        return 0
    fi
    grep -E "^${key}=" "$env_file" | tail -n 1 | cut -d= -f2-
}

ensure_image_reference() {
    local key="$1"
    local fallback="$2"
    local configured="${!key:-}"

    if [ -z "$configured" ]; then
        configured="$(get_dotenv_value "$key")"
    fi

    if [ -z "$configured" ]; then
        configured="$fallback"
    fi

    if docker manifest inspect "$configured" >/dev/null 2>&1; then
        export "$key=$configured"
        info "Using ${key}=${configured}"
        return 0
    fi

    warn "${key}=${configured} is unavailable, falling back to ${fallback}"
    if docker manifest inspect "$fallback" >/dev/null 2>&1; then
        export "$key=$fallback"
        success "Fallback ${key}=${fallback} is available"
        return 0
    fi

    error "Neither ${configured} nor fallback ${fallback} is available for ${key}"
    return 1
}

prepare_compose_overrides() {
    stage "Resolving deployment images"

    ensure_image_reference PYTHON_BASE_IMAGE "python:3.12-slim"
    ensure_image_reference NODE_BASE_IMAGE "node:24-alpine"
    ensure_image_reference MYSQL_IMAGE "mysql:8.4"
    ensure_image_reference REDIS_IMAGE "redis:7.4-alpine"
    ensure_image_reference ETCD_IMAGE "quay.io/coreos/etcd:v3.5.5"
    ensure_image_reference MINIO_IMAGE "minio/minio:RELEASE.2024-12-18T13-15-44Z"
    ensure_image_reference MILVUS_IMAGE "milvusdb/milvus:v2.5.4"
    ensure_image_reference NGINX_IMAGE "nginx:1.27-alpine"
}

wait_for_healthy() {
    local container="$1"
    local display_name="$2"
    local timeout="${3:-120}"
    local elapsed=0
    local interval=3

    info "${display_name} is starting..."

    while [ "$elapsed" -lt "$timeout" ]; do
        local status
        status="$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "not_found")"

        case "$status" in
            healthy)
                success "${display_name} is healthy"
                return 0
                ;;
            unhealthy)
                local logs
                logs="$(docker logs --tail 10 "$container" 2>&1 || true)"
                error "${display_name} failed to become healthy:"
                echo "$logs"
                return 1
                ;;
            not_found|starting)
                ;;
            *)
                ;;
        esac

        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    local logs
    logs="$(docker logs --tail 10 "$container" 2>&1 || true)"
    error "${display_name} timed out after ${timeout}s. Recent logs:"
    echo "$logs"
    return 1
}

check_prerequisites() {
    if ! command -v docker >/dev/null 2>&1; then
        error "docker command not found"
        exit 1
    fi

    if ! docker compose version >/dev/null 2>&1; then
        error "docker compose plugin not found"
        exit 1
    fi

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        warn ".env not found, copying from .env.example"
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        warn "fill required API keys in .env and rerun"
        exit 1
    fi

    prepare_compose_overrides
}

do_up() {
    check_prerequisites

    stage "Stage 1/4: infrastructure (MySQL, Redis, etcd, MinIO)"
    docker compose up -d interview_mysql interview_redis interview_etcd interview_minio

    wait_for_healthy interview_mysql "MySQL" 120
    wait_for_healthy interview_redis "Redis" 30
    wait_for_healthy interview_etcd "etcd" 30
    wait_for_healthy interview_minio "MinIO" 30

    stage "Stage 2/4: vector database (Milvus)"
    docker compose up -d interview_milvus
    warn "Milvus first startup can take a few minutes"
    wait_for_healthy interview_milvus "Milvus" 360

    stage "Stage 3/4: applications (Backend, Frontend)"
    docker compose up -d --build interview_backend interview_frontend

    wait_for_healthy interview_backend "Backend (FastAPI)" 120
    wait_for_healthy interview_frontend "Frontend (Vue3)" 60

    stage "Stage 4/4: gateway (Nginx)"
    docker compose up -d interview_nginx
    wait_for_healthy interview_nginx "Nginx" 30

    stage "Database initialization"

    info "Initializing database schema..."
    if docker exec interview_backend python /app/scripts/init_db.py; then
        success "Database schema initialized"
    else
        warn "Database initialization failed or already exists, skipping"
    fi

    info "Seeding demo data..."
    if docker exec interview_backend python /app/scripts/seed_demo.py; then
        success "Demo data imported"
    else
        warn "Demo data import failed or already exists, skipping"
    fi

    stage "Deployment complete"
    success "All services are deployed"
    docker compose ps
    info "Frontend: http://localhost"
    info "API docs: http://localhost/docs"
}

do_down() {
    info "Stopping all services..."
    docker compose down
    success "All services stopped"
}

do_status() {
    docker compose ps
}

do_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker compose logs -f "$service"
    else
        docker compose logs -f
    fi
}

do_restart() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        error "Specify a service to restart"
        exit 1
    fi
    info "Restarting ${service}..."
    docker compose restart "$service"
    success "${service} restarted"
}

do_verify() {
    stage "Connectivity verification"

    info "Checking Backend -> MySQL..."
    if docker exec interview_backend python -c "
from app.db.session import engine
with engine.connect() as conn:
    conn.execute(__import__('sqlalchemy').text('SELECT 1'))
print('MySQL connection successful')
"; then
        success "MySQL reachable"
    else
        error "MySQL check failed"
    fi

    info "Checking Backend -> Redis..."
    if docker exec interview_backend python -c "
import redis
r = redis.from_url('redis://interview_redis:6379/0')
r.ping()
print('Redis connection successful')
"; then
        success "Redis reachable"
    else
        error "Redis check failed"
    fi

    info "Checking Backend -> Milvus..."
    if docker exec interview_backend python -c "
from pymilvus import connections
connections.connect(uri='http://interview_milvus:19530')
print('Milvus connection successful')
connections.disconnect('default')
"; then
        success "Milvus reachable"
    else
        error "Milvus check failed"
    fi

    success "Connectivity verification complete"
}

COMMAND="${1:-up}"

case "$COMMAND" in
    up)
        do_up
        ;;
    down)
        do_down
        ;;
    status)
        do_status
        ;;
    logs)
        do_logs "${2:-}"
        ;;
    restart)
        do_restart "${2:-}"
        ;;
    verify)
        do_verify
        ;;
    *)
        echo "Usage: $0 {up|down|status|logs|restart|verify}"
        exit 1
        ;;
esac
