#!/bin/sh
set -eu
# Init only on a fresh volume. Values remain in the private server environment.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
CREATE ROLE studio_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE studio TO studio_app;
GRANT USAGE, CREATE ON SCHEMA public TO studio_app;
SQL
