"""Registro documental da avaliação: reúne num único arquivo (Word/PDF) tudo o que foi registrado no
processo — identificação codificada, demanda, entrevistas e observações, instrumentos e resultados
transcritos, análise qualitativa, documentos produzidos (com o texto emitido) e o histórico da auditoria.

Serve à guarda documental pelo prazo exigido pelo CFP (confira a resolução vigente). O nome da pessoa
avaliada segue a regra 4 do CLAUDE.md: marcador no conteúdo, nome só no arquivo gerado.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import avaliacoes as av
from . import documentos as dc
from . import render
from .catalogo import FUSO, ErroValidacao, auditar
from .models import Avaliacao, Codificacao, RegistroAuditoria, RegistroAvaliacao
from .satepsi import ROTULOS

ACOES = {
    "criar_avaliacao": "Avaliação criada", "editar_avaliacao": "Dados da avaliação editados",
    "alterar_status_avaliacao": "Situação da avaliação alterada", "criar_registro_avaliacao": "Registro incluído",
    "editar_registro_avaliacao": "Registro editado", "registrar_aplicacao": "Instrumento registrado",
    "registrar_resultado": "Resultado registrado", "editar_resultado": "Resultado corrigido",
    "criar_documento": "Documento criado (rascunho)", "editar_secao_documento": "Texto de documento editado",
    "documento_volta_a_rascunho": "Documento voltou a rascunho", "documento_revisado": "Documento revisado",
    "documento_aprovado": "Documento aprovado", "documento_emitido": "Documento emitido",
    "retificar_documento": "Documento retificado", "codificar_trecho": "Trecho codificado (qualitativa)",
    "remover_codificacao": "Codificação removida", "exportar_registro_documental": "Registro documental exportado",
}

AVISO_GUARDA = (
    "Este registro reúne as informações do processo de avaliação mantidas no SIAP-IA. Guarde-o em local "
    "seguro pelo prazo mínimo exigido pelas normas do Conselho Federal de Psicologia (confira a resolução "
    "vigente), junto com os protocolos e materiais físicos do processo, que não estão no sistema."
)


def _br(valor) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, datetime):
        return valor.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")


def montar(s: Session, avaliacao_id: int) -> render.Documento:
    a = s.get(Avaliacao, avaliacao_id)
    if a is None:
        raise ErroValidacao("Avaliação não encontrada.")
    perfil = dc.obter_perfil(s)
    agora = datetime.now(FUSO)
    b: list = [render.Titulo("Registro documental da avaliação psicológica"),
               render.Paragrafo(f"{a.codigo} · gerado em {agora:%d/%m/%Y %H:%M}", alinhamento="centro", italico=True)]

    b.append(render.Secao("1. Identificação do processo"))
    perfil_txt = f"{a.faixa_etaria}" + (f", {a.idade} anos" if a.idade is not None else "")
    b.append(render.Tabela(["Campo", "Informação"], [
        ["Código interno", a.codigo],
        ["Pessoa avaliada", dc.TOKEN_NOME],
        ["Finalidade", a.finalidade.nome],
        ["Faixa etária / idade", perfil_txt],
        ["Escolaridade", a.escolaridade or "Não informada"],
        ["Contexto / solicitante", a.contexto or "—"],
        ["Situação", av.STATUS[a.status]],
        ["Início / conclusão", f"{_br(a.data_inicio)} / {_br(a.data_conclusao)}"],
        ["Profissional responsável", f"{perfil.nome or '—'} — CRP {perfil.crp or '—'}"],
    ], esquerda=True))

    b.append(render.Secao("2. Demanda e objetivos"))
    b.append(render.Paragrafo(a.demanda or "Não registrada."))

    b.append(render.Secao("3. Entrevistas, observações e demais registros"))
    if not a.registros:
        b.append(render.Paragrafo("Nenhum registro."))
    for r in a.registros:
        b.append(render.Subsecao(f"{_br(r.data)} — {r.tipo}" + (f" (editado em {_br(r.editado_em)})" if r.editado_em else "")))
        b.append(render.Paragrafo(r.conteudo))

    b.append(render.Secao("4. Instrumentos aplicados e resultados"))
    if not a.aplicacoes:
        b.append(render.Paragrafo("Nenhum instrumento registrado."))
    else:
        b.append(render.Tabela(
            ["Instrumento / versão", "Data", "Modalidade", "SATEPSI no registro"],
            [[ap.versao.rotulo, _br(ap.data_aplicacao), ap.modalidade,
              ROTULOS.get(ap.satepsi_status_no_registro, ap.satepsi_status_no_registro)] for ap in a.aplicacoes],
            nota="Situação SATEPSI fotografada no momento em que a aplicação foi registrada no sistema.",
        ))
        for ap in a.aplicacoes:
            b.append(render.Subsecao(ap.versao.rotulo))
            if ap.observacoes:
                b.append(render.Paragrafo(f"Observações da aplicação: {ap.observacoes}"))
            if ap.resultados:
                b.append(render.Tabela(
                    ["Medida", "Bruto", "Padronizado", "Percentil", "Classificação", "Referência"],
                    [[r.medida, r.escore_bruto or "—", r.escore_padrao or "—", r.percentil or "—",
                      r.classificacao or "—", r.referencia] for r in ap.resultados],
                    nota="Valores transcritos do manual ou da plataforma oficial do instrumento; não calculados pelo sistema.",
                ))
            else:
                b.append(render.Paragrafo("Sem resultados registrados."))

    codificacoes = list(s.scalars(select(Codificacao).join(RegistroAvaliacao)
                                  .where(RegistroAvaliacao.avaliacao_id == avaliacao_id)))
    if codificacoes:
        b.append(render.Secao("5. Análise qualitativa"))
        por_codigo: dict[str, list[str]] = {}
        for c in codificacoes:
            por_codigo.setdefault(c.codigo.nome, []).append(c.trecho)
        b.append(render.Tabela(["Código", "Trechos"], [[k, str(len(v))] for k, v in sorted(por_codigo.items())]))
        for codigo, trechos in sorted(por_codigo.items()):
            b.append(render.Subsecao(codigo))
            b.append(render.Lista([f"“{t}”" for t in trechos]))

    n = 6 if codificacoes else 5
    documentos = dc.listar_documentos(s, avaliacao_id)
    b.append(render.Secao(f"{n}. Documentos produzidos"))
    if not documentos:
        b.append(render.Paragrafo("Nenhum documento."))
    else:
        b.append(render.Tabela(
            ["Código", "Tipo", "Situação", "Emissão", "Integridade (SHA-256)"],
            [[d.codigo, d.titulo, dc.STATUS[d.status], _br(d.data_emissao),
              (d.hash_conteudo[:16] + "…") if d.hash_conteudo else "—"] for d in reversed(documentos)],
        ))
        for d in reversed(documentos):
            if d.status != dc.EMITIDO:
                continue
            emitido = json.loads(d.conteudo_emitido)
            b.append(render.Subsecao(f"Texto emitido — {d.codigo} ({_br(d.data_emissao)})"))
            for sec in emitido["secoes"]:
                b.append(render.Paragrafo(sec["titulo"], negrito=True, alinhamento="esquerda"))
                b.append(render.Paragrafo(sec["conteudo"]))

    b.append(render.Secao(f"{n + 1}. Histórico do processo (auditoria)"))
    eventos = list(s.scalars(
        select(RegistroAuditoria).where(or_(
            (RegistroAuditoria.entidade == "avaliacao") & (RegistroAuditoria.entidade_id == avaliacao_id),
            RegistroAuditoria.detalhes.like(f"%{a.codigo}%"),
        )).order_by(RegistroAuditoria.id)
    ))
    b.append(render.Tabela(["Quando", "Ação"], [[_br(e.quando), ACOES.get(e.acao, e.acao.replace("_", " "))]
                                                for e in eventos] or [["—", "Sem eventos"]], esquerda=True))

    b.append(render.Espaco())
    b.append(render.Paragrafo(AVISO_GUARDA, italico=True, tamanho=10))
    if perfil.nome and perfil.crp:
        b.append(render.Assinatura(perfil.nome, perfil.crp, perfil.titulacao))

    textos = json.dumps([getattr(x, "texto", None) or getattr(x, "linhas", None) or getattr(x, "itens", None)
                         for x in b if not isinstance(x, render.Paragrafo) or "gerado em" not in x.texto],
                        ensure_ascii=False, default=str)
    resumo_hash = hashlib.sha256(textos.encode("utf-8")).hexdigest()
    return render.Documento(
        b, rodape=f"Registro documental {a.codigo}", controle=f"Resumo de integridade (SHA-256): {resumo_hash}",
        tamanho_fonte=11, entrelinha=1.3, metadados={"titulo": f"Registro documental {a.codigo}", "hash": resumo_hash},
    )


def registrar_exportacao(s: Session, avaliacao_id: int, formato: str) -> None:
    a = s.get(Avaliacao, avaliacao_id)
    if a is not None:
        auditar(s, "exportar_registro_documental", "avaliacao", avaliacao_id, codigo=a.codigo, formato=formato)
