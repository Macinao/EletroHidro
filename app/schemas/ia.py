from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class PerguntaIA(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"pergunta": "Quais disjuntores estão abaixo do estoque mínimo?"}]},
    )

    pergunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class RespostaIA(BaseModel):
    pergunta: str
    sql: str = Field(description="Consulta que foi realmente executada (validada e com LIMIT aplicado).")
    colunas: list[str]
    linhas: list[list[Any]] = Field(description="Cada linha segue a ordem de `colunas`.")
    total_linhas: int
    truncado: bool = Field(description="True se havia mais linhas do que o máximo permitido.")
