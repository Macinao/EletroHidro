from fastapi import FastAPI

from app.errors import registrar_handlers
from app.routers import clientes, movimentacoes, produtos

app = FastAPI(
    title="EletroHidro Distribuidora — API",
    description="API REST de estoque, vendas e financeiro de uma distribuidora "
    "fictícia de materiais elétricos e hidráulicos (projeto de portfólio).",
    version="0.2.0",
)
registrar_handlers(app)
app.include_router(produtos.router)
app.include_router(clientes.router)
app.include_router(movimentacoes.router)


@app.get("/saude", tags=["Infra"], summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    return {"status": "ok"}
