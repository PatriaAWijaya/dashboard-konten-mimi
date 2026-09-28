#!/usr/bin/env bash
# Entrypoint: (opsional) siapkan role DB non-superuser, migrasi, grant — lalu jalankan CMD.
#
# Mode docker-compose (variabel SUPERUSER_*/APP_DB_* di-set): buat role least-privilege
# + grant, persis seperti sebelumnya.
# Mode hosting (Render/Supabase, dsb — variabel SUPERUSER_* KOSONG): lewati pembuatan
# role, langsung jalankan migrasi dengan DATABASE_URL lalu start aplikasi.
set -euo pipefail

echo "[entrypoint] DATABASE_URL: $([ -n "${DATABASE_URL:-}" ] && echo TERISI || echo KOSONG)"

python3 -c 'import os; print("[entrypoint] python DATABASE_URL:", "ADA" if os.environ.get("DATABASE_URL") else "TIDAK ADA")'
export DATABASE_URL SUPERUSER_DATABASE_URL MIGRATION_DATABASE_URL FERNET_KEY JWT_SECRET_KEY ENV FRONTEND_URL API_BASE_URL CORS_ORIGINS BANK_NAME BANK_ACCOUNT_NUMBER BANK_ACCOUNT_NAME MAX_BRANDS_PER_ORG MAX_ACCOUNTS_PER_PLATFORM APP_DB_USER APP_DB_PASSWORD PORT 2>/dev/null || true

if [ -n "${SUPERUSER_DATABASE_URL:-}" ] && [ -n "${APP_DB_USER:-}" ] && [ -n "${APP_DB_PASSWORD:-}" ]; then
    export MIGRATION_DATABASE_URL="${MIGRATION_DATABASE_URL:-$SUPERUSER_DATABASE_URL}"

    echo "[entrypoint] Menyiapkan role database '${APP_DB_USER}'..."
    DBNAME="$(psql "$SUPERUSER_DATABASE_URL" -tAc "SELECT current_database()")"
    SUPERUSER_NAME="$(psql "$SUPERUSER_DATABASE_URL" -tAc "SELECT current_user")"

    psql "$SUPERUSER_DATABASE_URL" -v ON_ERROR_STOP=1 <<EOSQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_DB_USER}') THEN
    CREATE ROLE "${APP_DB_USER}" WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
    RAISE NOTICE 'Role ${APP_DB_USER} dibuat.';
  ELSE
    RAISE NOTICE 'Role ${APP_DB_USER} sudah ada, dilewati.';
  END IF;
END
\$\$;
GRANT CONNECT ON DATABASE "${DBNAME}" TO "${APP_DB_USER}";
GRANT USAGE ON SCHEMA public TO "${APP_DB_USER}";
EOSQL

    echo "[entrypoint] Menjalankan migrasi database..."
    alembic upgrade head

    echo "[entrypoint] Memberikan grant ke role '${APP_DB_USER}'..."
    psql "$SUPERUSER_DATABASE_URL" -v ON_ERROR_STOP=1 <<EOSQL
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "${APP_DB_USER}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "${APP_DB_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${SUPERUSER_NAME}" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "${APP_DB_USER}";
ALTER DEFAULT PRIVILEGES FOR ROLE "${SUPERUSER_NAME}" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO "${APP_DB_USER}";
EOSQL
else
    echo "[entrypoint] Mode hosting: SUPERUSER_DATABASE_URL tidak di-set, lewati pembuatan role."
    echo "[entrypoint] Menjalankan migrasi database..."
    alembic upgrade head
fi

if [ $# -eq 0 ]; then
  # Render menyediakan $PORT; hormati bila ada.
  set -- uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi

echo "[entrypoint] Menjalankan: $*"
exec "$@"
