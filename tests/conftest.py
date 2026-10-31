import pytest

from siap.db import criar_engine, fabrica_sessoes


@pytest.fixture
def url_banco(tmp_path):
    return f"sqlite:///{tmp_path / 'teste.db'}"


@pytest.fixture
def fabrica(url_banco):
    engine = criar_engine(url_banco)
    yield fabrica_sessoes(engine)
    engine.dispose()
