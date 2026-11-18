"""Filtro de período (data_inicio/data_fim, ambos inclusivos) reutilizado pelas listagens e relatórios."""

from datetime import date, datetime, time, tzinfo
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


def _fuso_da_aplicacao() -> tzinfo | None:
    # Deslocamento atual do fuso do processo: -03:00 numa máquina no Brasil, UTC no container Docker.
    # (Deslocamento fixo: o Brasil não tem horário de verão desde 2019.)
    return datetime.now().astimezone().tzinfo


def inicio_do_dia(dia: date) -> datetime:
    """00:00 do dia no fuso da aplicação, como instante absoluto (para comparar com colunas timestamptz).

    Comparar timestamptz com um `date` puro faz o PostgreSQL usar o fuso da SESSÃO do banco (UTC),
    e não o da aplicação: um pedido feito às 22h no Brasil cairia no dia seguinte do filtro.
    """
    return datetime.combine(dia, time.min, tzinfo=_fuso_da_aplicacao())


def fim_do_dia(dia: date) -> datetime:
    """23:59:59.999999 do dia, para usar com `<=` (somar 1 dia estouraria em 9999-12-31)."""
    return datetime.combine(dia, time.max, tzinfo=_fuso_da_aplicacao())
