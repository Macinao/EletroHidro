from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import StatusConta


class ContaReceberResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pedido_id: int
    valor: Decimal
    data_emissao: date
    data_vencimento: date
    data_pagamento: date | None
    # Lê a propriedade "situacao" do modelo (PENDENTE vencida aparece como VENCIDO).
    status: StatusConta = Field(validation_alias="situacao")


class PagamentoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"data_pagamento": "2025-03-10"}]})

    data_pagamento: date | None = Field(None, description="Padrão: hoje.")
