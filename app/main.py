from fastapi import FastAPI

from app.errors import registrar_handlers
from app.routers import clientes, contas_receber, ia, movimentacoes, pedidos, produtos, relatorios

app = FastAPI(
    title="EletroHidro Distribuidora — API",
    description="API REST de estoque, vendas e financeiro de uma distribuidora "
    "fictícia de materiais elétricos e hidráulicos (projeto de portfólio).",
    version="0.5.0",
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
