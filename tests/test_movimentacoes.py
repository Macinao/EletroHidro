import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import sessionmaker

from app.errors import Conflito
from app.models import TipoMovimentacao
from app.services import estoque


def _mov(produto_id: int, tipo: str, quantidade: int, motivo: str = "Teste automatizado") -> dict:
    return {"produto_id": produto_id, "tipo": tipo, "quantidade": quantidade, "motivo": motivo}


def _estoque(client, produto_id: int) -> int:
    return client.get(f"/produtos/{produto_id}").json()["estoque_atual"]


def test_entrada_e_saida_atualizam_o_estoque(client, criar_produto):
    p = criar_produto()
    assert client.post("/movimentacoes", json=_mov(p["id"], "ENTRADA", 50)).status_code == 201
    assert client.post("/movimentacoes", json=_mov(p["id"], "SAIDA", 20)).status_code == 201
    assert _estoque(client, p["id"]) == 30


def test_saida_maior_que_o_saldo_retorna_409_e_nao_altera_nada(client, criar_produto):
    p = criar_produto(estoque=5)
    r = client.post("/movimentacoes", json=_mov(p["id"], "SAIDA", 6))
    assert r.status_code == 409
    assert "Estoque insuficiente" in r.json()["detail"]
    assert _estoque(client, p["id"]) == 5
    assert client.get("/movimentacoes", params={"produto_id": p["id"]}).json()["total"] == 1  # só a carga inicial


def test_ajuste_negativo_reduz_e_nao_pode_negativar(client, criar_produto):
    p = criar_produto(estoque=10)
    assert client.post("/movimentacoes", json=_mov(p["id"], "AJUSTE", -3, "Perda no inventário")).status_code == 201
    assert _estoque(client, p["id"]) == 7
    assert client.post("/movimentacoes", json=_mov(p["id"], "AJUSTE", -8)).status_code == 409


def test_ajuste_positivo_aumenta(client, criar_produto):
    p = criar_produto(estoque=10)
    client.post("/movimentacoes", json=_mov(p["id"], "AJUSTE", 4, "Sobra no inventário"))
    assert _estoque(client, p["id"]) == 14


def test_quantidade_zero_ou_negativa_em_entrada_saida_retorna_422(client, criar_produto):
    p = criar_produto(estoque=10)
    for tipo, qtd in [("ENTRADA", 0), ("ENTRADA", -1), ("SAIDA", -1), ("AJUSTE", 0)]:
        assert client.post("/movimentacoes", json=_mov(p["id"], tipo, qtd)).status_code == 422, (tipo, qtd)
    assert _estoque(client, p["id"]) == 10


def test_motivo_e_obrigatorio(client, criar_produto):
    p = criar_produto()
    r = client.post("/movimentacoes", json={"produto_id": p["id"], "tipo": "ENTRADA", "quantidade": 1})
    assert r.status_code == 422
    assert r.json()["erros"] == [{"campo": "motivo", "mensagem": "campo obrigatório"}]


def test_produto_inexistente_retorna_404(client):
    assert client.post("/movimentacoes", json=_mov(999, "ENTRADA", 1)).status_code == 404


def test_listagem_filtra_por_tipo_e_datas(client, criar_produto):
    p = criar_produto(estoque=10)
    client.post("/movimentacoes", json=_mov(p["id"], "SAIDA", 2))
    saidas = client.get("/movimentacoes", params={"tipo": "SAIDA", "produto_id": p["id"]}).json()
    assert saidas["total"] == 1 and saidas["itens"][0]["quantidade"] == 2

    assert client.get("/movimentacoes", params={"data_inicio": "2999-01-01"}).json()["total"] == 0
    r = client.get("/movimentacoes", params={"data_inicio": "2025-02-01", "data_fim": "2025-01-01"})
    assert r.status_code == 400


def test_saidas_concorrentes_nao_vendem_o_mesmo_estoque(engine, client, criar_produto):
    """Protege contra o "lost update" (por isso o FOR UPDATE em aplicar_movimentacao).

    A (saldo 10, saída de 6) ainda não commitou quando B (também saída de 6) começa.
    - SEM lock: B lê o saldo antigo 10, espera A commitar e grava 4 por cima: vendeu 12 de 10
      e nenhum CHECK reclama, porque 4 >= 0.
    - COM lock: B só lê depois do commit de A, enxerga 4 e é recusada com Conflito.
    """
    p = criar_produto(estoque=10)
    nova_sessao = sessionmaker(bind=engine, expire_on_commit=False)

    def saida_b() -> str:
        with nova_sessao() as b:
            try:
                estoque.aplicar_movimentacao(b, p["id"], TipoMovimentacao.SAIDA, 6, "B")
                b.commit()
                return "ok"
            except Conflito:
                return "conflito"

    with nova_sessao() as a, ThreadPoolExecutor(max_workers=1) as pool:
        estoque.aplicar_movimentacao(a, p["id"], TipoMovimentacao.SAIDA, 6, "A")  # sem commit: segura o lock
        futuro = pool.submit(saida_b)
        time.sleep(0.5)  # dá tempo de B chegar ao ponto em que fica esperando
        a.commit()
        assert futuro.result(timeout=10) == "conflito"

    assert _estoque(client, p["id"]) == 4
