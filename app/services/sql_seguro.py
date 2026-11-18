"""Validação do SQL gerado pela IA: só passa UM SELECT inofensivo, e com LIMIT.

O texto gerado pelo modelo é NÃO CONFIÁVEL (pode errar ou ser manipulado pela pergunta do
usuário: "prompt injection"). Por isso este módulo PARSEIA o SQL (sqlglot, dialeto PostgreSQL)
em vez de procurar palavras com regex, que é facilmente burlável (`DeLeTe`, comentários, etc.).

Falha FECHADA: o que o parser não entende (Command) ou que não está na lista permitida é recusado.
O que é executado é o SQL REGENERADO a partir da árvore validada, não o texto original.

Esta é a 1ª de várias camadas. As outras ficam no banco e valem mesmo se esta falhar:
usuário PostgreSQL só com SELECT, transação READ ONLY e statement_timeout.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.errors import ConsultaInvalida

# Qualquer um destes nós, em QUALQUER lugar da árvore (inclusive dentro de CTE), reprova a consulta.
_NOS_PROIBIDOS = tuple(
    getattr(exp, nome)
    for nome in (
        "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterTable", "Command", "Copy",
        "TruncateTable", "Set", "Use", "Grant", "Revoke", "Transaction", "Commit", "Rollback", "Analyze",
    )
    if hasattr(exp, nome)
)  # fmt: skip

# Funções que leem arquivos, abrem conexões, mudam configuração ou executam SQL em texto.
_PREFIXOS_FUNCAO_PROIBIDOS = ("pg_", "lo_", "dblink")
_FUNCOES_PROIBIDAS = {"set_config", "query_to_xml", "query_to_xml_and_xmlschema", "table_to_xml", "cursor_to_xml"}


def _rejeitar(motivo: str) -> ConsultaInvalida:
    return ConsultaInvalida(f"Consulta rejeitada pela validação de segurança: {motivo}")


def _nome_funcao(funcao: exp.Func) -> str:
    return (funcao.name if isinstance(funcao, exp.Anonymous) else funcao.sql_name()).lower()


def validar_e_limitar(sql: str, tabelas_permitidas: set[str], max_linhas: int) -> str:
    """Retorna o SQL seguro (regenerado e com LIMIT) ou lança ConsultaInvalida."""
    try:
        comandos = [c for c in sqlglot.parse(sql, dialect="postgres") if c is not None]
    except SqlglotError as erro:
        raise _rejeitar("o SQL não é válido para PostgreSQL.") from erro

    if len(comandos) != 1:
        raise _rejeitar("é permitida exatamente uma consulta.")
    raiz = comandos[0]
    if not isinstance(raiz, (exp.Select, exp.SetOperation)):  # SetOperation = UNION/INTERSECT/EXCEPT
        raise _rejeitar("somente consultas SELECT são permitidas.")

    permitidas = {t.lower() for t in tabelas_permitidas}
    ctes = {cte.alias_or_name.lower() for cte in raiz.find_all(exp.CTE)}

    for no in raiz.walk():
        if isinstance(no, _NOS_PROIBIDOS):
            raise _rejeitar(f"comando não permitido ({type(no).__name__.upper()}).")
        if isinstance(no, exp.Select) and (no.args.get("into") or no.args.get("locks")):
            raise _rejeitar("SELECT ... INTO e FOR UPDATE/SHARE não são permitidos.")
        if isinstance(no, exp.Func):
            nome = _nome_funcao(no)
            if nome in _FUNCOES_PROIBIDAS or nome.startswith(_PREFIXOS_FUNCAO_PROIBIDOS):
                raise _rejeitar(f"função não permitida ({nome}).")
        if isinstance(no, exp.Table):
            if not isinstance(no.this, exp.Identifier):  # ex.: FROM generate_series(...)
                raise _rejeitar("funções na cláusula FROM não são permitidas.")
            if no.args.get("catalog") or (no.db and no.db.lower() != "public"):
                raise _rejeitar(f"schema não permitido ({no.db or no.catalog}).")  # pg_catalog, information_schema...
            nome = no.name.lower()
            if not no.db and nome in ctes:
                continue  # referência a uma CTE definida na própria consulta
            if nome not in permitidas:
                raise _rejeitar(f"tabela não permitida ({no.name}).")

    _aplicar_limite(raiz, max_linhas)
    return raiz.sql(dialect="postgres")


def _aplicar_limite(raiz: exp.Expression, max_linhas: int) -> None:
    """Garante LIMIT <= max_linhas + 1. O "+1" permite ao chamador saber se houve truncamento."""
    teto = max_linhas + 1
    atual = raiz.args.get("limit")
    valor = None
    if isinstance(atual, exp.Limit) and isinstance(atual.expression, exp.Literal) and atual.expression.is_int:
        valor = int(atual.expression.this)
    if valor is None or valor > teto:  # sem LIMIT, LIMIT ALL, FETCH FIRST ou valor acima do teto
        raiz.set("limit", exp.Limit(expression=exp.Literal.number(teto)))
