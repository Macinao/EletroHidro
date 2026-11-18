from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationInfo, field_validator

from app.models import TipoMovimentacao
from app.schemas.tipos import Id, QuantidadeComSinal


class MovimentacaoCriar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"produto_id": 1, "tipo": "ENTRADA", "quantidade": 50, "motivo": "Compra do fornecedor NF 1234"},
                {"produto_id": 1, "tipo": "AJUSTE", "quantidade": -2, "motivo": "Perda apurada no inventário"},
            ]
        },
    )

    produto_id: Id
    tipo: TipoMovimentacao
    quantidade: QuantidadeComSinal  # ENTRADA/SAIDA: positiva. AJUSTE: com sinal (+ sobra, - perda).
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]

    @field_validator("quantidade")
    @classmethod
    def _quantidade_coerente_com_tipo(cls, quantidade: int, info: ValidationInfo) -> int:
        if quantidade == 0:
            raise ValueError("A quantidade não pode ser zero.")
        tipo = info.data.get("tipo")
        if tipo is not None and tipo != TipoMovimentacao.AJUSTE and quantidade < 0:
            raise ValueError("Em ENTRADA e SAIDA a quantidade deve ser positiva; só AJUSTE aceita valor negativo.")
        return quantidade


class MovimentacaoResposta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 120,
                    "produto_id": 44,
                    "tipo": "ENTRADA",
                    "quantidade": 50,
                    "motivo": "Compra do fornecedor - NF 1234",
                    "data_hora": "2026-11-18T17:18:21.293641Z",
                    "pedido_id": None,
                }
            ]
        },
    )

    id: int
    produto_id: int
    tipo: TipoMovimentacao
    quantidade: int
    motivo: str
    data_hora: datetime
    pedido_id: int | None
