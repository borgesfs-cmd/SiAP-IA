"""Regra de conformidade SATEPSI.

Este é o ÚNICO lugar que decide se uma versão de instrumento está elegível a uso
profissional (aplicação/correção). Nenhuma tela ou módulo pode contornar `avaliar`.

Política (Documento Mestre, seção 6):
- Sem verificação registrada ............ bloqueado ("não verificado")
- Última verificação desfavorável ....... bloqueado
- Restrito / em avaliação / não localizado bloqueado (preventivo)
- Favorável, mas verificação vencida .... bloqueado até nova consulta
- Favorável e dentro da validade ........ elegível (respeitadas as condições registradas)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

FAVORAVEL = "favoravel"
DESFAVORAVEL = "desfavoravel"
RESTRITO = "restrito"
EM_AVALIACAO = "em_avaliacao"
NAO_LOCALIZADO = "nao_localizado"
NAO_VERIFICADO = "nao_verificado"  # derivado: nunca é gravado no banco

STATUS_REGISTRAVEIS = (FAVORAVEL, DESFAVORAVEL, RESTRITO, EM_AVALIACAO, NAO_LOCALIZADO)

ROTULOS = {
    FAVORAVEL: "Favorável",
    DESFAVORAVEL: "Desfavorável",
    RESTRITO: "Restrito / com condições",
    EM_AVALIACAO: "Em avaliação",
    NAO_LOCALIZADO: "Não localizado",
    NAO_VERIFICADO: "Não verificado",
}

VALIDADE_PADRAO_DIAS = 90
VALIDADE_MAXIMA_DIAS = 365
FONTE_PADRAO = "SATEPSI — https://satepsi.cfp.org.br/"

_MOTIVOS_BLOQUEIO = {
    DESFAVORAVEL: "Última consulta ao SATEPSI indicou parecer desfavorável.",
    RESTRITO: "Situação com restrições/condições: bloqueado preventivamente até análise profissional.",
    EM_AVALIACAO: "Instrumento em avaliação no SATEPSI: bloqueado preventivamente.",
    NAO_LOCALIZADO: "Versão não localizada no SATEPSI: bloqueado preventivamente.",
}


class VerificacaoLike(Protocol):
    id: int | None
    status: str
    data_consulta: date
    validade_dias: int
    condicoes: str


@dataclass(frozen=True)
class Situacao:
    status: str
    liberado: bool
    motivo: str
    data_consulta: date | None = None
    vence_em: date | None = None
    vencida: bool = False
    condicoes: str = ""

    @property
    def rotulo(self) -> str:
        return ROTULOS[self.status]

    @property
    def rotulo_uso(self) -> str:
        return "Elegível" if self.liberado else "Bloqueado"


def verificacao_vigente(verificacoes: Iterable[VerificacaoLike]) -> VerificacaoLike | None:
    """A verificação que vale é a de data de consulta mais recente; empate → a registrada por último."""
    lista = list(verificacoes)
    if not lista:
        return None
    return max(lista, key=lambda v: (v.data_consulta, v.id or 0))


def avaliar(verificacoes: Iterable[VerificacaoLike], hoje: date) -> Situacao:
    v = verificacao_vigente(verificacoes)
    if v is None:
        return Situacao(
            status=NAO_VERIFICADO,
            liberado=False,
            motivo="Nenhuma verificação no SATEPSI registrada para esta versão.",
        )

    vence_em = v.data_consulta + timedelta(days=v.validade_dias)
    base = dict(data_consulta=v.data_consulta, vence_em=vence_em, condicoes=v.condicoes or "")

    if v.data_consulta > hoje:
        return Situacao(status=v.status, liberado=False,
                        motivo="Data de consulta no futuro: registro inconsistente.", **base)

    if v.status != FAVORAVEL:
        motivo = _MOTIVOS_BLOQUEIO.get(v.status, "Situação desconhecida: bloqueado preventivamente.")
        status = v.status if v.status in ROTULOS else NAO_VERIFICADO
        return Situacao(status=status, liberado=False, motivo=motivo, **base)

    if hoje > vence_em:
        return Situacao(
            status=FAVORAVEL, liberado=False, vencida=True,
            motivo=f"Verificação vencida em {vence_em:%d/%m/%Y}: consulte novamente o SATEPSI.",
            **base,
        )

    motivo = f"Favorável na consulta de {v.data_consulta:%d/%m/%Y}; válida até {vence_em:%d/%m/%Y}."
    if v.condicoes:
        motivo += " Observe as condições registradas."
    return Situacao(status=FAVORAVEL, liberado=True, motivo=motivo, **base)
