"""Routers HTTP."""

from typing import Any

# Tipo do argumento `responses=` do FastAPI (documentação das respostas de erro no Swagger).
Respostas = dict[int | str, dict[str, Any]]
