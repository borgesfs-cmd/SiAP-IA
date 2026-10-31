"""PDF dos documentos, registro documental, biblioteca de textos e relatório de pesquisa."""

import io
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from docx import Document
from pypdf import PdfReader
from sqlalchemy import select

from siap import avaliacoes as av
from siap import biblioteca as bb
from siap import catalogo, finalidades, qualitativo, registro_documental, render, satepsi
from siap import documentos as dc
from siap import estatistica as es
from siap import relatorio_pesquisa as rp
from siap.exportar_docx import gerar_pdf
from siap.models import Finalidade, RegistroAuditoria

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
NOME = "Maria Exemplo Fictícia"


def texto_pdf(dados: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(dados)).pages)


def texto_docx(dados: bytes) -> str:
    d = Document(io.BytesIO(dados))
    partes = [p.text for p in d.paragraphs]
    for t in d.tables:
        partes += [c.text for row in t.rows for c in row.cells]
    return "\n".join(partes)


@pytest.fixture
def s(fabrica):
    with fabrica.begin() as sessao:
        finalidades.carregar_finalidades_padrao(sessao)
        dc.salvar_perfil(sessao, nome="Dra. Teste", crp="06/12345", cidade_uf="São Paulo/SP")
        yield sessao


@pytest.fixture
def caso(s):
    fid = s.scalar(select(Finalidade.id).where(Finalidade.nome == "Psicodiagnóstico"))
    inst = catalogo.criar_instrumento(s, nome="Teste A", sigla="TA", categoria="Atenção")
    vid = inst.versoes[0].id
    catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=1),
                                   evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
    a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", idade=30, data_inicio=HOJE,
                           demanda="Queixa de desatenção.", referencia=HOJE)
    r = av.adicionar_registro(s, a.id, tipo="Entrevista inicial", data=HOJE, conteudo="Relata sono irregular.",
                              referencia=HOJE)
    ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Individual presencial",
                                referencia=HOJE)
    av.adicionar_resultado(s, ap.id, medida="Total", escore_bruto="45", percentil="60", classificacao="Média",
                           referencia="Manual do Teste A")
    cod = qualitativo.obter_ou_criar_codigo(s, "Sono")
    qualitativo.codificar(s, registro_id=r.id, codigo_id=cod.id, trecho="sono irregular")
    d = dc.criar_documento(s, a.id, "atestado")
    dc.salvar_secoes(s, d.id, {sec.id: dc._PENDENTE.sub("conteúdo redigido", sec.conteudo) for sec in d.secoes})
    dc.marcar_revisado(s, d.id)
    dc.aprovar(s, d.id, confirmo_revisao_e_autoria=True, referencia=HOJE)
    dc.emitir(s, d.id, referencia=HOJE)
    return a, d


# ------------------------------------------------------------------ PDF

def test_pdf_do_documento_final_com_nome_e_controle(s, caso):
    _, d = caso
    conteudo, final = dc.conteudo_para_exportar(s, d.id)
    texto = texto_pdf(gerar_pdf(conteudo, final=final, nome_pessoa=NOME))
    assert NOME in texto and dc.TOKEN_NOME not in texto
    assert "ATESTADO PSICOLÓGICO" in texto and "CRP 06/12345" in texto and "Página 1 de" in texto
    assert d.hash_conteudo in texto.replace("\n", "") and "RASCUNHO" not in texto


def test_pdf_rascunho_sem_nome_mantem_marcador(s, caso):
    a, _ = caso
    d = dc.criar_documento(s, a.id, "laudo")
    conteudo, final = dc.conteudo_para_exportar(s, d.id)
    texto = texto_pdf(gerar_pdf(conteudo, final=final))
    assert "RASCUNHO" in texto and "NOME DA PESSOA AVALIADA" in texto


def test_render_caracteres_especiais():
    doc = render.Documento([render.Titulo("Ação — “teste” ≥ 50 • ç"), render.Paragrafo("Média ± DP: α = ,81; ω = ,83")])
    texto = texto_pdf(render.para_pdf(doc))
    assert "“TESTE”" in texto and "≥" in texto and "α" in texto and "ω" in texto
    assert "α = ,81" in texto_docx(render.para_docx(doc))


# ---------------------------------------------------- registro documental

