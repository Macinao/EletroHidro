#!/bin/sh
# Cria o usuário PostgreSQL SOMENTE LEITURA usado pelo endpoint /ia/perguntar.
# - Roda sozinho na 1ª criação do volume do banco (pasta /docker-entrypoint-initdb.d).
# - É idempotente: pode ser executado de novo num banco já existente:
#     docker compose exec db sh /docker-entrypoint-initdb.d/01-somente-leitura.sh
set -e

psql -v ON_ERROR_STOP=1 \
     -v ro_senha="$READONLY_DB_PASSWORD" -v dono="$POSTGRES_USER" -v banco="$POSTGRES_DB" \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
-- Cria o papel só se ainda não existir (\gexec executa o texto que o SELECT devolveu).
SELECT format('CREATE ROLE eletrohidro_ro LOGIN PASSWORD %L', :'ro_senha')
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'eletrohidro_ro')
\gexec

ALTER ROLE eletrohidro_ro WITH PASSWORD :'ro_senha' CONNECTION LIMIT 10;
-- Valem para toda sessão desse usuário, mesmo que a aplicação esqueça de configurar:
ALTER ROLE eletrohidro_ro SET default_transaction_read_only = on;
ALTER ROLE eletrohidro_ro SET statement_timeout = '10s';

-- Só leitura: nenhum INSERT/UPDATE/DELETE/DDL é concedido.
GRANT CONNECT ON DATABASE :"banco" TO eletrohidro_ro;
GRANT USAGE ON SCHEMA public TO eletrohidro_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO eletrohidro_ro;
-- Tabelas criadas depois (pelas migrações do Alembic) já nascem legíveis:
ALTER DEFAULT PRIVILEGES FOR ROLE :"dono" IN SCHEMA public GRANT SELECT ON TABLES TO eletrohidro_ro;
EOSQL
