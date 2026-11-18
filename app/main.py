import logging
from typing import Any

from fastapi import FastAPI

from app.errors import Erro, ErroValidacao, registrar_handlers
from app.routers import Respostas, clientes, contas_receber, ia, movimentacoes, pedidos, produtos, relatorios

# O uvicorn só configura os loggers dele: sem isto, os logger.info() da aplicação (ex.: a trilha de
# auditoria das consultas da IA) seriam descartados, pois o nível padrão do Python é WARNING.
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("app").setLevel(logging.INFO)

DESCRICAO = """
API REST de estoque, vendas e financeiro da **EletroHidro Distribuidora** (empresa fictícia de materiais
elétricos e hidráulicos). Projeto de portfólio.

### Fluxo principal
1. **Produtos** e **Clientes** são cadastrados; o estoque entra por **Movimentações** (ENTRADA).
2. Um **Pedido** nasce `ABERTO` → `confirmar` (baixa o estoque) → `faturar` (gera a conta a receber)
   → `entregar`. Pode ser `cancelar`ado antes de faturar (o estoque é estornado).
3. O **Financeiro** registra o pagamento das contas a receber.
4. Os **Relatórios** respondem perguntas de gestão em SQL puro; a **IA** responde perguntas em português.

### Convenções
- Listagens são paginadas (`pagina`, `tamanho`) e filtráveis.
- Erros: `400` parâmetro inválido · `404` não encontrado · `409` conflito com o estado atual
  (estoque insuficiente, duplicidade, transição de status inválida) · `422` dados inválidos
  (a resposta traz `erros` com `campo` e `mensagem`).
- Valores monetários são strings decimais (`"28.90"`) para não perder precisão.
- Esta API não tem autenticação (escopo do projeto).
"""

TAGS = [
    {
        "name": "Produtos",
        "description": "Cadastro de produtos. O estoque **não** é editado aqui: só muda por movimentações.",
    },
    {"name": "Clientes", "description": "Clientes PF (CPF) e PJ (CNPJ), com validação dos dígitos verificadores."},
    {"name": "Movimentações de estoque", "description": "ENTRADA, SAÍDA e AJUSTE. O estoque nunca fica negativo."},
    {"name": "Pedidos", "description": "Pedidos de venda e seu ciclo de status, com baixa e estorno de estoque."},
    {"name": "Financeiro", "description": "Contas a receber geradas no faturamento e registro de pagamento."},
    {"name": "Relatórios", "description": "Consultas de gestão escritas em SQL puro (joins, agregações, filtros)."},
    {
        "name": "IA",
        "description": "Perguntas em português respondidas via Claude, com SQL validado e executado "
        "somente para leitura.",
    },
    {"name": "Infra", "description": "Verificação de saúde."},
]

# Documenta no Swagger o formato REAL dos erros. Sem isto, o FastAPI descreve o 422 com o formato
# padrão dele (loc/msg/type), que não é o que esta API devolve.
RESPOSTAS_DE_ERRO: Respostas = {
    422: {"model": ErroValidacao, "description": "Dados inválidos: lista de erros por campo."},
    "default": {"model": Erro, "description": "Demais erros: corpo com o campo `detail`."},
}

app = FastAPI(
    title="EletroHidro Distribuidora — API",
    description=DESCRICAO,
    version="1.0.0",
    openapi_tags=TAGS,
)
registrar_handlers(app)
for modulo in (produtos, clientes, movimentacoes, pedidos, contas_receber, relatorios, ia):
    app.include_router(modulo.router, responses=RESPOSTAS_DE_ERRO)


@app.get("/saude", tags=["Infra"], summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    return {"status": "ok"}


_gerar_openapi = app.openapi


def _openapi_em_portugues() -> dict[str, Any]:
    """Gera o documento OpenAPI uma vez e traduz o rótulo padrão do FastAPI ("Successful Response")."""
    if app.openapi_schema is None:
        for operacoes in _gerar_openapi()["paths"].values():
            for operacao in operacoes.values():
                for resposta in operacao.get("responses", {}).values():
                    if resposta.get("description") == "Successful Response":
                        resposta["description"] = "Sucesso"
    assert app.openapi_schema is not None  # preenchido (e reaproveitado) pelo próprio FastAPI
    return app.openapi_schema


app.openapi = _openapi_em_portugues  # type: ignore[method-assign]