def test_registro_documental_reune_o_processo(s, caso):
    a, d = caso
    doc = registro_documental.montar(s, a.id)
    pdf, docx = texto_pdf(render.para_pdf(doc, NOME)), texto_docx(render.para_docx(doc))
    for trecho in (a.codigo, "Psicodiagnóstico", "Queixa de desatenção", "Relata sono irregular", "Teste A",
                   "Manual do Teste A", "Sono", d.codigo, "Avaliação criada", "Dra. Teste"):
        assert trecho in pdf.replace("\n", " ") or trecho in pdf, trecho
        assert trecho in docx, trecho
    assert NOME in pdf and dc.TOKEN_NOME in docx  # nome só quando informado
    registro_documental.registrar_exportacao(s, a.id, "pdf")
    log = s.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == "exportar_registro_documental")).one()
    assert NOME not in log.detalhes


# ------------------------------------------------------------- biblioteca

def test_biblioteca_exemplos_criar_e_validar(s):
    assert bb.carregar_exemplos(s) == len(bb.EXEMPLOS) and bb.carregar_exemplos(s) == 0
    t = bb.criar(s, titulo="Minha frase", categoria="Conclusão", secao="conclusao", texto=f"{dc.TOKEN_NOME} apresenta [[...]].")
    assert t in bb.listar(s, secao="conclusao")
    assert t not in bb.listar(s, secao="analise")  # filtra por seção
    with pytest.raises(catalogo.ErroValidacao, match="Já existe"):
        bb.criar(s, titulo="minha FRASE", categoria="Conclusão", secao="conclusao", texto="x")
    with pytest.raises(catalogo.ErroValidacao, match="identificação direta"):
        bb.criar(s, titulo="Contato", categoria="Outro", secao="qualquer", texto="ligar (11) 98765-4321")
    bb.editar(s, t.id, titulo="Minha frase", categoria="Conclusão", secao="conclusao", texto="Novo.", ativo=False)
    assert t not in bb.listar(s)


def test_inserir_trecho_segue_regras_do_documento(s, caso):
    a, emitido = caso
    t = bb.criar(s, titulo="Cautela", categoria="Análise", secao="analise", texto="Interpretar com cautela.")
    d = dc.criar_documento(s, a.id, "laudo")
    analise = next(x for x in d.secoes if x.chave == "analise")
    bb.inserir_em_secao(s, documento_id=d.id, secao_id=analise.id, trecho_id=t.id)
    assert analise.conteudo.endswith("Interpretar com cautela.") and t.usos == 1
    with pytest.raises(catalogo.ErroValidacao, match="Retificar"):
        bb.inserir_em_secao(s, documento_id=emitido.id, secao_id=emitido.secoes[0].id, trecho_id=t.id)
    with pytest.raises(catalogo.ErroValidacao, match="não pertence"):
        bb.inserir_em_secao(s, documento_id=d.id, secao_id=emitido.secoes[0].id, trecho_id=t.id)


# ------------------------------------------------------- relatório de pesquisa

@pytest.mark.parametrize("valor,casas,sem_zero,esperado", [
    (0.8123, 2, True, ",81"), (-0.123, 2, True, "-,12"), (12.5, 2, False, "12,50"), (1.0, 3, True, "1,000"),
    (float("nan"), 2, False, "—"),
])
def test_formato_apa(valor, casas, sem_zero, esperado):
    assert rp.num(valor, casas, sem_zero) == esperado
    assert rp.valor_p(0.0004) == "< ,001" and rp.valor_p(0.034) == ",034"


def test_relatorio_com_todas_as_analises():
    df = pd.read_csv(Path(__file__).parent / "dados" / "holzinger_swineford_1939.csv")
    itens = list(df.columns)
    rng = np.random.default_rng(1)
    dic = pd.DataFrame((rng.random((400, 4)) < [0.3, 0.5, 0.6, 0.8]).astype(int), columns=list("abcd"))
    doc = rp.montar(
        conjunto="Holzinger", n_total=len(df), descritivas=es.descritivas(df, itens),
        precisao=es.precisao(df, ["x4", "x5", "x6"]), afe=es.afe(df, itens, 3, "promax"), rotacao_afe="promax",
        afc=es.afc(df, {"visual": ["x1", "x2", "x3"], "textual": ["x4", "x5", "x6"], "speed": ["x7", "x8", "x9"]}),
        tri=es.tri(dic, list("abcd"), "2PL"),
    )
    texto = texto_docx(render.para_docx(doc))
    for t in ("Tabela 1", "Tabela 6", "Método", "Resultados", "Referências", "Cronbach", "Horn", "Hendrickson",
              "Hu, L.", "Birnbaum", "85,31", ",931", "[,071; ,114]"):
        assert t in texto, t
    assert "0,931" not in texto  # sem zero à esquerda em CFI
    assert texto_pdf(render.para_pdf(doc))  # PDF gera sem erro


def test_relatorio_sem_analises_recusado():
    with pytest.raises(catalogo.ErroValidacao, match="ao menos uma"):
        rp.montar(conjunto="x", n_total=0)
