"""Etapa 3: finalidades, avaliações, registros, aplicações e resultados."""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from siap import avaliacoes as av
from siap import catalogo, finalidades, satepsi
from siap.models import Finalidade, RegistroAuditoria

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture
def s(fabrica):
    with fabrica.begin() as sessao:
        finalidades.carregar_finalidades_padrao(sessao)
        yield sessao


def fin(s, nome) -> int:
    return s.scalar(select(Finalidade.id).where(Finalidade.nome == nome))


def versao_liberada(s, nome="Teste A", **kw) -> int:
    inst = catalogo.criar_instrumento(s, nome=nome, sigla=nome[-1], categoria="Atenção")
    vid = inst.versoes[0].id
    catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=1),
                                   evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG,
                                   referencia=HOJE, **kw)
    return vid


def nova_avaliacao(s, finalidade="Psicodiagnóstico", **kw):
    base = dict(finalidade_id=fin(s, finalidade), faixa_etaria="Adulto", data_inicio=HOJE, referencia=HOJE)
    base.update(kw)
    return av.criar_avaliacao(s, **base)


# --------------------------------------------------------------- finalidades

def test_finalidades_padrao_incluem_psicodiagnostico_e_neuropsicologica(s):
    nomes = {f.nome for f in finalidades.listar_finalidades(s)}
    assert {"Psicodiagnóstico", "Avaliação neuropsicológica", "Trânsito (CNH)",
            "Porte/posse de arma de fogo"} <= nomes
    assert finalidades.carregar_finalidades_padrao(s) == 0  # idempotente


def test_incluir_finalidade_manual(s):
    f = finalidades.criar_finalidade(s, nome="Avaliação pré-cirúrgica (bariátrica)", descricao="x")
    assert not f.padrao and f.ativa
    with pytest.raises(catalogo.ErroValidacao):
        finalidades.criar_finalidade(s, nome="avaliação PRÉ-cirúrgica (bariátrica)")
    with pytest.raises(catalogo.ErroValidacao):
        finalidades.criar_finalidade(s, nome="  ")


def test_finalidade_desativada_nao_aceita_nova_avaliacao(s):
    nova = finalidades.criar_finalidade(s, nome="Orientação profissional")
    finalidades.definir_ativa(s, nova.id, False)
    with pytest.raises(catalogo.ErroValidacao, match="desativada"):
        av.criar_avaliacao(s, finalidade_id=nova.id, faixa_etaria="Adolescente", data_inicio=HOJE, referencia=HOJE)
    finalidades.definir_ativa(s, nova.id, True)
    av.criar_avaliacao(s, finalidade_id=nova.id, faixa_etaria="Adolescente", data_inicio=HOJE, referencia=HOJE)


# ------------------------------------------------- SATEPSI × finalidade

def test_verificacao_restrita_a_finalidades(s):
    vid = versao_liberada(s, abrange_todas_finalidades=False, finalidades_ids=[fin(s, "Trânsito (CNH)")])
    assert catalogo.pode_uso_profissional(s, vid, HOJE, fin(s, "Trânsito (CNH)")).liberado
    bloq = catalogo.pode_uso_profissional(s, vid, HOJE, fin(s, "Psicodiagnóstico"))
    assert not bloq.liberado and "Psicodiagnóstico" in bloq.motivo


def test_verificacao_para_todas_as_finalidades(s):
    vid = versao_liberada(s)
    for f in finalidades.listar_finalidades(s):
        assert catalogo.pode_uso_profissional(s, vid, HOJE, f.id).liberado


def test_restricao_sem_finalidade_selecionada_e_recusada(s):
    with pytest.raises(catalogo.ErroValidacao, match="ao menos uma"):
        versao_liberada(s, abrange_todas_finalidades=False, finalidades_ids=[])


# ------------------------------------------------------------- avaliações

