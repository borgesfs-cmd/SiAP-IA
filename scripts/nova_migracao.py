"""Gera uma nova migração Alembic comparando os modelos com um banco SQLite temporário.

Uso:  python scripts/nova_migracao.py "descrição da mudança"
Revise o arquivo gerado em siap/migracoes/versions/ antes de enviar.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from siap.db import configuracao_alembic  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)

with tempfile.TemporaryDirectory() as pasta:
    engine = create_engine(f"sqlite:///{pasta}/gerar.db")
    cfg = configuracao_alembic()
    with engine.begin() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, "head")
        command.revision(cfg, message=sys.argv[1], autogenerate=True)
