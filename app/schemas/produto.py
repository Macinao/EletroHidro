"""Schemas de produto (equivalentes aos DTOs de request/response no Spring).

O estoque_atual NÃO é aceito na criação/edição: ele só muda por movimentações,
assim todo saldo tem uma trilha de auditoria.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import CategoriaProduto, UnidadeProduto
from app.schemas.tipos import EstoqueMinimo

Preco = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, examples=["28.90"])]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ProdutoCriar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",  # campo desconhecido (ex.: estoque_atual) vira 422, não é ignorado em silêncio
        json_schema_extra={
            "examples": [
                {
                    "sku": "DJ-BIP-32A",
                    "nome": "Disjuntor Bipolar 32A Curva C",
                    "descricao": "Disjuntor termomagnético DIN, 32A, 220V",
                    "categoria": "ELETRICO",
                    "subcategoria": "Disjuntores",
                    "unidade": "UN",
                    "preco_venda": "28.90",
                    "estoque_minimo": 10,
                }
            ]
        },
    )

    sku: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    descricao: Annotated[str, StringConstraints(max_length=500)] | None = None
    categoria: CategoriaProduto
    subcategoria: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    unidade: UnidadeProduto
    preco_venda: Preco
    estoque_minimo: EstoqueMinimo = 0


class ProdutoAtualizar(BaseModel):
    """PATCH: só os campos enviados mudam. O SKU é imutável. Valores null são ignorados."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"preco_venda": "31.50"}]})

    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)] | None = None
    descricao: Annotated[str, StringConstraints(max_length=500)] | None = None
    categoria: CategoriaProduto | None = None
    subcategoria: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    unidade: UnidadeProduto | None = None
    preco_venda: Preco | None = None
    estoque_minimo: EstoqueMinimo | None = None
    ativo: bool | None = None


class ProdutoResposta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,  # permite ler direto do objeto ORM
        json_schema_extra={
            "examples": [
                {
                    "id": 7,
                    "sku": "DJ-MONO-20A",
                    "nome": "Disjuntor Monopolar 20A Curva C",
                    "descricao": None,
                    "categoria": "ELETRICO",
                    "subcategoria": "Disjuntores",
                    "unidade": "UN",
                    "preco_venda": "14.90",
                    "estoque_atual": 13,
                    "estoque_minimo": 40,
                    "ativo": True,
                }
            ]
        },
    )

    id: int
    sku: str
    nome: str
    descricao: str | None
    categoria: CategoriaProduto
    subcategoria: str
    unidade: UnidadeProduto
    preco_venda: Decimal
    estoque_atual: int
    estoque_minimo: int
    ativo: bool
