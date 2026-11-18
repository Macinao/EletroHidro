from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models import CategoriaProduto


class ProdutoMaisVendido(BaseModel):
    produto_id: int
    sku: str
    nome: str
    categoria: CategoriaProduto
    quantidade_vendida: int
    faturamento: Decimal


class FaturamentoMensal(BaseModel):
    mes: str  # AAAA-MM
    categoria: CategoriaProduto
    faturamento: Decimal
    qtd_pedidos: int


class ClienteRanking(BaseModel):
    posicao: int
    cliente_id: int
    nome: str
    cidade: str
    uf: str
    qtd_pedidos: int
    faturamento: Decimal


class ProdutoEstoqueBaixo(BaseModel):
    produto_id: int
    sku: str
    nome: str
    categoria: CategoriaProduto
    subcategoria: str
    estoque_atual: int
    estoque_minimo: int
    falta: int


class ClienteInadimplente(BaseModel):
    cliente_id: int
    nome: str
    uf: str
    qtd_contas: int
    total_vencido: Decimal
    vencimento_mais_antigo: date
    dias_atraso_maximo: int
