"""Engine e sessão do SQLAlchemy.

- Engine  ~ DataSource/pool de conexões do Spring.
- Session ~ EntityManager (unidade de trabalho). Diferente do Spring, NÃO existe
  @Transactional mágico: o service controla commit/rollback explicitamente
  (session.commit()), o que deixa a fronteira da transação visível no código.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Nomes determinísticos para PK/FK/CHECK/índices. Sem isso o Postgres inventa nomes
# e o Alembic não consegue apagar/alterar essas constraints depois.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe base de todos os modelos (o Alembic lê o Base.metadata)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependência do FastAPI: abre uma sessão por requisição e sempre a fecha.

    Equivale a injetar o EntityManager no Spring; aqui a injeção é feita
    por Depends(get_db) na assinatura da rota.
    """
    with SessionLocal() as session:
        yield session


@contextmanager
def transacao(db: Session) -> Iterator[None]:
    """Tudo ou nada: commita ao sair do bloco, ou faz rollback (liberando locks) se houver erro.

    É o `@Transactional` do Spring escrito à mão, só que explícito no ponto onde se usa.
    """
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise
