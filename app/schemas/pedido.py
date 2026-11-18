from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import StatusPedido


class ItemCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: int
    quantidade: int = Field(gt=0)
    # O preço NÃO é informado: o servidor usa o preço atual do produto e o congela no item.


class PedidoCriar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"cliente_id": 1, "itens": [{"produto_id": 1, "quantidade": 10}, {"produto_id": 5, "quantidade": 3}]}]
        },
    )

    cliente_id: int
    itens: list[ItemCriar] = Field(min_length=1)

    @model_validator(mode="after")
    def _sem_produto_repetido(self) -> Self:
        ids = [item.produto_id for item in self.itens]
        if len(ids) != len(set(ids)):
            raise ValueError("Produto repetido nos itens; some as quantidades em um único item.")
        return self


class ItemResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    produto_id: int
    quantidade: int
    preco_unitario: Decimal
    subtotal: Decimal


class PedidoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    status: StatusPedido
    data_pedido: datetime
    itens: list[ItemResposta]
    total: Decimal
