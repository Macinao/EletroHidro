import re
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.models import TipoCliente
from app.validadores import cnpj_valido, cpf_valido

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}  # fmt: skip

Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
Cidade = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Contato = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]


def _validar_uf(uf: str | None) -> str | None:
    if uf is None:
        return None
    uf = uf.strip().upper()
    if uf not in UFS:
        raise ValueError("UF inválida.")
    return uf


class ClienteCriar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "tipo": "PJ",
                    "documento": "11.222.333/0001-81",
                    "nome": "Construtora Alvorada Ltda",
                    "cidade": "Campinas",
                    "uf": "SP",
                    "contato": "compras@alvorada.example",
                }
            ]
        },
    )

    tipo: TipoCliente
    documento: str  # aceita com ou sem máscara; é gravado só com dígitos
    nome: Nome  # nome (PF) ou razão social (PJ)
    cidade: Cidade
    uf: str
    contato: Contato | None = None

    _uf = field_validator("uf")(_validar_uf)

    @field_validator("documento")
    @classmethod
    def _so_digitos(cls, valor: str) -> str:
        return re.sub(r"\D", "", valor)

    @model_validator(mode="after")
    def _documento_confere_com_tipo(self) -> Self:
        if self.tipo == TipoCliente.PF and not cpf_valido(self.documento):
            raise ValueError("CPF inválido.")
        if self.tipo == TipoCliente.PJ and not cnpj_valido(self.documento):
            raise ValueError("CNPJ inválido.")
        return self


class ClienteAtualizar(BaseModel):
    """PATCH: tipo e documento são imutáveis (identificam o cliente). Valores null são ignorados."""

    model_config = ConfigDict(extra="forbid")

    nome: Nome | None = None
    cidade: Cidade | None = None
    uf: str | None = None
    contato: Contato | None = None

    _uf = field_validator("uf")(_validar_uf)


class ClienteResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoCliente
    documento: str
    nome: str
    cidade: str
    uf: str
    contato: str | None
