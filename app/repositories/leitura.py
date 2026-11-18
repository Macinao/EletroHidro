"""Execução de SQL arbitrário (já validado) com o usuário SOMENTE LEITURA do PostgreSQL.

Camadas de proteção NO BANCO, independentes do validador:
 1. O usuário (eletrohidro_ro) só tem GRANT SELECT: INSERT/UPDATE/DELETE/DDL dão "permission denied".
 2. A transação é aberta como READ ONLY.
 3. statement_timeout aborta consultas lentas (ex.: produto cartesiano).
"""

from functools import lru_cache
from typing import Any

import psycopg.errors as pg
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.errors import ConsultaInvalida, ServicoIndisponivel


@lru_cache
def engine_somente_leitura(url: str) -> Engine:
    # Pool pequeno: o uso da IA é esporádico e não deve competir com a API principal.
    return create_engine(url, pool_size=2, max_overflow=2, pool_pre_ping=True)


def executar(engine: Engine, sql: str, timeout_segundos: int) -> tuple[list[str], list[list[Any]]]:
    try:
        with engine.connect() as conexao:
            conexao.exec_driver_sql("SET TRANSACTION READ ONLY")
            # set_config(..., true) vale só para esta transação (equivale a SET LOCAL, mas aceita parâmetro).
            conexao.execute(
                text("SELECT set_config('statement_timeout', :ms, true)"), {"ms": str(timeout_segundos * 1000)}
            )
            # exec_driver_sql: o SQL vai como está (sem o parser de :parametros do text()).
            # O psycopg trata "%" como início de placeholder; como não há parâmetros, escapamos
            # cada "%" (senão todo LIKE '%texto%' gerado pela IA quebraria).
            resultado = conexao.exec_driver_sql(sql.replace("%", "%%"))
            return list(resultado.keys()), [list(linha) for linha in resultado.fetchall()]
    except DBAPIError as erro:
        original = erro.orig
        if isinstance(original, pg.QueryCanceled):
            raise ConsultaInvalida(
                f"A consulta excedeu o tempo limite de {timeout_segundos}s e foi cancelada."
            ) from erro
        if isinstance(original, pg.OperationalError):  # conexão/autenticação do usuário somente leitura
            raise ServicoIndisponivel("Não foi possível conectar ao banco com o usuário somente leitura.") from erro
        detalhe = getattr(getattr(original, "diag", None), "message_primary", None) or "erro na execução"
        raise ConsultaInvalida(f"A consulta gerada falhou na execução: {detalhe}.") from erro
