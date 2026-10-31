"""Geração do arquivo .docx de um documento psicológico.

O nome da pessoa avaliada é recebido só aqui, substitui o marcador no arquivo gerado e não é gravado.
"""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .documentos import TOKEN_NOME

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")


def data_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _campo(paragrafo, instrucao: str) -> None:
    """Insere um campo do Word (ex.: PAGE, NUMPAGES)."""
    run = paragrafo.add_run()
    inicio = OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    texto = OxmlElement("w:instrText")
    texto.set(qn("xml:space"), "preserve")
    texto.text = instrucao
    fim = OxmlElement("w:fldChar")
    fim.set(qn("w:fldCharType"), "end")
    run._r.append(inicio)
    run._r.append(texto)
    run._r.append(fim)


def _substituir_nome(texto: str, nome: str) -> str:
    return texto.replace(TOKEN_NOME, nome) if nome else texto


def gerar_docx(conteudo: dict, *, final: bool, nome_pessoa: str = "") -> bytes:
    nome_pessoa = (nome_pessoa or "").strip()
    doc = Document()
    secao = doc.sections[0]
    secao.top_margin = secao.bottom_margin = Cm(2.5)
    secao.left_margin = Cm(3)
    secao.right_margin = Cm(2)

    estilo = doc.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(12)
    estilo.paragraph_format.line_spacing = 1.5
    estilo.paragraph_format.space_after = Pt(6)

    if not final:
        cab = secao.header.paragraphs[0]
        cab.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cab.add_run("RASCUNHO — SEM VALIDADE COMO DOCUMENTO PSICOLÓGICO")
        r.bold = True
        r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    rodape = secao.footer.paragraphs[0]
    rodape.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rodape.add_run(f"{conteudo['codigo']} · Página ").font.size = Pt(9)
    _campo(rodape, "PAGE")
    rodape.add_run(" de ").font.size = Pt(9)
    _campo(rodape, "NUMPAGES")
    if conteudo.get("hash"):
        controle = secao.footer.add_paragraph()
        controle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rc = controle.add_run(f"Controle de integridade (SHA-256): {conteudo['hash']}")
        rc.font.size = Pt(7)

    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = titulo.add_run(conteudo["titulo"].upper())
    rt.bold = True
    rt.font.size = Pt(14)

    numerar = len(conteudo["secoes"]) > 1
    for i, sec in enumerate(conteudo["secoes"], start=1):
        if numerar:
            h = doc.add_paragraph()
            rh = h.add_run(f"{i}. {sec['titulo'].upper()}")
            rh.bold = True
        for linha in _substituir_nome(sec["conteudo"], nome_pessoa).split("\n"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            if linha.startswith("- "):
                p.paragraph_format.left_indent = Cm(0.75)
                linha = "• " + linha[2:]
            partes = linha.split(TOKEN_NOME)
            for j, parte in enumerate(partes):
                p.add_run(parte)
                if j < len(partes) - 1:  # nome não informado: marcador destacado
                    destaque = p.add_run(TOKEN_NOME)
                    destaque.bold = True
                    destaque.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    data_emissao = date.fromisoformat(conteudo["data_emissao"])
    local = conteudo.get("local") or ""
    doc.add_paragraph()
    p_data = doc.add_paragraph(f"{local + ', ' if local else ''}{data_extenso(data_emissao)}.")
    p_data.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph()
    for texto, negrito in (("_______________________________________", False),
                           (conteudo["autor"]["nome"], True),
                           (f"Psicóloga(o) — CRP {conteudo['autor']['crp']}", False),
                           (conteudo["autor"].get("titulacao") or "", False)):
        if not texto:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.add_run(texto).bold = negrito

    saida = io.BytesIO()
    doc.save(saida)
    return saida.getvalue()
