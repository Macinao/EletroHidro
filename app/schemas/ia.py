from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class PerguntaIA(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"pergunta": "Quais disjuntores estão abaixo do estoque mínimo?"}]},
    )

    pergunta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class RespostaIA(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pergunta": "Quais disjuntores estão abaixo do estoque mínimo?",
                    "sql": "SELECT sku, nome, estoque_atual, estoque_minimo FROM produtos WHERE ativo AND "
                    "subcategoria ILIKE 'Disjuntores' AND estoque_atual < estoque_minimo ORDER BY sku LIMIT 101",
                    "colunas": ["sku", "nome", "estoque_atual", "estoque_minimo"],
                    "linhas": [
                        ["DJ-MONO-20A", "Disjuntor Monopolar 20A Curva C", 13, 40],
                        ["DJ-MONO-32A", "Disjuntor Monopolar 32A Curva C", 13, 40],
                        ["DJ-TRI-63A", "Disjuntor Tripolar 63A Curva C", 0, 10],
                    ],
                    "total_linhas": 3,
                    "truncado": False,
                }
            ]
        }
    )

    pergunta: str
    sql: str = Field(description="Consulta que foi realmente executada (validada e com LIMIT aplicado).")
    colunas: list[str]
    linhas: list[list[Any]] = Field(description="Cada linha segue a ordem de `colunas`.")
    total_linhas: int
    truncado: bool = Field(description="True se havia mais linhas do que o máximo permitido.")
