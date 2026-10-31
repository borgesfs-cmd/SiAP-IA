"""Gerador único de documentos: um conteúdo em blocos → Word (.docx) e PDF.

Usado por documentos psicológicos, registro documental e relatório de pesquisa. O marcador de nome
(`TOKEN_NOME`) é substituído aqui, só no arquivo gerado; se o nome não for informado, o marcador sai
destacado em vermelho para preenchimento manual (CLAUDE.md, regra 4).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .documentos import TOKEN_NOME

FONTES = Path(__file__).resolve().parent.parent / "static" / "fontes"
VERMELHO = (192, 0, 0)


# ------------------------------------------------------------------ blocos

@dataclass
class Titulo:
    texto: str


@dataclass
class Secao:
    texto: str


@dataclass
class Subsecao:
    texto: str


@dataclass
class Paragrafo:
    texto: str
    alinhamento: str = "justificado"  # justificado | esquerda | centro | direita
    negrito: bool = False
    italico: bool = False
    tamanho: float | None = None


@dataclass
class Lista:
    itens: list[str]


@dataclass
class Tabela:
    colunas: list[str]
    linhas: list[list[str]]
    titulo: str = ""
    nota: str = ""
    numero: int | None = None  # "Tabela 1"
    esquerda: bool = False     # alinhar o texto à esquerda (tabelas de texto)


@dataclass
class Assinatura:
    nome: str
    crp: str
    titulacao: str = ""


@dataclass
class Espaco:
    linhas: int = 1


@dataclass
class Documento:
    blocos: list
    cabecalho_alerta: str = ""      # ex.: "RASCUNHO — SEM VALIDADE"
    rodape: str = ""                # ex.: código do documento
    controle: str = ""              # ex.: SHA-256
    tamanho_fonte: float = 12
    entrelinha: float = 1.5
    metadados: dict = field(default_factory=dict)


def _partes_nome(texto: str, nome: str) -> list[tuple[str, bool]]:
    """Divide o texto em (trecho, é_marcador_pendente)."""
    if nome:
        return [(texto.replace(TOKEN_NOME, nome), False)]
    partes = texto.split(TOKEN_NOME)
    saida: list[tuple[str, bool]] = []
    for i, parte in enumerate(partes):
        if parte:
            saida.append((parte, False))
        if i < len(partes) - 1:
            saida.append((TOKEN_NOME, True))
    return saida


# -------------------------------------------------------------------- DOCX

def _campo(paragrafo, instrucao: str, tamanho: float) -> None:
    run = paragrafo.add_run()
    run.font.size = Pt(tamanho)
    inicio, texto, fim = OxmlElement("w:fldChar"), OxmlElement("w:instrText"), OxmlElement("w:fldChar")
    inicio.set(qn("w:fldCharType"), "begin")
    texto.set(qn("xml:space"), "preserve")
    texto.text = instrucao
    fim.set(qn("w:fldCharType"), "end")
    run._r.append(inicio)
    run._r.append(texto)
    run._r.append(fim)


def _bordas_apa(tabela) -> None:
    """Estilo APA: linha acima e abaixo do cabeçalho e no fim da tabela; sem linhas verticais."""
    tbl = tabela._tbl
    props = tbl.tblPr
    bordas = OxmlElement("w:tblBorders")
    for lado in ("top", "bottom"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "8")
        el.set(qn("w:color"), "000000")
        bordas.append(el)
    for lado in ("left", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "nil")
        bordas.append(el)
    props.append(bordas)
    for celula in tabela.rows[0].cells:
        tc_pr = celula._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        el = OxmlElement("w:bottom")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:color"), "000000")
        b.append(el)
        tc_pr.append(b)


_ALINH_DOCX = {"justificado": WD_ALIGN_PARAGRAPH.JUSTIFY, "esquerda": WD_ALIGN_PARAGRAPH.LEFT,
               "centro": WD_ALIGN_PARAGRAPH.CENTER, "direita": WD_ALIGN_PARAGRAPH.RIGHT}


def _escrever_docx(p, texto: str, nome: str, negrito=False, italico=False, tamanho=None):
    for trecho, pendente in _partes_nome(texto, nome):
        run = p.add_run(trecho)
        run.bold = negrito or pendente
        run.italic = italico
        if tamanho:
            run.font.size = Pt(tamanho)
        if pendente:
            run.font.color.rgb = RGBColor(*VERMELHO)


def para_docx(doc: Documento, nome_pessoa: str = "") -> bytes:
    nome = (nome_pessoa or "").strip()
    d = DocxDocument()
    sec = d.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2.5)
    sec.left_margin, sec.right_margin = Cm(3), Cm(2)
    estilo = d.styles["Normal"]
    estilo.font.name = "Arial"
    estilo.font.size = Pt(doc.tamanho_fonte)
    estilo.paragraph_format.line_spacing = doc.entrelinha
    estilo.paragraph_format.space_after = Pt(6)

    if doc.cabecalho_alerta:
        cab = sec.header.paragraphs[0]
        cab.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cab.add_run(doc.cabecalho_alerta)
        r.bold = True
        r.font.color.rgb = RGBColor(*VERMELHO)
    rod = sec.footer.paragraphs[0]
    rod.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rod.add_run(f"{doc.rodape} · Página " if doc.rodape else "Página ").font.size = Pt(9)
    _campo(rod, "PAGE", 9)
    rod.add_run(" de ").font.size = Pt(9)
    _campo(rod, "NUMPAGES", 9)
    if doc.controle:
        c = sec.footer.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.add_run(doc.controle).font.size = Pt(7)

    for b in doc.blocos:
        if isinstance(b, Titulo):
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _escrever_docx(p, b.texto.upper(), nome, negrito=True, tamanho=doc.tamanho_fonte + 2)
        elif isinstance(b, Secao):
            p = d.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            _escrever_docx(p, b.texto, nome, negrito=True)
        elif isinstance(b, Subsecao):
            p = d.add_paragraph()
            _escrever_docx(p, b.texto, nome, negrito=True, italico=True)
        elif isinstance(b, Paragrafo):
            for linha in b.texto.split("\n"):
                p = d.add_paragraph()
                p.alignment = _ALINH_DOCX[b.alinhamento]
                _escrever_docx(p, linha, nome, b.negrito, b.italico, b.tamanho)
        elif isinstance(b, Lista):
            for item in b.itens:
                p = d.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.75)
                _escrever_docx(p, "• " + item, nome)
        elif isinstance(b, Tabela):
            if b.numero is not None or b.titulo:
                if b.numero is not None:
                    p = d.add_paragraph()
                    p.paragraph_format.space_before = Pt(10)
                    _escrever_docx(p, f"Tabela {b.numero}", nome, negrito=True)
                if b.titulo:
                    _escrever_docx(d.add_paragraph(), b.titulo, nome, italico=True)
            t = d.add_table(rows=1 + len(b.linhas), cols=len(b.colunas))
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, col in enumerate(b.colunas):
                cel = t.rows[0].cells[j].paragraphs[0]
                cel.paragraph_format.line_spacing = 1.0
                _escrever_docx(cel, col, nome, negrito=True, tamanho=doc.tamanho_fonte - 2)
            for i, linha in enumerate(b.linhas, start=1):
                for j, valor in enumerate(linha):
                    cel = t.rows[i].cells[j].paragraphs[0]
                    cel.paragraph_format.line_spacing = 1.0
                    _escrever_docx(cel, str(valor), nome, tamanho=doc.tamanho_fonte - 2)
            _bordas_apa(t)
            if b.nota:
                p = d.add_paragraph()
                _escrever_docx(p, "Nota. ", nome, italico=True, tamanho=doc.tamanho_fonte - 2)
                _escrever_docx(p, b.nota, nome, tamanho=doc.tamanho_fonte - 2)
        elif isinstance(b, Assinatura):
            d.add_paragraph()
            for texto, negrito in (("_______________________________________", False), (b.nome, True),
                                   (f"Psicóloga(o) — CRP {b.crp}", False), (b.titulacao, False)):
                if texto:
                    p = d.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.space_after = Pt(0)
                    _escrever_docx(p, texto, nome, negrito=negrito)
        elif isinstance(b, Espaco):
            for _ in range(b.linhas):
                d.add_paragraph()
    saida = io.BytesIO()
    d.save(saida)
    return saida.getvalue()


# --------------------------------------------------------------------- PDF

def para_pdf(doc: Documento, nome_pessoa: str = "") -> bytes:
    from fpdf import FPDF, FontFace
    from fpdf.enums import TableBordersLayout

    nome = (nome_pessoa or "").strip()

    class _PDF(FPDF):
        def header(self):
            if doc.cabecalho_alerta:
                self.set_font("Lib", "B", 10)
                self.set_text_color(*VERMELHO)
                self.cell(0, 6, doc.cabecalho_alerta, align="C", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(0, 0, 0)
                self.ln(2)

        def footer(self):
            self.set_y(-18)
            self.set_font("Lib", "", 8)
            texto = f"{doc.rodape} · Página {self.page_no()} de {{nb}}" if doc.rodape else f"Página {self.page_no()} de {{nb}}"
            self.cell(0, 5, texto, align="C", new_x="LMARGIN", new_y="NEXT")
            if doc.controle:
                self.set_font("Lib", "", 6)
                self.cell(0, 4, doc.controle, align="C")

    pdf = _PDF(format="A4", unit="mm")
    pdf.set_margins(30, 25, 20)
    pdf.set_auto_page_break(True, margin=25)
    for estilo, arquivo in (("", "Regular"), ("B", "Bold"), ("I", "Italic"), ("BI", "BoldItalic")):
        pdf.add_font("Lib", estilo, str(FONTES / f"LiberationSans-{arquivo}.ttf"))
    pdf.alias_nb_pages("{nb}")
    pdf.set_title(doc.metadados.get("titulo", "SIAP-IA"))
    pdf.set_creator("SIAP-IA")
    pdf.add_page()
    corpo = doc.tamanho_fonte
    altura = corpo * 0.3528 * doc.entrelinha  # pt → mm × entrelinha
    alinh = {"justificado": "J", "esquerda": "L", "centro": "C", "direita": "R"}

    def escrever(texto: str, estilo: str = "", tamanho: float = corpo, alinhamento: str = "J", h: float | None = None):
        h = h or tamanho * 0.3528 * doc.entrelinha
        partes = _partes_nome(texto, nome)
        if len(partes) == 1 and not partes[0][1]:
            pdf.set_font("Lib", estilo, tamanho)
            pdf.multi_cell(0, h, partes[0][0], align=alinhamento, new_x="LMARGIN", new_y="NEXT")
            return
        # trecho com marcador pendente: escreve em linha, destacando o marcador
        for trecho, pendente in partes:
            pdf.set_font("Lib", "B" if pendente else estilo, tamanho)
            if pendente:
                pdf.set_text_color(*VERMELHO)
            pdf.write(h, trecho)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(h)

    for b in doc.blocos:
        if isinstance(b, Titulo):
            escrever(b.texto.upper(), "B", corpo + 2, "C")
            pdf.ln(2)
        elif isinstance(b, Secao):
            pdf.ln(2)
            escrever(b.texto, "B", corpo, "L")
        elif isinstance(b, Subsecao):
            escrever(b.texto, "BI", corpo, "L")
        elif isinstance(b, Paragrafo):
            estilo = ("B" if b.negrito else "") + ("I" if b.italico else "")
            for linha in b.texto.split("\n"):
                escrever(linha if linha else " ", estilo, b.tamanho or corpo, alinh[b.alinhamento])
            pdf.ln(1.5)
        elif isinstance(b, Lista):
            for item in b.itens:
                pdf.set_x(pdf.l_margin + 6)
                escrever("• " + item, "", corpo, "L")
        elif isinstance(b, Tabela):
            pdf.ln(2)
            if b.numero is not None:
                escrever(f"Tabela {b.numero}", "B", corpo - 1, "L", h=5.5)
            if b.titulo:
                escrever(b.titulo, "I", corpo - 1, "L", h=5.5)
            pdf.set_font("Lib", "", corpo - 3)
            with pdf.table(borders_layout=TableBordersLayout.HORIZONTAL_LINES, line_height=5,
                           text_align="LEFT" if b.esquerda else "CENTER", first_row_as_headings=True,
                           headings_style=FontFace(emphasis="BOLD")) as tabela:
                cab = tabela.row()
                for col in b.colunas:
                    cab.cell(col.replace(TOKEN_NOME, nome) if nome else col)
                for linha in b.linhas:
                    r = tabela.row()
                    for valor in linha:
                        r.cell(str(valor).replace(TOKEN_NOME, nome) if nome else str(valor))
            if b.nota:
                pdf.ln(1)
                escrever("Nota. " + b.nota, "I", corpo - 3, "L", h=4.5)
            pdf.ln(2)
        elif isinstance(b, Assinatura):
            pdf.ln(10)
            for texto, estilo in (("_______________________________________", ""), (b.nome, "B"),
                                  (f"Psicóloga(o) — CRP {b.crp}", ""), (b.titulacao, "")):
                if texto:
                    escrever(texto, estilo, corpo, "C", h=6)
        elif isinstance(b, Espaco):
            pdf.ln(altura * b.linhas)
    return bytes(pdf.output())
