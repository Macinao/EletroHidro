"""Linhas dos relatórios. Os exemplos (Swagger) são resultados reais sobre os dados do seed."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import CategoriaProduto


def _exemplo(dados: dict) -> ConfigDict:
    return ConfigDict(json_schema_extra={"examples": [dados]})


class ProdutoMaisVendido(BaseModel):
    model_config = _exemplo(
        {
            "produto_id": 6,
            "sku": "CAB-PP-3X2.5",
            "nome": "Cabo PP 3x2,5mm² 750V (por metro)",
            "categoria": "ELETRICO",
            "quantidade_vendida": 99,
            "faturamento": "970.20",
        }
    )

    produto_id: int
    sku: str
    nome: str
    categoria: CategoriaProduto
    quantidade_vendida: int
    faturamento: Decimal


class FaturamentoMensal(BaseModel):
    model_config = _exemplo({"mes": "2026-10", "categoria": "ELETRICO", "faturamento": "2113.50", "qtd_pedidos": 3})

    mes: str  # AAAA-MM
    categoria: CategoriaProduto
    faturamento: Decimal
    qtd_pedidos: int


class ClienteRanking(BaseModel):
    model_config = _exemplo(
        {
            "posicao": 1,
            "cliente_id": 2,
            "nome": "Elétrica Brasil Instalações Ltda",
            "cidade": "São Paulo",
            "uf": "SP",
            "qtd_pedidos": 6,
            "faturamento": "3854.70",
        }
    )

    posicao: int
    cliente_id: int
    nome: str
    cidade: str
    uf: str
    qtd_pedidos: int
    faturamento: Decimal


class ProdutoEstoqueBaixo(BaseModel):
    model_config = _exemplo(
        {
            "produto_id": 7,
            "sku": "DJ-MONO-20A",
            "nome": "Disjuntor Monopolar 20A Curva C",
            "categoria": "ELETRICO",
            "subcategoria": "Disjuntores",
            "estoque_atual": 13,
            "estoque_minimo": 40,
            "falta": 27,
        }
    )

    produto_id: int
    sku: str
    nome: str
    categoria: CategoriaProduto
    subcategoria: str
    estoque_atual: int
    estoque_minimo: int
    falta: int


class ClienteInadimplente(BaseModel):
    model_config = _exemplo(
        {
            "cliente_id": 4,
            "nome": "Condomínio Residencial Parque Verde",
            "uf": "PR",
            "qtd_contas": 2,
            "total_vencido": "3423.30",
            "vencimento_mais_antigo": "2026-08-13",
            "dias_atraso_maximo": 97,
        }
    )

    cliente_id: int
    nome: str
    uf: str
    qtd_contas: int
    total_vencido: Decimal
    vencimento_mais_antigo: date
    dias_atraso_maximo: int
