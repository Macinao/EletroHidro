"""Filtro de período (data_inicio/data_fim, ambos inclusivos) reutilizado pelas listagens e relatórios."""

from datetime import date
from typing import NamedTuple

from fastapi import Query

from app.errors import RequisicaoInvalida


class Periodo(NamedTuple):
    data_inicio: date | None
    data_fim: date | None


def periodo(
    data_inicio: date | None = Query(None, description="Início do período, inclusive (AAAA-MM-DD)."),
    data_fim: date | None = Query(None, description="Fim do período, inclusive (AAAA-MM-DD)."),
) -> Periodo:
    if data_inicio and data_fim and data_inicio > data_fim:
        raise RequisicaoInvalida("data_inicio não pode ser posterior a data_fim.")
    return Periodo(data_inicio, data_fim)
