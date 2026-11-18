from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import TipoMovimentacao


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

    produto_id: int
    tipo: TipoMovimentacao
    quantidade: int  # ENTRADA/SAIDA: positiva. AJUSTE: com sinal (+ sobra, - perda).
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]

    @model_validator(mode="after")
    def _quantidade_coerente_com_tipo(self) -> Self:
        if self.quantidade == 0:
            raise ValueError("A quantidade não pode ser zero.")
        if self.tipo != TipoMovimentacao.AJUSTE and self.quantidade < 0:
            raise ValueError("Em ENTRADA e SAIDA a quantidade deve ser positiva; só AJUSTE aceita valor negativo.")
        return self


class MovimentacaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    tipo: TipoMovimentacao
    quantidade: int
    motivo: str
    data_hora: datetime
    pedido_id: int | None
