"""Teste de fumaça: todas as páginas abrem sem erro com banco novo."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
PAGINAS = ["paginas/panorama.py", "paginas/avaliacoes.py", "paginas/documentos.py", "paginas/qualitativo.py", "paginas/consultor_ia.py", "paginas/catalogo.py",
           "paginas/verificacao_satepsi.py", "paginas/finalidades.py", "paginas/auditoria_backup.py"]


@pytest.fixture(autouse=True)
def banco_isolado(monkeypatch, url_banco):
    monkeypatch.setenv("DATABASE_URL", url_banco)
    monkeypatch.chdir(RAIZ)


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_abre_pela_navegacao(pagina):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.run()
    at.switch_page(pagina).run()
    assert not at.exception, at.exception
    assert at.title


def test_panorama_mostra_inventario_bloqueado():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.run()
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Testes no catálogo"] == "14"
    assert metricas["Versões"] == "15"
    assert metricas["Elegíveis a uso profissional"] == "0"


def test_senha_protege_quando_configurada():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.secrets["APP_PASSWORD"] = "segredo"
    at.run()
    assert not at.metric  # nada exibido antes da senha
    at.text_input[0].input("errada")
    at.button[0].click().run()
    assert at.error and not at.metric
    at.text_input[0].input("segredo")
    at.button[0].click().run()
    assert at.metric


def test_url_invalida_mostra_erro_amigavel(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://...copiado do Neon...?sslmode=require")
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception
    assert "Banco de dados não configurado" in at.error[0].value
