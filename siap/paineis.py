"""Painéis: agregações para visualização. Somente contagens e valores TRANSCRITOS — nada é calculado
a partir de normas (CLAUDE.md, regra 5). Percentis só entram nos gráficos quando o texto registrado é
um número simples entre 0 e 100.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import avaliacoes as av
from . import documentos as dc
from .catalogo import hoje, listar_catalogo
from .models import AplicacaoInstrumento, Avaliacao, DocumentoPsicologico

_NUM = re.compile(r"^\s*[Pp]?\s*(\d{1,3}(?:[.,]\d+)?)\s*$")


def percentil_numerico(texto: str | None) -> float | None:
    """'55' → 55.0; '55,5' → 55.5; 'P75' → 75.0; faixas ('50-75'), textos e valores fora de 0–100 → None."""
    m = _NUM.match(texto or "")
    if not m:
        return None
    valor = float(m.group(1).replace(",", "."))
    return valor if 0 <= valor <= 100 else None


def _contagem(itens) -> list[dict]:
    return [{"categoria": k, "quantidade": v} for k, v in Counter(itens).most_common()]


@dataclass(frozen=True)
class VisaoGeral:
    total_avaliacoes: int
    em_andamento: int
    concluidas: int
    documentos_emitidos: int
    versoes_elegiveis: int
    versoes_bloqueadas: int
    por_finalidade: list[dict]
    por_status: list[dict]
    por_mes: list[dict]
    instrumentos_mais_usados: list[dict]
    documentos_por_tipo: list[dict]
    motivos_bloqueio: list[dict]
    vencimentos: list[dict]


def _meses(referencia: date, quantidade: int = 12) -> list[str]:
    ano, mes, saida = referencia.year, referencia.month, []
    for _ in range(quantidade):
        saida.append(f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return list(reversed(saida))


def visao_geral(s: Session, referencia: date | None = None) -> VisaoGeral:
    referencia = referencia or hoje()
    avaliacoes = list(s.scalars(select(Avaliacao).options(selectinload(Avaliacao.finalidade))))
    aplicacoes = list(s.scalars(select(AplicacaoInstrumento).options(selectinload(AplicacaoInstrumento.versao))))
    documentos = list(s.scalars(select(DocumentoPsicologico)))
    catalogo = listar_catalogo(s, referencia)

    inicios = Counter(f"{a.data_inicio:%Y-%m}" for a in avaliacoes)
    por_mes = [{"mes": m, "quantidade": inicios.get(m, 0)} for m in _meses(referencia)]

    limite = referencia + timedelta(days=60)
    vencimentos = sorted(
        ({"versao": f"{l.instrumento} — {l.versao}", "vence_em": l.situacao.vence_em}
         for l in catalogo if l.situacao.liberado and l.situacao.vence_em and l.situacao.vence_em <= limite),
        key=lambda d: d["vence_em"],
    )
    return VisaoGeral(
        total_avaliacoes=len(avaliacoes),
        em_andamento=sum(a.status == av.EM_ANDAMENTO for a in avaliacoes),
        concluidas=sum(a.status == av.CONCLUIDA for a in avaliacoes),
        documentos_emitidos=sum(d.status == dc.EMITIDO for d in documentos),
        versoes_elegiveis=sum(l.situacao.liberado for l in catalogo),
        versoes_bloqueadas=sum(not l.situacao.liberado for l in catalogo),
        por_finalidade=_contagem(a.finalidade.nome for a in avaliacoes),
        por_status=_contagem(av.STATUS[a.status] for a in avaliacoes),
        por_mes=por_mes,
        instrumentos_mais_usados=_contagem(ap.versao.rotulo for ap in aplicacoes)[:10],
        documentos_por_tipo=_contagem(dc.MODELOS[d.tipo].titulo for d in documentos),
        motivos_bloqueio=_contagem(
            ("Vencida" if l.situacao.vencida else l.situacao.rotulo) for l in catalogo if not l.situacao.liberado
        ),
        vencimentos=vencimentos,
    )


def resultados_da_avaliacao(s: Session, avaliacao_id: int) -> list[dict]:
    a = s.get(Avaliacao, avaliacao_id)
    if a is None:
        return []
    linhas = []
    for ap in a.aplicacoes:
        for r in ap.resultados:
            linhas.append({
                "instrumento": ap.versao.rotulo, "medida": r.medida, "rotulo": f"{ap.versao.instrumento.sigla or ap.versao.nome_versao} · {r.medida}",
                "percentil": percentil_numerico(r.percentil), "percentil_registrado": r.percentil,
                "classificacao": r.classificacao, "escore_bruto": r.escore_bruto, "referencia": r.referencia,
                "data": ap.data_aplicacao,
            })
    return linhas


def linha_do_tempo(s: Session, avaliacao_id: int) -> list[dict]:
    a = s.get(Avaliacao, avaliacao_id)
    if a is None:
        return []
    eventos = [{"data": a.data_inicio, "tipo": "Início", "descricao": a.finalidade.nome}]
    eventos += [{"data": r.data, "tipo": "Registro", "descricao": r.tipo} for r in a.registros]
    eventos += [{"data": ap.data_aplicacao, "tipo": "Instrumento", "descricao": ap.versao.rotulo} for ap in a.aplicacoes]
    if a.data_conclusao:
        eventos.append({"data": a.data_conclusao, "tipo": "Conclusão", "descricao": "Avaliação concluída"})
    ordem = {"Início": 0, "Registro": 1, "Instrumento": 2, "Conclusão": 3}
    return sorted(eventos, key=lambda e: (e["data"], ordem[e["tipo"]]))


def medidas_comparaveis(s: Session) -> list[tuple[str, str]]:
    """(rótulo da versão, medida) com ao menos 2 percentis numéricos em avaliações diferentes."""
    contagem: Counter = Counter()
    for ap in s.scalars(select(AplicacaoInstrumento).options(selectinload(AplicacaoInstrumento.resultados),
                                                              selectinload(AplicacaoInstrumento.versao))):
        for r in ap.resultados:
            if percentil_numerico(r.percentil) is not None:
                contagem[(ap.versao.rotulo, r.medida)] += 1
    return sorted(k for k, v in contagem.items() if v >= 2)


def comparativo(s: Session, versao_rotulo: str, medida: str) -> list[dict]:
    """Percentis transcritos de uma mesma medida em diferentes avaliações (identificadas só por código)."""
    linhas = []
    for ap in s.scalars(select(AplicacaoInstrumento).options(selectinload(AplicacaoInstrumento.resultados),
                                                              selectinload(AplicacaoInstrumento.versao),
                                                              selectinload(AplicacaoInstrumento.avaliacao))):
        if ap.versao.rotulo != versao_rotulo:
            continue
        for r in ap.resultados:
            p = percentil_numerico(r.percentil)
            if r.medida == medida and p is not None:
                linhas.append({"avaliacao": ap.avaliacao.codigo, "finalidade": ap.avaliacao.finalidade.nome,
                               "percentil": p, "classificacao": r.classificacao, "data": ap.data_aplicacao})
    return sorted(linhas, key=lambda d: d["avaliacao"])
