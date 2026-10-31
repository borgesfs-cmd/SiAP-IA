"""Catálogo, versões, verificações, auditoria, persistência e backup."""

import base64
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from siap import catalogo, satepsi
from siap.db import criar_engine, fabrica_sessoes, normalizar_url
from siap.inventario import INVENTARIO_INICIAL, carregar_inventario_inicial
from siap.models import RegistroAuditoria, VerificacaoSATEPSI

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _teste_d2(s):
    return catalogo.criar_instrumento(s, nome="Teste d2", sigla="d2", categoria="Atenção",
                                      versoes=["d2", "d2-R"])


def test_multiplas_versoes_do_mesmo_teste(fabrica):
    with fabrica.begin() as s:
        inst = _teste_d2(s)
        assert [v.nome_versao for v in inst.versoes] == ["d2", "d2-R"]


def test_versao_padrao_usa_sigla(fabrica):
    with fabrica.begin() as s:
        inst = catalogo.criar_instrumento(s, nome="Teste X", sigla="TX", categoria="Outros")
        assert [v.nome_versao for v in inst.versoes] == ["TX"]


def test_nome_e_versao_duplicados_sao_recusados(fabrica):
    with fabrica.begin() as s:
        inst = _teste_d2(s)
        with pytest.raises(catalogo.ErroValidacao):
            catalogo.criar_instrumento(s, nome="teste D2", categoria="Atenção")
        with pytest.raises(catalogo.ErroValidacao):
            catalogo.adicionar_versao(s, inst.id, nome_versao="D2-r")


def test_categoria_invalida_recusada(fabrica):
    with fabrica.begin() as s, pytest.raises(catalogo.ErroValidacao):
        catalogo.criar_instrumento(s, nome="Y", categoria="Inexistente")


def test_cadastro_persiste_apos_reinicio(url_banco):
    engine = criar_engine(url_banco)
    with fabrica_sessoes(engine).begin() as s:
        _teste_d2(s)
    engine.dispose()

    engine = criar_engine(url_banco)
    with fabrica_sessoes(engine).begin() as s:
        linhas = catalogo.listar_catalogo(s, HOJE)
    engine.dispose()
    assert {(l.instrumento, l.versao) for l in linhas} == {("Teste d2", "d2"), ("Teste d2", "d2-R")}


def test_novo_teste_entra_bloqueado(fabrica):
    with fabrica.begin() as s:
        inst = _teste_d2(s)
        for v in inst.versoes:
            sit = catalogo.pode_uso_profissional(s, v.id, HOJE)
            assert sit.status == satepsi.NAO_VERIFICADO and not sit.liberado


def test_verificacao_e_por_versao(fabrica):
    with fabrica.begin() as s:
        d2, d2r = _teste_d2(s).versoes
        catalogo.registrar_verificacao(s, d2.id, status=satepsi.FAVORAVEL, data_consulta=HOJE,
                                       evidencia_nome="d2.png", evidencia_tipo="image/png",
                                       evidencia=PNG, referencia=HOJE)
        assert catalogo.pode_uso_profissional(s, d2.id, HOJE).liberado
        assert not catalogo.pode_uso_profissional(s, d2r.id, HOJE).liberado


def test_favoravel_exige_evidencia(fabrica):
    with fabrica.begin() as s:
        v = _teste_d2(s).versoes[0]
        with pytest.raises(catalogo.ErroValidacao):
            catalogo.registrar_verificacao(s, v.id, status=satepsi.FAVORAVEL, data_consulta=HOJE,
                                           referencia=HOJE)
        # situação bloqueante pode ser registrada sem evidência
        catalogo.registrar_verificacao(s, v.id, status=satepsi.NAO_LOCALIZADO, data_consulta=HOJE,
                                       referencia=HOJE)


