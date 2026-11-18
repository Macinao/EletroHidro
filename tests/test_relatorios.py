"""Relatórios sobre um dataset pequeno e controlado: os valores esperados foram calculados à mão.

Dataset (preços: DJ=30, CB=100, TB=20)               faturamento  emissão     vencimento  situação
  P1  cliente A (SP)  DJ x10 + CB x1                     400      2025-01-15  2025-01-31  FATURADO, pendente
  P2  cliente B (MG)  DJ x5  + TB x10                    350      2025-02-10  2025-02-28  FATURADO, pendente
  P3  cliente A (SP)  TB x20                             400      2025-02-20  2099-01-01  ENTREGUE
  P6  cliente B (MG)  TB x1                               20      2025-03-01  2025-03-31  FATURADO e PAGO
  P4  cliente A       CB x5                                -      CONFIRMADO (não conta como venda)
  P5  cliente B       DJ x100                              -      CANCELADO (não conta como venda)
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text


@pytest.fixture
def dados(client, sessao, criar_cliente, criar_produto):
    a = criar_cliente(nome="Alfa Construções", cidade="Campinas", uf="SP")
    b = criar_cliente(documento="11.444.777/0001-61", nome="Beta Instalações", cidade="Belo Horizonte", uf="MG")
    dj = criar_produto(sku="DJ", nome="Disjuntor", subcategoria="Disjuntores", preco_venda="30.00", estoque=1000)
    cb = criar_produto(sku="CB", nome="Cabo", subcategoria="Cabos", preco_venda="100.00", estoque=1000)
    tb = criar_produto(
        sku="TB",
        nome="Tubo",
        categoria="HIDRAULICO",
        subcategoria="Tubos",
        unidade="M",
        preco_venda="20.00",
        estoque=1000,
    )

    def pedido(cliente, itens, ate, emissao=None, vencimento=None, pago=False):
        corpo = {"cliente_id": cliente["id"], "itens": [{"produto_id": p["id"], "quantidade": q} for p, q in itens]}
        pid = client.post("/pedidos", json=corpo).json()["id"]
        etapas = {
            "CANCELADO": ["cancelar"],
            "CONFIRMADO": ["confirmar"],
            "FATURADO": ["confirmar", "faturar"],
            "ENTREGUE": ["confirmar", "faturar", "entregar"],
        }[ate]
        for etapa in etapas:
            assert client.post(f"/pedidos/{pid}/{etapa}").status_code == 200
        if pago:
            conta_id = client.get("/contas-receber", params={"pedido_id": pid}).json()["itens"][0]["id"]
            assert client.post(f"/contas-receber/{conta_id}/pagamento").status_code == 200
        if emissao:  # recua as datas para o passado (a API sempre fatura "hoje")
            sessao.execute(
                text("UPDATE contas_receber SET data_emissao = :e, data_vencimento = :v WHERE pedido_id = :id"),
                {"e": emissao, "v": vencimento, "id": pid},
            )
            sessao.commit()
        return pid

    pedido(a, [(dj, 10), (cb, 1)], "FATURADO", "2025-01-15", "2025-01-31")
    pedido(b, [(dj, 5), (tb, 10)], "FATURADO", "2025-02-10", "2025-02-28")
    pedido(a, [(tb, 20)], "ENTREGUE", "2025-02-20", "2099-01-01")
    pedido(b, [(tb, 1)], "FATURADO", "2025-03-01", "2025-03-31", pago=True)
    pedido(a, [(cb, 5)], "CONFIRMADO")
    pedido(b, [(dj, 100)], "CANCELADO")
    return {"a": a, "b": b}


def _resumo(linhas: list[dict], *campos: str) -> list[tuple]:
    return [
        tuple(Decimal(linha[c]) if c in ("faturamento", "total_vencido") else linha[c] for c in campos)
        for linha in linhas
    ]


# ---------- 1. produtos mais vendidos ----------


def test_produtos_mais_vendidos(client, dados):
    r = client.get("/relatorios/produtos-mais-vendidos")
    assert r.status_code == 200
    assert _resumo(r.json(), "sku", "quantidade_vendida", "faturamento") == [
        ("TB", 31, Decimal("620.00")),
        ("DJ", 15, Decimal("450.00")),
        ("CB", 1, Decimal("100.00")),
    ]


def test_produtos_mais_vendidos_com_filtros(client, dados):
    fevereiro = client.get(
        "/relatorios/produtos-mais-vendidos", params={"data_inicio": "2025-02-01", "data_fim": "2025-02-28"}
    )
    assert _resumo(fevereiro.json(), "sku", "quantidade_vendida") == [("TB", 30), ("DJ", 5)]

    eletricos = client.get("/relatorios/produtos-mais-vendidos", params={"categoria": "ELETRICO"})
    assert [p["sku"] for p in eletricos.json()] == ["DJ", "CB"]

    assert [p["sku"] for p in client.get("/relatorios/produtos-mais-vendidos", params={"limite": 1}).json()] == ["TB"]


# ---------- 2. faturamento por categoria e mês ----------


def test_faturamento_por_categoria_e_mes(client, dados):
    r = client.get("/relatorios/faturamento-por-categoria-mes")
    assert _resumo(r.json(), "mes", "categoria", "faturamento", "qtd_pedidos") == [
        ("2025-01", "ELETRICO", Decimal("400.00"), 1),
        ("2025-02", "ELETRICO", Decimal("150.00"), 1),
        ("2025-02", "HIDRAULICO", Decimal("600.00"), 2),
        ("2025-03", "HIDRAULICO", Decimal("20.00"), 1),
    ]
    sem_janeiro = client.get("/relatorios/faturamento-por-categoria-mes", params={"data_inicio": "2025-02-01"}).json()
    assert [linha["mes"] for linha in sem_janeiro] == ["2025-02", "2025-02", "2025-03"]


# ---------- 3. ranking de clientes ----------


def test_ranking_de_clientes(client, dados):
    r = client.get("/relatorios/ranking-clientes")
    assert _resumo(r.json(), "posicao", "nome", "qtd_pedidos", "faturamento") == [
        (1, "Alfa Construções", 2, Decimal("800.00")),
        (2, "Beta Instalações", 2, Decimal("370.00")),
    ]


def test_ranking_filtrado_por_uf_e_periodo(client, dados):
    mg = client.get("/relatorios/ranking-clientes", params={"uf": "mg"}).json()
    assert _resumo(mg, "posicao", "nome", "uf") == [(1, "Beta Instalações", "MG")]

    marco = client.get("/relatorios/ranking-clientes", params={"data_inicio": "2025-03-01"}).json()
    assert _resumo(marco, "nome", "faturamento") == [("Beta Instalações", Decimal("20.00"))]


# ---------- 4. estoque abaixo do mínimo ----------


def test_estoque_abaixo_do_minimo(client, criar_produto):
    criar_produto(sku="BAIXO", nome="Disjuntor Baixo", subcategoria="Disjuntores", estoque=3)  # falta 7
    criar_produto(sku="ZERADO", nome="Tomada Zerada", subcategoria="Tomadas")  # falta 10
    criar_produto(sku="NOLIMITE", nome="Cabo no limite", subcategoria="Cabos", estoque=10)  # = mínimo: não entra
    criar_produto(sku="OK", nome="Cabo ok", subcategoria="Cabos", estoque=50)
    criar_produto(sku="HID", nome="Tubo baixo", categoria="HIDRAULICO", subcategoria="Tubos", estoque=9)  # falta 1
    inativo = criar_produto(sku="INATIVO", nome="Inativo", subcategoria="Cabos", estoque=1)
    client.delete(f"/produtos/{inativo['id']}")

    todos = client.get("/relatorios/estoque-abaixo-do-minimo").json()
    assert [(p["sku"], p["falta"]) for p in todos] == [("ZERADO", 10), ("BAIXO", 7), ("HID", 1)]

    disjuntores = client.get("/relatorios/estoque-abaixo-do-minimo", params={"subcategoria": "disjuntores"}).json()
    assert [p["sku"] for p in disjuntores] == ["BAIXO"]
    hidraulicos = client.get("/relatorios/estoque-abaixo-do-minimo", params={"categoria": "HIDRAULICO"}).json()
    assert [p["sku"] for p in hidraulicos] == ["HID"]


# ---------- 5. contas vencidas por cliente ----------


def test_contas_vencidas_por_cliente(client, dados):
    r = client.get("/relatorios/contas-vencidas")
    linhas = r.json()
    # P3 vence em 2099 e P6 já está paga: ficam de fora.
    assert _resumo(linhas, "nome", "qtd_contas", "total_vencido", "vencimento_mais_antigo") == [
        ("Alfa Construções", 1, Decimal("400.00"), "2025-01-31"),
        ("Beta Instalações", 1, Decimal("350.00"), "2025-02-28"),
    ]
    assert linhas[0]["dias_atraso_maximo"] == (date.today() - date(2025, 1, 31)).days


def test_contas_vencidas_com_data_de_referencia(client, dados):
    # Em 15/02/2025 só a conta de janeiro estava vencida (a de fevereiro vencia dia 28).
    linhas = client.get("/relatorios/contas-vencidas", params={"data_referencia": "2025-02-15"}).json()
    assert _resumo(linhas, "nome", "dias_atraso_maximo") == [("Alfa Construções", 15)]


# ---------- validações comuns ----------


def test_parametros_invalidos(client):
    assert (
        client.get(
            "/relatorios/produtos-mais-vendidos", params={"data_inicio": "2025-02-01", "data_fim": "2025-01-01"}
        ).status_code
        == 400
    )
    assert client.get("/relatorios/ranking-clientes", params={"limite": 0}).status_code == 422
    assert client.get("/relatorios/ranking-clientes", params={"uf": "SAO"}).status_code == 422


def test_relatorios_vazios_retornam_lista_vazia(client):
    for rota in [
        "produtos-mais-vendidos",
        "faturamento-por-categoria-mes",
        "ranking-clientes",
        "estoque-abaixo-do-minimo",
        "contas-vencidas",
    ]:
        r = client.get(f"/relatorios/{rota}")
        assert r.status_code == 200 and r.json() == [], rota
