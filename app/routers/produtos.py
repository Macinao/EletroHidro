from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CategoriaProduto
from app.paginacao import Pagina, Paginacao, paginacao
from app.repositories import produtos as repo
from app.schemas.produto import ProdutoAtualizar, ProdutoCriar, ProdutoResposta
from app.services import produtos as service

router = APIRouter(prefix="/produtos", tags=["Produtos"])

_404 = {404: {"description": "Produto não encontrado."}}


@router.post(
    "",
    response_model=ProdutoResposta,
    status_code=201,
    summary="Cadastra um produto",
    description="O produto nasce com estoque 0; use `POST /movimentacoes` para dar entrada.",
    responses={409: {"description": "Já existe um produto com esse SKU."}},
)
def criar(dados: ProdutoCriar, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.get("", response_model=Pagina[ProdutoResposta], summary="Lista produtos (paginado, com filtros)")
def listar(
    categoria: CategoriaProduto | None = None,
    subcategoria: str | None = Query(None, description="Ex.: Disjuntores (sem diferenciar maiúsculas)."),
    ativo: bool | None = None,
    busca: str | None = Query(None, description="Trecho do nome ou do SKU."),
    p: Paginacao = Depends(paginacao),
    db: Session = Depends(get_db),
):
    return repo.listar(db, p, categoria=categoria, subcategoria=subcategoria, ativo=ativo, busca=busca)


@router.get("/{produto_id}", response_model=ProdutoResposta, summary="Busca um produto", responses=_404)
def obter(produto_id: int, db: Session = Depends(get_db)):
    return service.obter(db, produto_id)


@router.patch("/{produto_id}", response_model=ProdutoResposta, summary="Atualiza campos do produto", responses=_404)
def atualizar(produto_id: int, dados: ProdutoAtualizar, db: Session = Depends(get_db)):
    return service.atualizar(db, produto_id, dados)


@router.delete(
    "/{produto_id}",
    status_code=204,
    summary="Inativa o produto",
    description="Exclusão lógica (`ativo=false`): o histórico de vendas e movimentações é preservado.",
    responses=_404,
)
def inativar(produto_id: int, db: Session = Depends(get_db)) -> None:
    service.inativar(db, produto_id)
