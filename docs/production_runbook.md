# News Radar production runbook

## Required production settings

Keep `.env.prod` only on the server. At minimum, verify:

```dotenv
APP_ENV=production
DEBUG=false
TRUST_PROXY_HEADERS=true
FRONTEND_URL=https://news.safonovpavel.space
GOOGLE_REDIRECT_URI=https://news.safonovpavel.space/api/v1/auth/google/callback
VITE_API_URL=https://news.safonovpavel.space/api
```

Generate `SECRET_KEY` with a cryptographically secure generator. Do not rotate
it casually: rotation invalidates existing JWT and session cookies.

## Deployment

`scripts/deploy.sh` performs the production sequence:

1. Snapshot current application images with a `rollback` tag.
2. Fetch `main` and fast-forward to the exact commit SHA that passed CI.
3. Create and verify a PostgreSQL archive.
4. Build the backend, frontend, and bot images.
5. Apply Alembic migrations using the new backend image.
6. Replace services and wait for the dependency-aware readiness endpoint.
7. Remove build cache and dangling images older than seven days.
8. Restore the previous application images if the new deployment does not
   become ready.

Run:

```bash
bash scripts/deploy.sh
```

The migration policy must remain backward-compatible with the immediately
previous application version. Automatic image rollback cannot reverse a
destructive database migration.

## Backups

Create an on-server archive:

```bash
bash scripts/backup_postgres.sh
```

The script writes a custom-format `pg_dump`, verifies that `pg_restore` can
read it, and keeps seven days by default. An archive on the same VPS is not a
disaster-recovery backup. Copy verified archives to storage outside U1Host.

Test a backup without touching production data:

```bash
docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -lc 'createdb -U "$POSTGRES_USER" newsradar_restore_test'

docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -lc 'pg_restore -U "$POSTGRES_USER" -d newsradar_restore_test --clean --if-exists' \
  < backups/REPLACE_WITH_BACKUP.dump

docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -lc 'psql -U "$POSTGRES_USER" -d newsradar_restore_test -c \
  "SELECT COUNT(*) FROM news_items;"'

docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -lc 'dropdb -U "$POSTGRES_USER" newsradar_restore_test'
```

## Health and diagnostics

Liveness only checks the API process:

```text
GET /api/health
```

Readiness checks PostgreSQL and Redis:

```text
GET /api/health/ready
```

Useful diagnostics:

```bash
docker-compose --env-file .env.prod -f docker-compose.prod.yml ps
docker-compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 backend
docker-compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=200 worker
docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T worker \
  celery -A app.workers.celery_app inspect active
docker-compose --env-file .env.prod -f docker-compose.prod.yml exec -T worker \
  celery -A app.workers.celery_app inspect reserved
```

Docker JSON logs are rotated at 10 MB with three files per container.

## Cloudflare and origin TLS

Cloudflare's visitor certificate does not by itself encrypt or authenticate
the Cloudflare-to-origin connection.

Production target:

1. Install a Cloudflare Origin CA or public certificate on Nginx.
2. Change the Cloudflare SSL/TLS mode to **Full (strict)**.
3. Test HTTPS to the origin.
4. Restrict ports 80/443 to Cloudflare IP ranges or configure Authenticated
   Origin Pulls.
5. Only after verification, stop serving the application directly over
   unauthenticated origin HTTP.

References:

- <https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/>
- <https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/>

Do not enable strict origin validation before the certificate and Nginx HTTPS
configuration are tested, or production traffic will fail.

## Metrics

The FastAPI `/api/metrics` endpoint is blocked at the public Nginx layer.
Prometheus should scrape `http://backend:8000/api/metrics` over the internal
Docker network. Flower remains bound to `127.0.0.1:5555`; access it through an
SSH tunnel:

```bash
ssh -L 5555:127.0.0.1:5555 newsradar@SERVER_IP
```

Then open `http://127.0.0.1:5555` locally.
