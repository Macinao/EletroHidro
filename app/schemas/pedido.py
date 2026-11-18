from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import StatusPedido
from app.schemas.tipos import Id, Quantidade


class ItemCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: Id
    quantidade: Quantidade
    # O preço NÃO é informado: o servidor usa o preço atual do produto e o congela no item.


class PedidoCriar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"cliente_id": 1, "itens": [{"produto_id": 1, "quantidade": 10}, {"produto_id": 5, "quantidade": 3}]}
            ]
        },
    )

    cliente_id: Id
    itens: list[ItemCriar] = Field(min_length=1)

    @field_validator("itens")
    @classmethod
    def _sem_produto_repetido(cls, itens: list[ItemCriar]) -> list[ItemCriar]:
        ids = [item.produto_id for item in itens]
        if len(ids) != len(set(ids)):
            raise ValueError("Produto repetido nos itens; some as quantidades em um único item.")
        return itens


class ItemResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    produto_id: int
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal


class PedidoResposta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 31,
                    "cliente_id": 1,
                    "status": "ABERTO",
                    "data_pedido": "2026-11-18T17:18:22.122729Z",
                    "itens": [
                        {"produto_id": 44, "quantidade": 10, "preco_unitario": "28.90", "subtotal": "289.00"},
                        {"produto_id": 13, "quantidade": 20, "preco_unitario": "9.50", "subtotal": "190.00"},
                    ],
                    "total": "479.00",
                }
            ]
        },
    )

    id: int
    cliente_id: int
    status: StatusPedido
    data_pedido: datetime
    itens: list[ItemResposta]
    total: Decimal
