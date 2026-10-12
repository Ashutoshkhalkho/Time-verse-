# TIMEWISE — Production Deployment Runbook & Operational Architecture

**Document Version:** 1.0  
**Date:** October 2026  
**Target Environment:** Production Linux (Docker / Kubernetes / Systemd)  
**Stack:** FastAPI (Python 3.12+), Next.js 14, PostgreSQL 16+, Redis 7+

---

## 1. System Architecture Overview

The TIMEWISE production architecture consists of:
1. **Frontend Tier:** Next.js 14 application serving responsive React pages with static generation and server-side API proxying.
2. **Backend API Tier:** FastAPI application running on Uvicorn worker processes managed by Gunicorn master.
3. **Database Tier:** PostgreSQL 16 with ACID transactions and connection pooling (PgBouncer recommended).
4. **Cache & Deduplication Tier:** Redis 7 for token revocation ledger and the 5-minute alert deduplication window.
5. **Reverse Proxy & Edge Ingress:** Nginx / Cloudflare terminating TLS 1.3, enforcing HTTP Strict Transport Security (HSTS), and handling rate limits.

---

## 2. Environment Variables & Secret Management

All sensitive secrets must be injected at runtime via environment variables or secret managers (e.g., HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager). Never commit `.env` files containing production secrets.

### Required Production Environment Variables
| Variable Name | Description | Example / Recommendation |
|:---|:---|:---|
| `ENVIRONMENT` | Environment identifier | `production` |
| `DEBUG` | FastAPI debug flag (MUST be false in prod) | `false` |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://app_user:StrongPass@pg.internal:5432/timewise_prod?ssl=require` |
| `DATABASE_SYNC_URL` | Sync PostgreSQL connection string (for Alembic migrations) | `postgresql://app_user:StrongPass@pg.internal:5432/timewise_prod?ssl=require` |
| `SECRET_KEY` | 256-bit cryptographic signing key for JWTs | Output of `openssl rand -hex 32` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifespan | `7` |
| `REDIS_URL` | Redis connection URL | `redis://:RedisPass@redis.internal:6379/0` |
| `ALLOWED_HOSTS` | Trusted Host header domains | `timewise.university.edu,api.timewise.university.edu` |
| `CORS_ORIGINS` | Allowed frontend origin URLs | `https://timewise.university.edu` |
| `NEXT_PUBLIC_API_URL` | Public-facing API base URL for frontend | `https://api.timewise.university.edu/api/v1` |

---

## 3. Database Migrations & Management

Database migrations are executed using Alembic to guarantee schema synchronization without manual DDL operations.

### Migration Runbook Commands
```bash
# 1. Inspect current migration revision status
alembic current

# 2. Check for pending unapplied migrations
alembic heads

# 3. Apply all pending database migrations in production
alembic upgrade head

# 4. Safe single-revision rollback (if needed during deployment rollback)
alembic downgrade -1
```

---

## 4. Database Backup & Disaster Recovery Runbook

To safeguard institutional academic schedules, implement automated daily physical backups and continuous WAL archiving.

### 4.1 Automated Logical Backup
```bash
# Export compressed PostgreSQL database dump
pg_dump -h pg.internal -U app_user -d timewise_prod -F c -b -v -f /backups/timewise_backup_$(date +%Y%m%d_%H%M%S).dump

# Encrypt backup file at rest using GPG
gpg --symmetric --cipher-algo AES256 /backups/timewise_backup_*.dump
```

### 4.2 Database Restoration Drill
```bash
# 1. Terminate active application connections
psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'timewise_prod' AND pid <> pg_backend_pid();"

# 2. Drop and recreate clean production database
psql -U postgres -c "DROP DATABASE timewise_prod;"
psql -U postgres -c "CREATE DATABASE timewise_prod WITH OWNER app_user ENCODING 'UTF8';"

# 3. Restore database from backup archive
pg_restore -U app_user -d timewise_prod -v /backups/timewise_backup_TARGET.dump

# 4. Run database health validation query
psql -U app_user -d timewise_prod -c "SELECT count(*) FROM users; SELECT count(*) FROM timetables;"
```

---

## 5. HTTPS, Reverse Proxy & TLS Configuration

Deploy an Nginx reverse proxy with TLS 1.3 termination and secure HTTP headers.

### Example Nginx Configuration (`/etc/nginx/sites-available/timewise.conf`):
```nginx
server {
    listen 80;
    server_name timewise.university.edu api.timewise.university.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name timewise.university.edu;

    ssl_certificate /etc/letsencrypt/live/timewise.university.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/timewise.university.edu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl http2;
    server_name api.timewise.university.edu;

    ssl_certificate /etc/letsencrypt/live/timewise.university.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/timewise.university.edu/privkey.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 6. Operational Health Probes & Monitoring

TIMEWISE provides lightweight operational endpoints for container orchestration (Kubernetes / ECS / Docker):

| Endpoint | Probe Type | Description | Expected Status |
|:---|:---|:---|:---:|
| `GET /healthz` | **Liveness Probe** | Verifies FastAPI event loop is responsive | `200 OK` (`{"status": "ok"}`) |
| `GET /healthz/ready` | **Readiness Probe** | Verifies live PostgreSQL database connection | `200 OK` (`{"status": "ok", "database_connected": true}`) |
| `GET /api/v1/health` | **API Health Alias** | Standard API gateway health check | `200 OK` (`{"status": "ok"}`) |

### Logging & Correlation IDs
* Each incoming HTTP request receives a unique UUID `X-Request-ID` header.
* Response latency is recorded in microseconds in the `X-Process-Time` header.
* Operational logs are structured JSON for consumption by Datadog, CloudWatch, or ELK stack.