@pytest.mark.parametrize("kwargs", [
    {"status": "nao_verificado"},
    {"data_consulta": HOJE + timedelta(days=1)},
    {"validade_dias": 0},
    {"validade_dias": 400},
    {"fonte": "  "},
    {"evidencia_tipo": "text/plain"},
    {"evidencia": b"x" * (catalogo.EVIDENCIA_TAMANHO_MAX + 1)},
])
def test_validacoes_da_verificacao(fabrica, kwargs):
    base = dict(status=satepsi.FAVORAVEL, data_consulta=HOJE, evidencia_nome="e.png",
                evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
    base.update(kwargs)
    with fabrica.begin() as s:
        v = _teste_d2(s).versoes[0]
        with pytest.raises(catalogo.ErroValidacao):
            catalogo.registrar_verificacao(s, v.id, **base)


def test_desfavoravel_posterior_bloqueia_e_historico_e_preservado(fabrica):
    with fabrica.begin() as s:
        v = _teste_d2(s).versoes[0]
        catalogo.registrar_verificacao(s, v.id, status=satepsi.FAVORAVEL,
                                       data_consulta=HOJE - timedelta(days=10), evidencia_nome="a.pdf",
                                       evidencia_tipo="application/pdf", evidencia=b"%PDF-1.4", referencia=HOJE)
        catalogo.registrar_verificacao(s, v.id, status=satepsi.DESFAVORAVEL, data_consulta=HOJE,
                                       referencia=HOJE)
        assert not catalogo.pode_uso_profissional(s, v.id, HOJE).liberado
        assert s.scalar(select(func.count(VerificacaoSATEPSI.id))) == 2


def test_evidencia_guarda_hash_e_conteudo(fabrica):
    with fabrica.begin() as s:
        v = _teste_d2(s).versoes[0]
        ver = catalogo.registrar_verificacao(s, v.id, status=satepsi.FAVORAVEL, data_consulta=HOJE,
                                             evidencia_nome="e.png", evidencia_tipo="image/png",
                                             evidencia=PNG, referencia=HOJE)
        ver_id = ver.id
    with fabrica.begin() as s:
        carregada = catalogo.carregar_evidencia(s, ver_id)
        assert carregada.evidencia == PNG and len(carregada.evidencia_sha256) == 64


def test_toda_alteracao_gera_auditoria(fabrica):
    with fabrica.begin() as s:
        inst = _teste_d2(s)
        catalogo.atualizar_instrumento(s, inst.id, construto="Atenção concentrada")
        catalogo.atualizar_instrumento(s, inst.id, construto="Atenção concentrada")  # sem mudança
        catalogo.registrar_verificacao(s, inst.versoes[0].id, status=satepsi.EM_AVALIACAO,
                                       data_consulta=HOJE, referencia=HOJE)
        acoes = [r.acao for r in s.scalars(select(RegistroAuditoria).order_by(RegistroAuditoria.id))]
    assert acoes == ["criar_instrumento", "criar_versao", "criar_versao",
                     "editar_instrumento", "registrar_verificacao_satepsi"]


def test_edicao_rejeita_campo_nao_permitido(fabrica):
    with fabrica.begin() as s:
        inst = _teste_d2(s)
        with pytest.raises(catalogo.ErroValidacao):
            catalogo.atualizar_instrumento(s, inst.id, id=99)


def test_inventario_inicial_carrega_uma_vez_e_tudo_bloqueado(fabrica):
    with fabrica.begin() as s:
        assert carregar_inventario_inicial(s) == len(INVENTARIO_INICIAL)
        assert carregar_inventario_inicial(s) == 0
        linhas = catalogo.listar_catalogo(s, HOJE)
    assert len(linhas) == len(INVENTARIO_INICIAL) + 1  # d2 tem duas versões
    assert not any(l.situacao.liberado for l in linhas)
    assert {"d2", "d2-R"} <= {l.versao for l in linhas}


def test_backup_contem_tudo(fabrica):
    with fabrica.begin() as s:
        v = _teste_d2(s).versoes[0]
        catalogo.registrar_verificacao(s, v.id, status=satepsi.FAVORAVEL, data_consulta=HOJE,
                                       evidencia_nome="e.png", evidencia_tipo="image/png",
                                       evidencia=PNG, referencia=HOJE)
    with fabrica.begin() as s:
        dados = catalogo.exportar_backup(s)
    json.dumps(dados)  # serializável
    assert len(dados["instrumentos"]) == 1 and len(dados["versoes_instrumento"]) == 2
    assert base64.b64decode(dados["verificacoes_satepsi"][0]["evidencia"]["base64"]) == PNG
    assert dados["auditoria"]


def test_normalizar_url_postgres():
    assert normalizar_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalizar_url("postgresql://u:p@h/db?sslmode=require").startswith("postgresql+psycopg://")
    assert normalizar_url("sqlite:///x.db") == "sqlite:///x.db"


@pytest.mark.parametrize("url", [
    "postgresql://...copiado do Neon...?sslmode=require",
    "postgresql://usuario:senha@/neondb",
    "postgresql://usuario:senha@ep-x..neon.tech/db",
    "isto não é uma url",
])
def test_url_de_banco_invalida_gera_mensagem_clara(url):
    from siap.db import ConfiguracaoBancoInvalida, normalizar_url

    with pytest.raises(ConfiguracaoBancoInvalida, match="DATABASE_URL"):
        criar_engine(normalizar_url(url))


def test_localhost_e_aceito_pela_validacao():
    from siap.db import validar_url

    validar_url("postgresql+psycopg://u:p@localhost:5432/db")


def test_banco_inacessivel_gera_mensagem_clara():
    from siap.db import ConfiguracaoBancoInvalida

    with pytest.raises(ConfiguracaoBancoInvalida, match="Não foi possível conectar") as erro:
        criar_engine("postgresql+psycopg://u:Xq9zSenhaTeste@127.0.0.1:1/db?connect_timeout=2")
    assert "Xq9zSenhaTeste" not in str(erro.value)
