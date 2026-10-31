"""Serviços do catálogo (Biblioteca Dinâmica) e do Monitor SATEPSI.

Toda alteração passa por aqui e gera registro de auditoria na mesma transação.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, undefer

from . import satepsi
from .models import (
    Base,
    Finalidade,
    Instrumento,
    RegistroAuditoria,
    VerificacaoSATEPSI,
    VersaoInstrumento,
)

FUSO = ZoneInfo("America/Sao_Paulo")

CATEGORIAS = (
    "Personalidade / expressivos",
    "Atenção",
    "Inteligência / raciocínio",
    "Memória",
    "Outros",
)

EVIDENCIA_TAMANHO_MAX = 5 * 1024 * 1024
EVIDENCIA_TIPOS = {"image/png", "image/jpeg", "application/pdf"}

CAMPOS_EDITAVEIS = ("nome", "sigla", "categoria", "construto", "descricao", "observacoes")


class ErroValidacao(ValueError):
    """Dado inválido informado pelo usuário (mensagem pronta para exibir)."""


def hoje() -> date:
    return datetime.now(FUSO).date()


def _txt(valor: str | None) -> str:
    return (valor or "").strip()


def auditar(s: Session, acao: str, entidade: str, entidade_id: int | None, **detalhes) -> None:
    s.add(RegistroAuditoria(
        acao=acao, entidade=entidade, entidade_id=entidade_id,
        detalhes=json.dumps(detalhes, ensure_ascii=False, default=str),
    ))


# ---------------------------------------------------------------- instrumentos

def _validar_categoria(categoria: str) -> str:
    categoria = _txt(categoria)
    if categoria not in CATEGORIAS:
        raise ErroValidacao(f"Categoria inválida: {categoria!r}.")
    return categoria


def _nome_em_uso(s: Session, nome: str, exceto_id: int | None = None) -> bool:
    consulta = select(Instrumento.id).where(func.lower(Instrumento.nome) == nome.lower())
    if exceto_id is not None:
        consulta = consulta.where(Instrumento.id != exceto_id)
    return s.scalar(consulta) is not None


def criar_instrumento(
    s: Session, *, nome: str, categoria: str, sigla: str = "", construto: str = "",
    descricao: str = "", observacoes: str = "", versoes: list[str] | None = None,
) -> Instrumento:
    nome = _txt(nome)
    if not nome:
        raise ErroValidacao("Informe o nome do teste.")
    if _nome_em_uso(s, nome):
        raise ErroValidacao(f"Já existe um teste chamado {nome!r} no catálogo.")
    instrumento = Instrumento(
        nome=nome, sigla=_txt(sigla), categoria=_validar_categoria(categoria),
        construto=_txt(construto), descricao=_txt(descricao), observacoes=_txt(observacoes),
    )
    s.add(instrumento)
    s.flush()
    auditar(s, "criar_instrumento", "instrumento", instrumento.id, nome=nome, categoria=categoria)

    nomes_versao = [_txt(v) for v in (versoes or []) if _txt(v)] or [instrumento.sigla or "Versão única"]
    vistos: set[str] = set()
    for nv in nomes_versao:
        if nv.lower() in vistos:
            continue
        vistos.add(nv.lower())
        adicionar_versao(s, instrumento.id, nome_versao=nv)
    return instrumento


def atualizar_instrumento(s: Session, instrumento_id: int, **campos) -> Instrumento:
    instrumento = s.get(Instrumento, instrumento_id)
    if instrumento is None:
        raise ErroValidacao("Teste não encontrado.")
    antes, depois = {}, {}
    for campo, valor in campos.items():
        if campo not in CAMPOS_EDITAVEIS:
            raise ErroValidacao(f"Campo não editável: {campo}.")
        valor = _txt(valor)
        if campo == "nome":
            if not valor:
                raise ErroValidacao("O nome não pode ficar vazio.")
            if _nome_em_uso(s, valor, exceto_id=instrumento_id):
                raise ErroValidacao(f"Já existe um teste chamado {valor!r}.")
        if campo == "categoria":
            valor = _validar_categoria(valor)
        if getattr(instrumento, campo) != valor:
            antes[campo], depois[campo] = getattr(instrumento, campo), valor
            setattr(instrumento, campo, valor)
    if depois:
        auditar(s, "editar_instrumento", "instrumento", instrumento_id, antes=antes, depois=depois)
    return instrumento


def adicionar_versao(
    s: Session, instrumento_id: int, *, nome_versao: str, edicao: str = "",
    editora: str = "", populacao: str = "", observacoes: str = "",
) -> VersaoInstrumento:
    instrumento = s.get(Instrumento, instrumento_id)
    if instrumento is None:
        raise ErroValidacao("Teste não encontrado.")
    nome_versao = _txt(nome_versao)
    if not nome_versao:
        raise ErroValidacao("Informe o nome da versão.")
    existente = s.scalar(select(VersaoInstrumento.id).where(
        VersaoInstrumento.instrumento_id == instrumento_id,
        func.lower(VersaoInstrumento.nome_versao) == nome_versao.lower(),
    ))
    if existente is not None:
        raise ErroValidacao(f"O teste {instrumento.nome!r} já tem a versão {nome_versao!r}.")
    versao = VersaoInstrumento(
        instrumento_id=instrumento_id, nome_versao=nome_versao, edicao=_txt(edicao),
        editora=_txt(editora), populacao=_txt(populacao), observacoes=_txt(observacoes),
    )
    s.add(versao)
    s.flush()
    auditar(s, "criar_versao", "versao", versao.id, instrumento=instrumento.nome, versao=nome_versao)
    return versao


# ------------------------------------------------------------------- SATEPSI

def registrar_verificacao(
    s: Session, versao_id: int, *, status: str, data_consulta: date,
    fonte: str = satepsi.FONTE_PADRAO, validade_dias: int = satepsi.VALIDADE_PADRAO_DIAS,
    condicoes: str = "", observacoes: str = "", evidencia_nome: str | None = None,
    evidencia_tipo: str | None = None, evidencia: bytes | None = None,
    abrange_todas_finalidades: bool = True, finalidades_ids: list[int] | None = None,
    referencia: date | None = None,
) -> VerificacaoSATEPSI:
    """Registra uma nova consulta ao SATEPSI (nunca altera as anteriores).

    `abrange_todas_finalidades=False` restringe a validade às finalidades em `finalidades_ids`.
    """
    referencia = referencia or hoje()
    versao = s.get(VersaoInstrumento, versao_id)
    if versao is None:
        raise ErroValidacao("Versão não encontrada.")
    if status not in satepsi.STATUS_REGISTRAVEIS:
        raise ErroValidacao(f"Situação inválida: {status!r}.")
    if data_consulta > referencia:
        raise ErroValidacao("A data da consulta não pode estar no futuro.")
    if not 1 <= int(validade_dias) <= satepsi.VALIDADE_MAXIMA_DIAS:
        raise ErroValidacao(f"Validade deve ficar entre 1 e {satepsi.VALIDADE_MAXIMA_DIAS} dias.")
    fonte = _txt(fonte)
    if not fonte:
        raise ErroValidacao("Informe a fonte consultada.")

    sha = None
    if evidencia:
        if len(evidencia) > EVIDENCIA_TAMANHO_MAX:
            raise ErroValidacao("A evidência deve ter no máximo 5 MB.")
        if evidencia_tipo not in EVIDENCIA_TIPOS:
            raise ErroValidacao("Evidência deve ser PNG, JPG ou PDF.")
        sha = hashlib.sha256(evidencia).hexdigest()
    elif status == satepsi.FAVORAVEL:
        raise ErroValidacao(
            "Para registrar situação favorável, anexe a evidência da consulta "
            "(captura de tela ou PDF da página do SATEPSI)."
        )

    finalidades: list[Finalidade] = []
    if not abrange_todas_finalidades:
        ids = sorted(set(finalidades_ids or []))
        if not ids:
            raise ErroValidacao("Selecione ao menos uma finalidade ou marque “todas as finalidades”.")
        finalidades = list(s.scalars(select(Finalidade).where(Finalidade.id.in_(ids))))
        if len(finalidades) != len(ids):
            raise ErroValidacao("Finalidade inexistente na seleção.")

    verificacao = VerificacaoSATEPSI(
        versao=versao, status=status, data_consulta=data_consulta,
        validade_dias=int(validade_dias), fonte=fonte, condicoes=_txt(condicoes),
        observacoes=_txt(observacoes), evidencia_nome=evidencia_nome if evidencia else None,
        evidencia_tipo=evidencia_tipo if evidencia else None, evidencia_sha256=sha,
        evidencia=evidencia or None,
        abrange_todas_finalidades=abrange_todas_finalidades, finalidades=finalidades,
    )
    s.add(verificacao)
    s.flush()
    auditar(s, "registrar_verificacao_satepsi", "verificacao", verificacao.id,
            versao=versao.rotulo, status=status, data_consulta=data_consulta.isoformat(),
            validade_dias=int(validade_dias), evidencia_sha256=sha,
            finalidades="todas" if abrange_todas_finalidades else [f.nome for f in finalidades])
    return verificacao


def situacao_versao(
    versao: VersaoInstrumento, referencia: date | None = None, finalidade: Finalidade | None = None,
) -> satepsi.Situacao:
    return satepsi.avaliar(
        versao.verificacoes, referencia or hoje(),
        finalidade_id=finalidade.id if finalidade else None,
        finalidade_nome=finalidade.nome if finalidade else "",
    )


def pode_uso_profissional(
    s: Session, versao_id: int, referencia: date | None = None, finalidade_id: int | None = None,
) -> satepsi.Situacao:
    """PORTA ÚNICA de liberação para aplicação/correção profissional.

    Com `finalidade_id`, considera também as finalidades cobertas pela verificação vigente.
    """
    versao = s.get(VersaoInstrumento, versao_id)
    if versao is None:
        raise ErroValidacao("Versão não encontrada.")
    finalidade = s.get(Finalidade, finalidade_id) if finalidade_id is not None else None
    if finalidade_id is not None and finalidade is None:
        raise ErroValidacao("Finalidade não encontrada.")
    return situacao_versao(versao, referencia, finalidade)


# ------------------------------------------------------------------ consultas

@dataclass(frozen=True)
class LinhaCatalogo:
    instrumento_id: int
    versao_id: int
    instrumento: str
    sigla: str
    categoria: str
    construto: str
    versao: str
    editora: str
    situacao: satepsi.Situacao


def listar_catalogo(s: Session, referencia: date | None = None) -> list[LinhaCatalogo]:
    referencia = referencia or hoje()
    versoes = s.scalars(
        select(VersaoInstrumento)
        .options(selectinload(VersaoInstrumento.instrumento), selectinload(VersaoInstrumento.verificacoes))
        .join(Instrumento)
        .order_by(Instrumento.categoria, Instrumento.nome, VersaoInstrumento.nome_versao)
    ).all()
    return [
        LinhaCatalogo(
            instrumento_id=v.instrumento_id, versao_id=v.id, instrumento=v.instrumento.nome,
            sigla=v.instrumento.sigla, categoria=v.instrumento.categoria,
            construto=v.instrumento.construto, versao=v.nome_versao, editora=v.editora,
            situacao=situacao_versao(v, referencia),
        )
        for v in versoes
    ]


def listar_instrumentos(s: Session) -> list[Instrumento]:
    return list(s.scalars(select(Instrumento).order_by(Instrumento.nome)).all())


def listar_auditoria(s: Session, limite: int = 500) -> list[RegistroAuditoria]:
    return list(s.scalars(
        select(RegistroAuditoria).order_by(RegistroAuditoria.id.desc()).limit(limite)
    ).all())


def carregar_evidencia(s: Session, verificacao_id: int) -> VerificacaoSATEPSI | None:
    return s.scalar(
        select(VerificacaoSATEPSI).options(undefer(VerificacaoSATEPSI.evidencia))
        .where(VerificacaoSATEPSI.id == verificacao_id)
    )


# --------------------------------------------------------------------- backup

def exportar_backup(s: Session) -> dict:
    """Cópia integral em JSON de todas as tabelas (binários em base64). Guarde em local seguro."""
    dados: dict = {
        "formato": "siap-ia-backup",
        "versao_formato": 2,
        "gerado_em": datetime.now(FUSO).isoformat(),
    }
    for tabela in Base.metadata.sorted_tables:
        if tabela.name == "segredos_cifrados":  # chaves de API nunca vão para o backup
            continue
        linhas = []
        for registro in s.execute(select(tabela).order_by(*tabela.primary_key.columns)).mappings():
            linha = {}
            for coluna, valor in registro.items():
                if isinstance(valor, (bytes, bytearray, memoryview)):
                    linha[coluna] = {"base64": base64.b64encode(bytes(valor)).decode()}
                else:
                    linha[coluna] = valor
            linhas.append(linha)
        dados[tabela.name] = linhas
    auditar(s, "exportar_backup", "sistema", None, tabelas=len(dados) - 3)
    return json.loads(json.dumps(dados, ensure_ascii=False, default=str))
