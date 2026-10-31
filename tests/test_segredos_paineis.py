"""Chave da API cifrada e painéis."""

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from siap import avaliacoes as av
from siap import catalogo, finalidades, ia, satepsi, segredos
from siap import paineis as pn
from siap.models import Finalidade, RegistroAuditoria, SegredoCifrado

HOJE = date(2026, 10, 31)
CHAVE = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUV-wxyz"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture
def s(fabrica, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("APP_PASSWORD", "senha-do-app")
    with fabrica.begin() as sessao:
        finalidades.carregar_finalidades_padrao(sessao)
        yield sessao


# --------------------------------------------------------------- segredos

@pytest.mark.parametrize("colado", [CHAVE, f"  {CHAVE}\n", f'"{CHAVE}"', f'ANTHROPIC_API_KEY = "{CHAVE}"'])
def test_normaliza_o_que_vem_ao_colar(colado):
    assert segredos.normalizar_chave_anthropic(colado) == CHAVE


@pytest.mark.parametrize("colado", ["", "abc", "sk-ant-curta", "sk-ant-com espaco-no-meio-xxxxxxxx"])
def test_recusa_texto_que_nao_e_chave(colado):
    with pytest.raises(catalogo.ErroValidacao):
        segredos.normalizar_chave_anthropic(colado)


def test_chave_fica_cifrada_e_fora_do_backup_e_auditoria(s):
    segredos.salvar(s, segredos.CHAVE_ANTHROPIC, CHAVE)
    registro = s.get(SegredoCifrado, segredos.CHAVE_ANTHROPIC)
    assert CHAVE not in registro.cifrado and registro.final == "wxyz"
    assert segredos.ler(s, segredos.CHAVE_ANTHROPIC) == CHAVE
    est = segredos.estado(s, segredos.CHAVE_ANTHROPIC)
    assert est.legivel and est.mascarado.endswith("wxyz") and CHAVE not in est.mascarado
    backup = json.dumps(catalogo.exportar_backup(s))
    assert "segredos_cifrados" not in backup and CHAVE not in backup and registro.cifrado not in backup
    auditoria = " ".join(r.detalhes for r in s.scalars(select(RegistroAuditoria)))
    assert CHAVE not in auditoria


def test_senha_do_app_trocada_torna_chave_ilegivel(s, monkeypatch):
    segredos.salvar(s, segredos.CHAVE_ANTHROPIC, CHAVE)
    monkeypatch.setenv("APP_PASSWORD", "outra-senha")
    est = segredos.estado(s, segredos.CHAVE_ANTHROPIC)
    assert est.existe and not est.legivel
    assert segredos.ler(s, segredos.CHAVE_ANTHROPIC) is None


def test_sem_senha_do_app_nao_salva(s, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    with pytest.raises(catalogo.ErroValidacao, match="APP_PASSWORD"):
        segredos.salvar(s, segredos.CHAVE_ANTHROPIC, CHAVE)


def test_ia_usa_chave_salva_e_secrets_tem_prioridade(s, monkeypatch):
    ia.definir_consentimento(s, True)
    assert not ia.situacao(s)[0]
    segredos.salvar(s, segredos.CHAVE_ANTHROPIC, CHAVE)
    assert ia.situacao(s) == (True, "") and ia.chave_api(s) == CHAVE
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dos-secrets-xxxxxxxxxxxx")
    assert ia.chave_api(s) == "sk-ant-dos-secrets-xxxxxxxxxxxx"
    segredos.remover(s, segredos.CHAVE_ANTHROPIC)
    assert s.get(SegredoCifrado, segredos.CHAVE_ANTHROPIC) is None


def test_testar_chave_com_cliente_falso():
    ok = SimpleNamespace(models=SimpleNamespace(retrieve=lambda m: SimpleNamespace(display_name="Claude Opus 5.5")))
    assert ia.testar_chave(CHAVE, cliente=ok) == "Claude Opus 5.5"


# ---------------------------------------------------------------- painéis

@pytest.mark.parametrize("texto,esperado", [
    ("55", 55.0), ("55,5", 55.5), ("P75", 75.0), (" 0 ", 0.0), ("100", 100.0),
    ("50-75", None), ("Médio", None), ("120", None), ("", None), (None, None),
])
def test_percentil_numerico(texto, esperado):
    assert pn.percentil_numerico(texto) == esperado


def _cenario(s):
    fid = s.scalar(select(Finalidade.id).where(Finalidade.nome == "Psicodiagnóstico"))
    inst = catalogo.criar_instrumento(s, nome="Teste A", sigla="TA", categoria="Atenção")
    vid = inst.versoes[0].id
    catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=80),
                                   evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
    codigos = []
    for p in ("40", "70", "Médio"):
        a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, referencia=HOJE)
        ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Outra", referencia=HOJE)
        av.adicionar_resultado(s, ap.id, medida="Total", percentil=p if p[0].isdigit() else "",
                               classificacao="Médio", referencia="Manual")
        codigos.append(a)
    av.alterar_status(s, codigos[0].id, av.CONCLUIDA, referencia=HOJE)
    return codigos, vid


def test_visao_geral(s):
    _cenario(s)
    vg = pn.visao_geral(s, HOJE)
    assert (vg.total_avaliacoes, vg.em_andamento, vg.concluidas) == (3, 2, 1)
    assert vg.por_finalidade == [{"categoria": "Psicodiagnóstico", "quantidade": 3}]
    assert vg.por_mes[-1] == {"mes": "2026-10", "quantidade": 3} and len(vg.por_mes) == 12
    assert vg.instrumentos_mais_usados[0]["quantidade"] == 3
    assert vg.versoes_elegiveis == 1 and vg.vencimentos and vg.vencimentos[0]["vence_em"] == HOJE + timedelta(days=10)


def test_resultados_comparativo_e_linha_do_tempo(s):
    avaliacoes_, vid = _cenario(s)
    res = pn.resultados_da_avaliacao(s, avaliacoes_[1].id)
    assert res[0]["percentil"] == 70.0
    assert pn.resultados_da_avaliacao(s, avaliacoes_[2].id)[0]["percentil"] is None
    opcoes = pn.medidas_comparaveis(s)
    assert len(opcoes) == 1
    comp = pn.comparativo(s, *opcoes[0])
    assert sorted(c["percentil"] for c in comp) == [40.0, 70.0]
    tipos = [e["tipo"] for e in pn.linha_do_tempo(s, avaliacoes_[0].id)]
    assert tipos[0] == "Início" and "Instrumento" in tipos and tipos[-1] == "Conclusão"