def test_codigo_sequencial_por_ano(s):
    a1, a2 = nova_avaliacao(s), nova_avaliacao(s)
    a3 = nova_avaliacao(s, data_inicio=date(2025, 5, 1))
    assert (a1.codigo, a2.codigo, a3.codigo) == ("AV-2026-001", "AV-2026-002", "AV-2025-001")


@pytest.mark.parametrize("texto", [
    "CPF 123.456.789-09", "cpf 12345678909", "contato: fulano@exemplo.com", "tel (11) 98765-4321",
])
def test_recusa_identificadores_diretos(s, texto):
    with pytest.raises(catalogo.ErroValidacao, match="identificação direta"):
        nova_avaliacao(s, demanda=texto)


def test_textos_clinicos_comuns_sao_aceitos(s):
    a = nova_avaliacao(s, demanda="Queixa de desatenção há 2 anos; escore 112 no último teste; 3 sessões.")
    av.adicionar_registro(s, a.id, tipo="Anamnese", data=HOJE, conteudo="Relata sono de 6 h/noite.", referencia=HOJE)


def test_validacoes_de_perfil(s):
    with pytest.raises(catalogo.ErroValidacao):
        nova_avaliacao(s, faixa_etaria="Bebê")
    with pytest.raises(catalogo.ErroValidacao):
        nova_avaliacao(s, idade=130)
    with pytest.raises(catalogo.ErroValidacao):
        nova_avaliacao(s, data_inicio=HOJE + timedelta(days=1))


def test_registros_e_edicao_guardam_versao_anterior(s):
    a = nova_avaliacao(s)
    r = av.adicionar_registro(s, a.id, tipo="Entrevista inicial", data=HOJE, conteudo="Versão 1", referencia=HOJE)
    av.editar_registro(s, r.id, conteudo="Versão 2")
    assert r.conteudo == "Versão 2" and r.editado_em is not None
    log = s.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == "editar_registro_avaliacao")).one()
    assert json.loads(log.detalhes)["conteudo_anterior"] == "Versão 1"


# -------------------------------------------------------------- aplicações

def test_aplicacao_bloqueada_sem_verificacao(s):
    a = nova_avaliacao(s)
    inst = catalogo.criar_instrumento(s, nome="Sem verificação", categoria="Memória")
    with pytest.raises(catalogo.ErroValidacao, match="bloqueado"):
        av.registrar_aplicacao(s, a.id, versao_id=inst.versoes[0].id, data_aplicacao=HOJE,
                               modalidade="Individual presencial", referencia=HOJE)


def test_aplicacao_bloqueada_para_finalidade_nao_coberta(s):
    vid = versao_liberada(s, abrange_todas_finalidades=False, finalidades_ids=[fin(s, "Trânsito (CNH)")])
    neuro = nova_avaliacao(s, finalidade="Avaliação neuropsicológica")
    with pytest.raises(catalogo.ErroValidacao, match="não cobre"):
        av.registrar_aplicacao(s, neuro.id, versao_id=vid, data_aplicacao=HOJE,
                               modalidade="Individual presencial", referencia=HOJE)
    transito = nova_avaliacao(s, finalidade="Trânsito (CNH)")
    ap = av.registrar_aplicacao(s, transito.id, versao_id=vid, data_aplicacao=HOJE,
                                modalidade="Coletiva presencial", referencia=HOJE)
    assert ap.satepsi_status_no_registro == satepsi.FAVORAVEL and ap.verificacao_id_no_registro


def test_opcoes_de_versao_refletem_a_finalidade(s):
    vid = versao_liberada(s, abrange_todas_finalidades=False, finalidades_ids=[fin(s, "Trânsito (CNH)")])
    psico = nova_avaliacao(s)
    opcao = next(o for o in av.opcoes_de_versao(s, psico.id, HOJE) if o.versao_id == vid)
    assert not opcao.situacao.liberado


