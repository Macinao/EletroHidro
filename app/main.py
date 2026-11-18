from fastapi import FastAPI

from app.errors import registrar_handlers
from app.routers import clientes, contas_receber, ia, movimentacoes, pedidos, produtos, relatorios

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
    {"name": "Produtos", "description": "Cadastro de produtos. O estoque **não** é editado aqui: só muda por movimentações."},
    {"name": "Clientes", "description": "Clientes PF (CPF) e PJ (CNPJ), com validação dos dígitos verificadores."},
    {"name": "Movimentações de estoque", "description": "ENTRADA, SAÍDA e AJUSTE. O estoque nunca fica negativo."},
    {"name": "Pedidos", "description": "Pedidos de venda e seu ciclo de status, com baixa e estorno de estoque."},
    {"name": "Financeiro", "description": "Contas a receber geradas no faturamento e registro de pagamento."},
    {"name": "Relatórios", "description": "Consultas de gestão escritas em SQL puro (joins, agregações, filtros)."},
    {"name": "IA", "description": "Perguntas em português respondidas via Claude, com SQL validado e executado somente para leitura."},
    {"name": "Infra", "description": "Verificação de saúde."},
]

app = FastAPI(
    title="EletroHidro Distribuidora — API",
    description=DESCRICAO,
    version="1.0.0",
    openapi_tags=TAGS,
)
registrar_handlers(app)
app.include_router(produtos.router)
app.include_router(clientes.router)
app.include_router(movimentacoes.router)
app.include_router(pedidos.router)
app.include_router(contas_receber.router)
app.include_router(relatorios.router)
app.include_router(ia.router)


@app.get("/saude", tags=["Infra"], summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    return {"status": "ok"}
