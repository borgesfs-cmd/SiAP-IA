"""Etapa 4: documentos psicológicos, fluxo de aprovação, emissão e exportação."""

import io
import json
from datetime import date, timedelta

import pytest
from docx import Document
from sqlalchemy import select

from siap import avaliacoes as av
from siap import catalogo, finalidades, satepsi
from siap import documentos as dc
from siap.exportar_docx import gerar_docx
from siap.models import Finalidade

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
NOME = "Maria Exemplo Fictícia"


@pytest.fixture
def s(fabrica):
    with fabrica.begin() as sessao:
        finalidades.carregar_finalidades_padrao(sessao)
        dc.salvar_perfil(sessao, nome="Dra. Teste", crp="06/12345", cidade_uf="São Paulo/SP")
        yield sessao


@pytest.fixture
def avaliacao(s):
    fid = s.scalar(select(Finalidade.id).where(Finalidade.nome == "Psicodiagnóstico"))
    inst = catalogo.criar_instrumento(s, nome="Teste A", sigla="TA", categoria="Atenção")
    vid = inst.versoes[0].id
    catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=1),
                                   evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
    a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE - timedelta(days=3),
                           contexto="Encaminhamento clínico", demanda="Queixa de desatenção.", referencia=HOJE)
    av.adicionar_registro(s, a.id, tipo="Entrevista inicial", data=HOJE - timedelta(days=3), conteudo="Relato.",
                          referencia=HOJE)
    ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE - timedelta(days=2),
                                modalidade="Individual presencial", referencia=HOJE)
    av.adicionar_resultado(s, ap.id, medida="Total", escore_bruto="45", percentil="60", classificacao="Média",
                           referencia="Manual do Teste A, 2ª ed.")
    return a


def completar(s, doc):
    """Simula a redação profissional: remove todos os marcadores [[...]]."""
    dc.salvar_secoes(s, doc.id, {sec.id: dc._PENDENTE.sub("Texto redigido pela profissional.", sec.conteudo)
                                 for sec in doc.secoes})


def ate_emitido(s, doc):
    completar(s, doc)
    dc.marcar_revisado(s, doc.id)
    dc.aprovar(s, doc.id, confirmo_revisao_e_autoria=True, referencia=HOJE)
    return dc.emitir(s, doc.id, referencia=HOJE)


