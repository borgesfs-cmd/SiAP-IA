"""As migrações Alembic devem produzir exatamente o esquema dos modelos."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from siap.db import criar_engine, migrar
from siap.models import Base


def test_migracoes_correspondem_aos_modelos(url_banco):
    engine = criar_engine(url_banco)
    with engine.connect() as conexao:
        diferencas = compare_metadata(MigrationContext.configure(conexao), Base.metadata)
    engine.dispose()
    assert diferencas == []


def test_migrar_e_idempotente(url_banco):
    engine = criar_engine(url_banco)
    migrar(engine)
    assert "alembic_version" in inspect(engine).get_table_names()
    engine.dispose()
