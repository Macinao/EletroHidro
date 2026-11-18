from datetime import date

import pytest
from sqlalchemy import func, select, text

from app import seed
from app.models import Cliente, ContaReceber, Pedido, Produto, StatusPedido


@pytest.fixture
def populado(sessao):
    return seed.popular(sessao)


def test_quantidades_do_seed(populado, sessao):
    assert populado["produtos"] >= 40 and populado["clientes"] == 10 and populado["pedidos"] == 30
    assert sessao.scalar(select(func.count()).select_from(Produto).where(Produto.ativo.is_(False))) == 1


def test_documentos_dos_clientes_sao_validos(populado, sessao):
    # (o seed passa pelo ClienteCriar, que valida os dígitos; aqui só conferimos o armazenado)
    docs = sessao.scalars(select(Cliente.documento)).all()
    assert len(set(docs)) == 10 and {len(d) for d in docs} == {11, 14}


def test_pedidos_espalhados_em_varios_meses_e_status(populado, sessao):
    meses = sessao.scalars(select(func.to_char(Pedido.data_pedido, "YYYY-MM")).distinct()).all()
    assert len(meses) >= 6
    status = set(sessao.scalars(select(Pedido.status)))
    assert status == set(StatusPedido)  # todos os 5 status aparecem


def test_estoque_confere_com_a_soma_das_movimentacoes(populado, sessao):
    """Invariante central: o saldo de cada produto é EXATAMENTE o resultado do seu histórico."""
    divergentes = sessao.execute(
        text(
            """
            SELECT p.sku, p.estoque_atual,
                   COALESCE(SUM(CASE m.tipo WHEN 'SAIDA' THEN -m.quantidade ELSE m.quantidade END), 0) AS historico
              FROM produtos p LEFT JOIN movimentacoes_estoque m ON m.produto_id = p.id
             GROUP BY p.id HAVING p.estoque_atual <> COALESCE(SUM(CASE m.tipo WHEN 'SAIDA' THEN -m.quantidade ELSE m.quantidade END), 0)
            """
        )
    ).all()
    assert divergentes == []
    assert sessao.scalar(select(func.min(Produto.estoque_atual))) >= 0


def test_contas_a_receber_coerentes(populado, sessao):
    contas = sessao.scalars(select(ContaReceber)).all()
    faturados = sessao.scalar(
        select(func.count()).select_from(Pedido).where(Pedido.status.in_(["FATURADO", "ENTREGUE"]))
    )
    assert len(contas) == faturados  # uma conta por pedido faturado/entregue
    assert all(c.data_emissao <= date.today() and c.data_vencimento >= c.data_emissao for c in contas)
    assert all(c.data_pagamento is None or c.data_pagamento >= c.data_emissao for c in contas)
    assert any(c.status == "PAGO" for c in contas) and any(c.situacao == "VENCIDO" for c in contas)


def test_relatorios_ficam_interessantes_com_o_seed(populado, client):
    assert len(client.get("/relatorios/produtos-mais-vendidos").json()) == 10
    meses = {linha["mes"] for linha in client.get("/relatorios/faturamento-por-categoria-mes").json()}
    assert len(meses) >= 5
    ranking = client.get("/relatorios/ranking-clientes", params={"uf": "SP"}).json()
    assert ranking and ranking[0]["posicao"] == 1
    baixo = client.get("/relatorios/estoque-abaixo-do-minimo").json()
    assert len(baixo) == 7
    assert [
        p["sku"]
        for p in client.get("/relatorios/estoque-abaixo-do-minimo", params={"subcategoria": "disjuntores"}).json()
    ]
    vencidas = client.get("/relatorios/contas-vencidas").json()
    assert len(vencidas) >= 2 and all(v["total_vencido"] and v["dias_atraso_maximo"] > 0 for v in vencidas)


def test_seed_e_deterministico_e_nao_roda_duas_vezes(sessao):
    primeiro = seed.popular(sessao, hoje=date(2026, 6, 15))
    total1 = sessao.scalar(select(func.sum(ContaReceber.valor)))
    with pytest.raises(RuntimeError, match="já tem dados"):
        seed.popular(sessao)

    seed.limpar(sessao)
    segundo = seed.popular(sessao, hoje=date(2026, 6, 15))
    assert primeiro == segundo and sessao.scalar(select(func.sum(ContaReceber.valor))) == total1
