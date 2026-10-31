"""Ambiente Alembic: recebe a conexão pronta de siap.db.migrar (sem alembic.ini)."""

from alembic import context

from siap.models import Base

conexao = context.config.attributes["connection"]
context.configure(
    connection=conexao,
    target_metadata=Base.metadata,
    render_as_batch=conexao.dialect.name == "sqlite",
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