def test_rascunho_usa_apenas_dados_registrados(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    secoes = {sec.chave: sec.conteudo for sec in doc.secoes}
    assert list(secoes) == ["identificacao", "demanda", "procedimento", "analise", "conclusao", "referencias"]
    assert dc.TOKEN_NOME in secoes["identificacao"] and "CRP 06/12345" in secoes["identificacao"]
    assert "Psicodiagnóstico" in secoes["identificacao"]
    assert secoes["demanda"] == "Queixa de desatenção."
    assert "Teste A" in secoes["procedimento"] and "Entrevista inicial" in secoes["procedimento"]
    assert "percentil 60" in secoes["analise"] and "[[" in secoes["analise"]  # interpretação fica com a profissional
    assert secoes["conclusao"].startswith("[[")
    assert "Manual do Teste A, 2ª ed." in secoes["referencias"]
    assert doc.codigo == f"{avaliacao.codigo}/LAU-1" and doc.status == dc.RASCUNHO


@pytest.mark.parametrize("tipo", list(dc.MODELOS))
def test_todos_os_tipos_geram_rascunho_e_docx(s, avaliacao, tipo):
    doc = dc.criar_documento(s, avaliacao.id, tipo)
    conteudo, final = dc.conteudo_para_exportar(s, doc.id)
    assert not final
    Document(io.BytesIO(gerar_docx(conteudo, final=False)))  # arquivo válido


def test_marcadores_pendentes_bloqueiam_aprovacao(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    dc.marcar_revisado(s, doc.id)
    with pytest.raises(catalogo.ErroValidacao, match="completar"):
        dc.aprovar(s, doc.id, confirmo_revisao_e_autoria=True, referencia=HOJE)


def test_aprovacao_exige_confirmacao_de_autoria(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    completar(s, doc)
    dc.marcar_revisado(s, doc.id)
    with pytest.raises(catalogo.ErroValidacao, match="autoria"):
        dc.aprovar(s, doc.id, confirmo_revisao_e_autoria=False, referencia=HOJE)


def test_fluxo_exige_ordem(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    completar(s, doc)
    with pytest.raises(catalogo.ErroValidacao):
        dc.aprovar(s, doc.id, confirmo_revisao_e_autoria=True, referencia=HOJE)
    with pytest.raises(catalogo.ErroValidacao):
        dc.emitir(s, doc.id, referencia=HOJE)


def test_secao_obrigatoria_vazia_bloqueia(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    completar(s, doc)
    refs = next(sec for sec in doc.secoes if sec.chave == "referencias")
    dc.salvar_secoes(s, doc.id, {refs.id: ""})
    assert any("Referências" in b for b in dc.checar(s, doc.id, HOJE).bloqueios)


def test_perfil_incompleto_bloqueia(fabrica):
    with fabrica.begin() as s:
        finalidades.carregar_finalidades_padrao(s)
        fid = s.scalar(select(Finalidade.id).where(Finalidade.nome == "Psicodiagnóstico"))
        a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, referencia=HOJE)
        doc = dc.criar_documento(s, a.id, "declaracao")
        assert any("CRP" in b for b in dc.checar(s, doc.id, HOJE).bloqueios)
        with pytest.raises(catalogo.ErroValidacao):
            dc.salvar_perfil(s, nome="Sem CRP", crp="")


def test_editar_documento_revisado_volta_a_rascunho(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    completar(s, doc)
    dc.marcar_revisado(s, doc.id)
    dc.aprovar(s, doc.id, confirmo_revisao_e_autoria=True, referencia=HOJE)
    sec = doc.secoes[1]
    dc.salvar_secoes(s, doc.id, {sec.id: sec.conteudo + " Acréscimo."})
    assert doc.status == dc.RASCUNHO and doc.aprovado_em is None


def test_texto_com_identificador_e_recusado(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "laudo")
    with pytest.raises(catalogo.ErroValidacao, match="identificação direta"):
        dc.salvar_secoes(s, doc.id, {doc.secoes[1].id: "CPF 123.456.789-09"})


def test_emissao_congela_conteudo_e_hash(s, avaliacao):
    doc = ate_emitido(s, dc.criar_documento(s, avaliacao.id, "laudo"))
    assert doc.status == dc.EMITIDO and doc.data_emissao == HOJE
    congelado = json.loads(doc.conteudo_emitido)
    assert dc.calcular_hash(congelado) == doc.hash_conteudo
    with pytest.raises(catalogo.ErroValidacao, match="Retificar"):
        dc.salvar_secoes(s, doc.id, {doc.secoes[0].id: "mudança"})
    # mudar o perfil depois não altera o documento emitido
    dc.salvar_perfil(s, nome="Outro Nome", crp="06/99999")
    conteudo, final = dc.conteudo_para_exportar(s, doc.id)
    assert final and conteudo["autor"]["nome"] == "Dra. Teste" and conteudo["hash"] == doc.hash_conteudo


def test_retificacao_cria_novo_rascunho_e_preserva_original(s, avaliacao):
    original = ate_emitido(s, dc.criar_documento(s, avaliacao.id, "atestado"))
    novo = dc.retificar(s, original.id)
    assert novo.status == dc.RASCUNHO and novo.substitui_id == original.id
    assert novo.codigo == f"{avaliacao.codigo}/ATE-2"
    assert dc.substituido_por(s, original.id).id == novo.id
    assert original.status == dc.EMITIDO
    with pytest.raises(catalogo.ErroValidacao):
        dc.retificar(s, novo.id)


def test_avaliacao_cancelada_nao_gera_documento(s, avaliacao):
    av.alterar_status(s, avaliacao.id, av.CANCELADA)
    with pytest.raises(catalogo.ErroValidacao, match="cancelada"):
        dc.criar_documento(s, avaliacao.id, "laudo")


def test_alerta_declaracao_com_conteudo_clinico(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "declaracao")
    dc.salvar_secoes(s, doc.id, {doc.secoes[0].id: f"Declaro que {dc.TOKEN_NOME} apresenta transtorno."})
    assert any("Declaração" in a for a in dc.checar(s, doc.id, HOJE).alertas)


# ------------------------------------------------- nome nunca é gravado

def _texto_docx(dados: bytes) -> str:
    d = Document(io.BytesIO(dados))
    partes = [p.text for p in d.paragraphs]
    for sec in d.sections:
        partes += [p.text for p in sec.header.paragraphs] + [p.text for p in sec.footer.paragraphs]
    return "\n".join(partes)


def test_nome_entra_so_no_arquivo_e_nunca_no_banco(s, avaliacao):
    doc = ate_emitido(s, dc.criar_documento(s, avaliacao.id, "laudo"))
    conteudo, final = dc.conteudo_para_exportar(s, doc.id)
    texto = _texto_docx(gerar_docx(conteudo, final=final, nome_pessoa=NOME))
    assert NOME in texto and dc.TOKEN_NOME not in texto
    assert doc.hash_conteudo in texto and "Página" in texto and "RASCUNHO" not in texto
    backup = json.dumps(catalogo.exportar_backup(s), ensure_ascii=False)
    assert NOME not in backup and "Maria" not in backup


def test_sem_nome_o_marcador_permanece(s, avaliacao):
    doc = dc.criar_documento(s, avaliacao.id, "atestado")
    conteudo, final = dc.conteudo_para_exportar(s, doc.id)
    texto = _texto_docx(gerar_docx(conteudo, final=final))
    assert dc.TOKEN_NOME in texto and "RASCUNHO" in texto


def test_backup_inclui_documentos(s, avaliacao):
    ate_emitido(s, dc.criar_documento(s, avaliacao.id, "parecer"))
    dados = catalogo.exportar_backup(s)
    assert dados["documentos"][0]["hash_conteudo"] and dados["secoes_documento"] and dados["perfil_profissional"]
