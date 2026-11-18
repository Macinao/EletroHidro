"""Relatórios (somente leitura). Sem camada de service: não há regra de negócio nem transação,
o router chama direto as consultas SQL do repositório."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CategoriaProduto
from app.periodo import Periodo, periodo
from app.repositories import relatorios as repo
from app.schemas.relatorios import (
    ClienteInadimplente,
    ClienteRanking,
    FaturamentoMensal,
    ProdutoEstoqueBaixo,
    ProdutoMaisVendido,
)

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])

_NOTA_VENDAS = (
    "Considera apenas pedidos **FATURADO** e **ENTREGUE**; o período filtra pela data de faturamento "
    "(emissão da conta a receber)."
)
_400 = {400: {"description": "data_inicio posterior a data_fim."}}


@router.get(
    "/produtos-mais-vendidos",
    response_model=list[ProdutoMaisVendido],
    summary="Produtos mais vendidos no período",
    description=f"Quantidade e faturamento por produto, do mais vendido para o menos. {_NOTA_VENDAS}",
    responses=_400,
)
def produtos_mais_vendidos(
    per: Periodo = Depends(periodo),
    categoria: CategoriaProduto | None = None,
    limite: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return repo.produtos_mais_vendidos(db, per.data_inicio, per.data_fim, categoria and categoria.value, limite)


@router.get(
    "/faturamento-por-categoria-mes",
    response_model=list[FaturamentoMensal],
    summary="Faturamento por categoria e por mês",
    description=f"Uma linha por mês (AAAA-MM) e categoria. {_NOTA_VENDAS}",
    responses=_400,
)
def faturamento_por_categoria_mes(per: Periodo = Depends(periodo), db: Session = Depends(get_db)):
    return repo.faturamento_por_categoria_e_mes(db, per.data_inicio, per.data_fim)


@router.get(
    "/ranking-clientes",
    response_model=list[ClienteRanking],
    summary="Ranking de clientes por faturamento",
    description=f"Pode ser filtrado por UF. Empates dividem a mesma posição. {_NOTA_VENDAS}",
    responses=_400,
)
def ranking_clientes(
    per: Periodo = Depends(periodo),
    uf: str | None = Query(None, min_length=2, max_length=2, examples=["SP"]),
    limite: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return repo.ranking_clientes(db, per.data_inicio, per.data_fim, uf and uf.upper(), limite)


@router.get(
    "/estoque-abaixo-do-minimo",
    response_model=list[ProdutoEstoqueBaixo],
    summary="Produtos ativos com estoque abaixo do mínimo",
    description="Estoque atual **menor que** o mínimo; `falta` é quanto repor para chegar ao mínimo. Maior falta primeiro.",
)
def estoque_abaixo_do_minimo(
    categoria: CategoriaProduto | None = None,
    subcategoria: str | None = Query(None, description="Ex.: Disjuntores (sem diferenciar maiúsculas)."),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return repo.estoque_abaixo_do_minimo(db, categoria and categoria.value, subcategoria, limite)


@router.get(
    "/contas-vencidas",
    response_model=list[ClienteInadimplente],
    summary="Contas a receber vencidas, com total por cliente",
    description="Contas PENDENTES com vencimento anterior à data de referência, agrupadas por cliente (maior dívida primeiro).",
)
def contas_vencidas(
    data_referencia: date | None = Query(None, description="Padrão: hoje."),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return repo.contas_vencidas_por_cliente(db, data_referencia or date.today(), limite)
