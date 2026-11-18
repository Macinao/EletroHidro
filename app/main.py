from fastapi import FastAPI

app = FastAPI(
    title="EletroHidro Distribuidora — API",
    description="API REST de estoque, vendas e financeiro de uma distribuidora "
    "fictícia de materiais elétricos e hidráulicos (projeto de portfólio).",
    version="0.1.0",
)


@app.get("/saude", tags=["Infra"], summary="Verifica se a API está no ar")
def saude() -> dict[str, str]:
    return {"status": "ok"}
