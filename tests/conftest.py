"""Infra dos testes: banco PostgreSQL REAL e separado (nome do banco + "_test").

Por que não SQLite/H2? As regras dependem de recursos do Postgres (CHECK, FOR UPDATE,
SQL dos relatórios). Testar em outro banco esconderia bugs reais.
O banco de desenvolvimento nunca é tocado: o nome de teste é sempre derivado com "_test".
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg.sql as psql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (registra as tabelas no metadata)
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.routers.ia import get_cliente_ia, get_engine_leitura


@pytest.fixture(scope="session")
def engine():
    url = make_url(get_settings().database_url)
    nome_teste = f"{url.database}_test"

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        existe = conexao.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": nome_teste})
        if not existe:
            conexao.execute(text(f'CREATE DATABASE "{nome_teste}"'))
    admin.dispose()

    engine = create_engine(url.set(database=nome_teste))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessao(engine):
    """Sessão para o teste montar/consultar dados direto no banco. Limpa tudo antes de cada teste."""
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conexao:
        conexao.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    with sessionmaker(bind=engine, expire_on_commit=False)() as sessao:
        yield sessao


@pytest.fixture
def client(engine, sessao):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)

    def get_db_teste():
        with fabrica() as s:
            yield s

    def api_real_bloqueada():
        raise AssertionError("Os testes NUNCA podem chamar a API real da Anthropic: use a fixture ia_fake.")

    # Equivalente ao @MockBean/@TestConfiguration: troca dependências só nos testes.
    app.dependency_overrides[get_db] = get_db_teste
    app.dependency_overrides[get_cliente_ia] = api_real_bloqueada  # rede de segurança, mesmo com chave no .env
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- IA: usuário somente leitura real + cliente Anthropic falso ---


@pytest.fixture(scope="session")
def engine_ro(engine):
    """Engine do usuário SOMENTE LEITURA, apontando para o banco de teste."""
    url_ro = get_settings().database_url_readonly
    if not url_ro:
        pytest.skip("DATABASE_URL_READONLY não configurada (veja .env.example)")
    url_ro = make_url(url_ro).set(database=engine.url.database)
    usuario = url_ro.username

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conexao:
        if not conexao.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :u"), {"u": usuario}):
            conexao.connection.driver_connection.execute(
                psql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    psql.Identifier(usuario), psql.Literal(url_ro.password)
                )
            )
        # As tabelas do banco de teste são recriadas a cada sessão: reconcede o SELECT.
        conexao.execute(text(f'GRANT USAGE ON SCHEMA public TO "{usuario}"'))
        conexao.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{usuario}"'))

    engine_ro = create_engine(url_ro)
    yield engine_ro
    engine_ro.dispose()


class IaFake:
    """Cliente Anthropic falso (MagicMock) + configuração de IA da aplicação nos testes."""

    def __init__(self) -> None:
        self.cliente = MagicMock(name="anthropic_client")
        self.config = {
            "database_url": "postgresql+psycopg://x:y@localhost/x",
            "anthropic_api_key": "chave-falsa-de-teste",
            "anthropic_model": "modelo-de-teste",
            "database_url_readonly": "postgresql+psycopg://x:y@localhost/x",
            "ia_max_linhas": 100,
            "ia_timeout_segundos": 5,
        }

    def responder(self, texto: str, stop_reason: str = "end_turn") -> None:
        self.cliente.messages.create.return_value = SimpleNamespace(
            stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=texto)]
        )

    @property
    def chamadas(self) -> int:
        return self.cliente.messages.create.call_count


@pytest.fixture
def ia_fake(client, engine_ro) -> IaFake:
    fake = IaFake()
    app.dependency_overrides[get_cliente_ia] = lambda: fake.cliente
    app.dependency_overrides[get_engine_leitura] = lambda: engine_ro
    app.dependency_overrides[get_settings] = lambda: Settings(**fake.config)  # lido a cada requisição
    return fake


# --- Fábricas de dados (via API, para exercitar o caminho real) ---

PRODUTO_BASE = {
    "sku": "DJ-BIP-32A",
    "nome": "Disjuntor Bipolar 32A",
    "categoria": "ELETRICO",
    "subcategoria": "Disjuntores",
    "unidade": "UN",
    "preco_venda": "28.90",
    "estoque_minimo": 10,
}

CPF_VALIDO = "529.982.247-25"
CNPJ_VALIDO = "11.222.333/0001-81"
CLIENTE_BASE = {
    "tipo": "PJ",
    "documento": CNPJ_VALIDO,
    "nome": "Construtora Alvorada Ltda",
    "cidade": "Campinas",
    "uf": "SP",
}


@pytest.fixture
def criar_produto(client):
    def _criar(estoque: int = 0, **campos) -> dict:
        resposta = client.post("/produtos", json={**PRODUTO_BASE, **campos})
        assert resposta.status_code == 201, resposta.text
        produto = resposta.json()
        if estoque:
            mov = {"produto_id": produto["id"], "tipo": "ENTRADA", "quantidade": estoque, "motivo": "Carga inicial"}
            assert client.post("/movimentacoes", json=mov).status_code == 201
            produto["estoque_atual"] = estoque
        return produto

    return _criar


@pytest.fixture
def criar_cliente(client):
    def _criar(**campos) -> dict:
        resposta = client.post("/clientes", json={**CLIENTE_BASE, **campos})
        assert resposta.status_code == 201, resposta.text
        return resposta.json()

    return _criar
