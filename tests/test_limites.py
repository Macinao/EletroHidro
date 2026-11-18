"""Regressões da verificação de conformidade: entradas extremas, mensagens em português, fuso e Swagger.

Cada teste daqui falhava no código anterior (500, mensagem em inglês, pedido "sumindo" do filtro etc.).
"""

import re
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app

INGLES = re.compile(r"\b(should|Input|required|Field|List|at least|Value error|valid|dictionary|Internal)\b")

_BASE = {"sku": "S1", "nome": "N", "categoria": "ELETRICO", "subcategoria": "X", "unidade": "UN", "preco_venda": "1.00"}
_MOV = {"produto_id": 1, "tipo": "ENTRADA", "motivo": "teste"}


@pytest.mark.parametrize(
    ("caminho", "corpo"),
    [
        ("/pedidos", {"cliente_id": 1, "itens": []}),  # lista vazia
        ("/pedidos", {"cliente_id": 1, "itens": "x"}),  # não é lista
        ("/pedidos", []),  # corpo não é objeto
        ("/pedidos", "texto"),
        ("/produtos", {**_BASE, "preco_venda": "99999999999.00"}),  # dígitos inteiros demais
        ("/produtos", {**_BASE, "preco_venda": None}),
        ("/produtos", {**_BASE, "estoque_minimo": 1.5}),
        ("/produtos", {**_BASE, "categoria": "MADEIRA"}),  # opções listadas sem o "or" do Pydantic
        ("/movimentacoes", {**_MOV, "quantidade": 1.5}),
        ("/movimentacoes", {**_MOV, "quantidade": None}),
        ("/movimentacoes", {**_MOV, "quantidade": True}),
        ("/movimentacoes", {**_MOV, "quantidade": "5"}),
    ],
)
def test_validacoes_respondem_422_sempre_em_portugues(client, caminho, corpo):
    r = client.post(caminho, json=corpo)
    assert r.status_code == 422, r.text
    erros = r.json()["erros"]
    assert erros and not any(INGLES.search(e["mensagem"]) or " or " in e["mensagem"] for e in erros), erros
    assert all(e["campo"] for e in erros)  # erro no corpo inteiro aparece como campo "corpo"


def test_quantidade_booleana_nao_vira_1_unidade(client, criar_produto):
    """Antes, `"quantidade": true` era aceito em silêncio como 1 unidade."""
    produto = criar_produto(estoque=10)
    r = client.post("/movimentacoes", json={**_MOV, "produto_id": produto["id"], "quantidade": True})
    assert r.status_code == 422 and r.json()["erros"][0]["mensagem"] == "deve ser um número inteiro"
    assert client.get(f"/produtos/{produto['id']}").json()["estoque_atual"] == 10


@pytest.mark.parametrize(
    ("metodo", "caminho", "corpo"),
    [
        ("POST", "/movimentacoes", {**_MOV, "quantidade": 10**12}),
        ("POST", "/pedidos", {"cliente_id": 1, "itens": [{"produto_id": 1, "quantidade": 10**12}]}),
        ("POST", "/produtos", {**_BASE, "estoque_minimo": 10**12}),
        ("PATCH", "/produtos/1", {"estoque_minimo": 10**12}),
        ("GET", "/produtos?pagina=100000000000000000000", None),
        ("GET", "/produtos/9223372036854775808", None),  # id acima do maior INTEGER: pega na rede de segurança
        ("POST", "/movimentacoes", {**_MOV, "produto_id": 2**40, "quantidade": 1}),
    ],
)
def test_valores_extremos_viram_422_e_nao_500(client, criar_produto, metodo, caminho, corpo):
    criar_produto()
    r = client.request(metodo, caminho, json=corpo)
    assert r.status_code == 422, r.text
    assert not INGLES.search(r.text)


@pytest.mark.parametrize("rota", ["/pedidos", "/movimentacoes"])
def test_data_fim_no_limite_do_calendario_nao_quebra(client, rota):
    assert client.get(rota, params={"data_inicio": "0001-01-01", "data_fim": "9999-12-31"}).status_code == 200