def test_validacoes_de_aplicacao(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s, data_inicio=HOJE - timedelta(days=5))
    for kw in (dict(data_aplicacao=HOJE + timedelta(days=1)), dict(data_aplicacao=HOJE - timedelta(days=6)),
               dict(modalidade="Telepatia")):
        base = dict(versao_id=vid, data_aplicacao=HOJE, modalidade="Individual presencial", referencia=HOJE)
        base.update(kw)
        with pytest.raises(catalogo.ErroValidacao):
            av.registrar_aplicacao(s, a.id, **base)


def test_resultados_exigem_medida_valor_e_referencia(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s)
    ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Individual presencial",
                                referencia=HOJE)
    for faltando in (dict(medida=""), dict(escore_bruto="", percentil=""), dict(referencia="")):
        campos = dict(medida="Total", escore_bruto="45", percentil="60", referencia="Manual, tabela 3")
        campos.update(faltando)
        with pytest.raises(catalogo.ErroValidacao):
            av.adicionar_resultado(s, ap.id, **campos)
    r = av.adicionar_resultado(s, ap.id, medida="Total", escore_bruto="45", percentil="60",
                               classificacao="Médio", referencia="Manual, tabela 3")
    av.editar_resultado(s, r.id, medida="Total", escore_bruto="47", percentil="65",
                        classificacao="Médio", referencia="Manual, tabela 3")
    assert r.escore_bruto == "47" and r.editado_em is not None


def test_finalidade_nao_muda_apos_aplicacao(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s)
    perfil = dict(faixa_etaria="Adulto", idade=30, escolaridade="", contexto="", demanda="")
    av.atualizar_avaliacao(s, a.id, finalidade_id=fin(s, "Avaliação neuropsicológica"), **perfil)
    av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Individual presencial",
                           referencia=HOJE)
    with pytest.raises(catalogo.ErroValidacao, match="finalidade"):
        av.atualizar_avaliacao(s, a.id, finalidade_id=fin(s, "Psicodiagnóstico"), **perfil)


def test_avaliacao_concluida_fica_somente_leitura_ate_reabrir(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s)
    av.alterar_status(s, a.id, av.CONCLUIDA, referencia=HOJE)
    assert a.data_conclusao == HOJE
    with pytest.raises(catalogo.ErroValidacao, match="reabra"):
        av.adicionar_registro(s, a.id, tipo="Devolutiva", data=HOJE, conteudo="x", referencia=HOJE)
    with pytest.raises(catalogo.ErroValidacao, match="reabra"):
        av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Outra", referencia=HOJE)
    av.alterar_status(s, a.id, av.EM_ANDAMENTO)
    assert a.data_conclusao is None
    av.adicionar_registro(s, a.id, tipo="Devolutiva", data=HOJE, conteudo="x", referencia=HOJE)


def test_alerta_quando_versao_perde_elegibilidade(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s)
    av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Individual presencial",
                           referencia=HOJE)
    assert av.alertas_conformidade(s, HOJE) == []
    catalogo.registrar_verificacao(s, vid, status=satepsi.DESFAVORAVEL, data_consulta=HOJE, referencia=HOJE)
    alertas = av.alertas_conformidade(s, HOJE)
    assert [x.codigo for x in alertas] == [a.codigo]
    assert len(a.aplicacoes) == 1  # nada é apagado
    av.alterar_status(s, a.id, av.CONCLUIDA, referencia=HOJE)
    assert av.alertas_conformidade(s, HOJE) == []  # só avaliações em andamento


def test_backup_inclui_tabelas_da_etapa_3(s):
    vid = versao_liberada(s)
    a = nova_avaliacao(s)
    ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Outra", referencia=HOJE)
    av.adicionar_resultado(s, ap.id, medida="Total", percentil="50", referencia="Manual")
    dados = catalogo.exportar_backup(s)
    for tabela in ("finalidades", "avaliacoes", "registros_avaliacao", "aplicacoes_instrumento",
                   "resultados_registrados", "verificacao_finalidades"):
        assert tabela in dados
    assert dados["avaliacoes"][0]["codigo"] == "AV-2026-001"
