#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
target_commit="${1:-origin/main}"

test -f .env.prod
grep -Eq '^APP_ENV=production$' .env.prod
grep -Eq '^DEBUG=false$' .env.prod
grep -Eq '^TRUST_PROXY_HEADERS=true$' .env.prod

compose=(
  docker-compose
  --env-file .env.prod
  -f docker-compose.prod.yml
)

images=(
  news-radar-backend
  news-radar-embedding-service
  news-radar-frontend
  news-radar-bot
)

rollback_available=false
for image in "${images[@]}"; do
  if docker image inspect "$image:latest" > /dev/null 2>&1; then
    docker tag "$image:latest" "$image:rollback"
    rollback_available=true
  fi
done

rollback() {
  if [[ "$rollback_available" != true ]]; then
    echo "No previous application images are available for rollback" >&2
    return 1
  fi

  echo "Restoring previous application images" >&2
  for image in "${images[@]}"; do
    if docker image inspect "$image:rollback" > /dev/null 2>&1; then
      docker tag "$image:rollback" "$image:latest"
    fi
  done
  "${compose[@]}" up -d --no-build --force-recreate
}

if [[ -n "$1" && "$1" != "origin/main" ]]; then
    git fetch --all
    git checkout "$1"
    echo "Switched to commit: $(git rev-parse HEAD)"
fi

"$project_dir/scripts/backup_postgres.sh"

# Build first, migrate with the new backend image, then replace services.
"${compose[@]}" build
"${compose[@]}" run --rm backend alembic upgrade head
if ! "${compose[@]}" up -d --remove-orphans; then
  "${compose[@]}" ps >&2
  "${compose[@]}" logs --tail=100 embedding-service >&2
  rollback
  exit 1
fi

for attempt in $(seq 1 20); do
  if curl --fail --silent --show-error \
    http://127.0.0.1/api/health/ready > /dev/null; then
    echo "Deployment is ready"
    docker builder prune -a -f --filter "until=168h"
    docker image prune -f --filter "until=168h"
    exit 0
  fi
  echo "Waiting for readiness ($attempt/20)"
  sleep 3
done

echo "Deployment failed readiness check" >&2
"${compose[@]}" ps >&2
"${compose[@]}" logs --tail=100 embedding-service >&2
"${compose[@]}" logs --tail=100 backend >&2
rollback
exit 1