def test_pedido_com_total_acima_do_suportado_e_recusado_ja_na_criacao(client, criar_cliente, criar_produto):
    """O total (10 x 9.999.999.999,99) não caberia na conta a receber: antes, isso só estourava (500) ao faturar."""
    cliente = criar_cliente()
    caro = criar_produto(sku="CARO", preco_venda="9999999999.99", estoque=10)
    r = client.post(
        "/pedidos", json={"cliente_id": cliente["id"], "itens": [{"produto_id": caro["id"], "quantidade": 10}]}
    )
    assert r.status_code == 422 and "excede o máximo" in r.json()["detail"]
    assert client.get("/pedidos").json()["total"] == 0


def test_pedido_feito_a_noite_aparece_no_filtro_do_proprio_dia(client, sessao, criar_cliente, criar_produto):
    """Comparar timestamptz com `date` usava o fuso do banco (UTC): às 22h no Brasil o pedido caía no dia seguinte."""
    cliente = criar_cliente()
    produto = criar_produto(estoque=5)
    pedido = client.post(
        "/pedidos", json={"cliente_id": cliente["id"], "itens": [{"produto_id": produto["id"], "quantidade": 1}]}
    ).json()
    hoje = date.today()
    noite_local = datetime.combine(hoje, time(22, 30)).astimezone()  # 22:30 no fuso desta máquina
    sessao.execute(text("UPDATE pedidos SET data_pedido = :d WHERE id = :id"), {"d": noite_local, "id": pedido["id"]})
    sessao.execute(text("UPDATE movimentacoes_estoque SET data_hora = :d"), {"d": noite_local})
    sessao.commit()

    for rota in ["/pedidos", "/movimentacoes"]:
        no_dia = client.get(rota, params={"data_inicio": hoje.isoformat(), "data_fim": hoje.isoformat()}).json()
        assert no_dia["total"] >= 1, rota
        amanha = (hoje + timedelta(days=1)).isoformat()
        assert client.get(rota, params={"data_inicio": amanha}).json()["total"] == 0, rota


def test_erro_inesperado_responde_500_em_portugues(client, monkeypatch):
    from app.services import produtos as service

    def explodir(*_args):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(service, "obter", explodir)
    r = TestClient(app, raise_server_exceptions=False).get("/produtos/1")
    assert r.status_code == 500 and r.json() == {"detail": "Erro interno do servidor."}


def test_prompt_da_ia_usa_a_data_de_hoje_da_aplicacao(client, ia_fake):
    ia_fake.responder("SELECT 1 AS um")
    client.post("/ia/perguntar", json={"pergunta": "Quais contas estão vencidas?"})
    sistema = ia_fake.cliente.messages.create.call_args.kwargs["system"]
    assert f"DATE '{date.today().isoformat()}'" in sistema and "CURRENT_DATE" not in sistema.split("ESQUEMA")[
        0
    ].replace("e não CURRENT_DATE", "")


def test_swagger_documenta_o_formato_real_dos_erros_e_exemplos_de_resposta(client):
    doc = client.get("/openapi.json").json()
    esquemas = doc["components"]["schemas"]
    assert "HTTPValidationError" not in esquemas  # o formato padrão do FastAPI (loc/msg/type) não é o desta API
    resposta_422 = doc["paths"]["/produtos"]["post"]["responses"]["422"]
    assert resposta_422["content"]["application/json"]["schema"]["$ref"].endswith("/ErroValidacao")
    descricoes = [
        r["description"] for op in doc["paths"].values() for o in op.values() for r in o["responses"].values()
    ]
    assert "Successful Response" not in descricoes
    for modelo in ["ProdutoResposta", "ClienteResposta", "PedidoResposta", "MovimentacaoResposta",
                   "ContaReceberResposta", "ProdutoMaisVendido", "ClienteRanking", "RespostaIA"]:  # fmt: skip
        assert esquemas[modelo].get("examples"), modelo
