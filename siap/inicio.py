"""Dados da página inicial: saudação, primeiros passos, avisos e atividade recente."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import avaliacoes as av
from . import documentos as dc
from .catalogo import hoje, listar_auditoria, listar_catalogo
from .models import DocumentoPsicologico, RegistroAuditoria


@dataclass(frozen=True)
class Passo:
    titulo: str
    descricao: str
    feito: bool
    pagina: str
    opcional: bool = False


@dataclass(frozen=True)
class Aviso:
    nivel: str  # "erro" | "atencao" | "info"
    texto: str
    pagina: str


@dataclass(frozen=True)
class Atividade:
    quando: datetime
    icone: str
    texto: str


@dataclass(frozen=True)
class ResumoInicio:
    nome: str
    avaliacoes_andamento: int
    documentos_pendentes: int
    versoes_elegiveis: int
    versoes_total: int
    passos: list[Passo]
    avisos: list[Aviso]
    atividades: list[Atividade]

    @property
    def progresso(self) -> float:
        obrigatorios = [p for p in self.passos if not p.opcional]
        return sum(p.feito for p in obrigatorios) / len(obrigatorios)


_ATIVIDADES = {
    "criar_avaliacao": ("🗂️", "Avaliação {codigo} criada ({finalidade})"),
    "alterar_status_avaliacao": ("🔁", "Situação de avaliação alterada para {para}"),
    "criar_registro_avaliacao": ("💬", "{tipo} registrada em {avaliacao}"),
    "registrar_aplicacao": ("🧪", "{versao} aplicado em {avaliacao}"),
    "registrar_resultado": ("📈", "Resultado registrado ({medida})"),
    "registrar_verificacao_satepsi": ("✅", "Verificação SATEPSI: {versao}"),
    "criar_documento": ("📝", "Rascunho {codigo} criado"),
    "documento_aprovado": ("👍", "Documento {codigo} aprovado"),
    "documento_emitido": ("📄", "Documento {codigo} emitido"),
    "criar_instrumento": ("📚", "Teste cadastrado: {nome}"),
    "criar_finalidade": ("🎯", "Finalidade incluída: {nome}"),
    "codificar_trecho": ("🧩", "Trecho codificado ({codigo})"),
    "importar_conjunto_dados": ("📐", "Conjunto de pesquisa importado: {nome}"),
    "exportar_backup": ("💾", "Backup exportado"),
    "consulta_ia": ("✨", "Consulta ao Consultor IA"),
}


def _texto_atividade(registro: RegistroAuditoria) -> Atividade | None:
    modelo = _ATIVIDADES.get(registro.acao)
    if modelo is None:
        return None
    try:
        dados = json.loads(registro.detalhes or "{}")
    except ValueError:
        dados = {}
    icone, texto = modelo
    try:
        texto = texto.format_map(_Padrao(dados))
    except (KeyError, ValueError, IndexError):
        pass
    return Atividade(registro.quando, icone, texto)


class _Padrao(dict):
    def __missing__(self, chave):
        return "—"


def resumo(s: Session, referencia: date | None = None) -> ResumoInicio:
    referencia = referencia or hoje()
    perfil = dc.obter_perfil(s)
    catalogo = listar_catalogo(s, referencia)
    avaliacoes = av.listar_avaliacoes(s)
    documentos = list(s.scalars(select(DocumentoPsicologico)))
    acoes = set(s.scalars(select(RegistroAuditoria.acao).distinct()))

    elegiveis = [l for l in catalogo if l.situacao.liberado]
    passos = [
        Passo("Preencha seus dados profissionais", "Nome e CRP aparecem na assinatura dos documentos.",
              bool(perfil.nome and perfil.crp), "paginas/documentos.py"),
        Passo("Verifique no SATEPSI os testes que você usa", "Só testes verificados podem ser aplicados.",
              bool(elegiveis), "paginas/verificacao_satepsi.py"),
        Passo("Crie sua primeira avaliação", "Identificada só por código, sem nome da pessoa.",
              bool(avaliacoes), "paginas/avaliacoes.py"),
        Passo("Emita seu primeiro documento", "Laudo, atestado, relatório, parecer ou declaração.",
              any(d.status == dc.EMITIDO for d in documentos), "paginas/documentos.py"),
        Passo("Faça um backup", "Guarde a cópia em local protegido.", "exportar_backup" in acoes,
              "paginas/auditoria_backup.py"),
        Passo("Ative o Consultor IA", "Opcional: sugestões de redação e metodologia.", perfil.ia_habilitada,
              "paginas/consultor_ia.py", opcional=True),
    ]

    avisos: list[Aviso] = []
    for alerta in av.alertas_conformidade(s, referencia):
        avisos.append(Aviso("erro", f"{alerta.codigo}: {alerta.versao} deixou de estar elegível.",
                            "paginas/avaliacoes.py"))
    limite = referencia + timedelta(days=15)
    for l in elegiveis:
        if l.situacao.vence_em and l.situacao.vence_em <= limite:
            avisos.append(Aviso("atencao", f"Verificação SATEPSI de {l.instrumento} — {l.versao} vence em "
                                           f"{l.situacao.vence_em:%d/%m}.", "paginas/verificacao_satepsi.py"))
    aprovados = [d for d in documentos if d.status == dc.APROVADO]
    if aprovados:
        avisos.append(Aviso("info", f"{len(aprovados)} documento(s) aprovado(s) aguardando emissão.",
                            "paginas/documentos.py"))
    rascunhos = [d for d in documentos if d.status in (dc.RASCUNHO, dc.REVISADO)]
    if rascunhos:
        avisos.append(Aviso("info", f"{len(rascunhos)} documento(s) em elaboração.", "paginas/documentos.py"))

    atividades = [a for a in (_texto_atividade(r) for r in listar_auditoria(s, limite=60)) if a][:8]
    return ResumoInicio(
        nome=perfil.nome,
        avaliacoes_andamento=sum(a.status == av.EM_ANDAMENTO for a in avaliacoes),
        documentos_pendentes=len(aprovados) + len(rascunhos),
        versoes_elegiveis=len(elegiveis),
        versoes_total=len(catalogo),
        passos=passos, avisos=avisos, atividades=atividades,
    )
