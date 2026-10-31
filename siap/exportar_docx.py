"""Exportação dos documentos psicológicos para Word e PDF (via siap.render).

O nome da pessoa avaliada é recebido só aqui, substitui o marcador no arquivo gerado e não é gravado.
"""

from __future__ import annotations

from datetime import date

from . import render
from .documentos import TOKEN_NOME  # noqa: F401  (reexportado por compatibilidade)

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")


def data_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def documento_psicologico(conteudo: dict, *, final: bool) -> render.Documento:
    blocos: list = [render.Titulo(conteudo["titulo"])]
    numerar = len(conteudo["secoes"]) > 1
    for i, sec in enumerate(conteudo["secoes"], start=1):
        if numerar:
            blocos.append(render.Secao(f"{i}. {sec['titulo'].upper()}"))
        linhas = sec["conteudo"].split("\n")
        paragrafo: list[str] = []
        for linha in linhas:
            if linha.startswith("- "):
                if paragrafo:
                    blocos.append(render.Paragrafo("\n".join(paragrafo)))
                    paragrafo = []
                blocos.append(render.Lista([linha[2:]]))
            else:
                paragrafo.append(linha)
        if paragrafo:
            blocos.append(render.Paragrafo("\n".join(paragrafo)))
    local = conteudo.get("local") or ""
    data_emissao = date.fromisoformat(conteudo["data_emissao"])
    blocos.append(render.Espaco())
    blocos.append(render.Paragrafo(f"{local + ', ' if local else ''}{data_extenso(data_emissao)}.", alinhamento="direita"))
    autor = conteudo["autor"]
    blocos.append(render.Assinatura(autor["nome"], autor["crp"], autor.get("titulacao") or ""))
    return render.Documento(
        blocos,
        cabecalho_alerta="" if final else "RASCUNHO — SEM VALIDADE COMO DOCUMENTO PSICOLÓGICO",
        rodape=conteudo["codigo"],
        controle=f"Controle de integridade (SHA-256): {conteudo['hash']}" if conteudo.get("hash") else "",
        metadados={"titulo": f"{conteudo['titulo']} {conteudo['codigo']}"},
    )


def gerar_docx(conteudo: dict, *, final: bool, nome_pessoa: str = "") -> bytes:
    return render.para_docx(documento_psicologico(conteudo, final=final), nome_pessoa)


def gerar_pdf(conteudo: dict, *, final: bool, nome_pessoa: str = "") -> bytes:
    return render.para_pdf(documento_psicologico(conteudo, final=final), nome_pessoa)
