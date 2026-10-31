"""Análise qualitativa: livro de códigos, codificação de trechos literais e matriz código × registro."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import avaliacoes as av
from .catalogo import ErroValidacao, _txt, auditar
from .models import Avaliacao, Codificacao, CodigoQualitativo, RegistroAvaliacao


def _norm(texto: str) -> str:
    return " ".join((texto or "").split())


def listar_codigos(s: Session, somente_ativos: bool = False) -> list[CodigoQualitativo]:
    consulta = select(CodigoQualitativo).order_by(CodigoQualitativo.nome)
    if somente_ativos:
        consulta = consulta.where(CodigoQualitativo.ativo.is_(True))
    return list(s.scalars(consulta))


def obter_ou_criar_codigo(s: Session, nome: str, descricao: str = "") -> CodigoQualitativo:
    nome = _txt(nome)
    if not nome:
        raise ErroValidacao("Informe o nome do código.")
    if len(nome) > 120:
        raise ErroValidacao("Nome do código muito longo (máximo 120 caracteres).")
    av.verificar_sem_identificadores(nome, descricao)
    existente = s.scalar(select(CodigoQualitativo).where(func.lower(CodigoQualitativo.nome) == nome.lower()))
    if existente:
        if not existente.ativo:
            existente.ativo = True
            auditar(s, "reativar_codigo_qualitativo", "codigo_qualitativo", existente.id, nome=existente.nome)
        return existente
    codigo = CodigoQualitativo(nome=nome, descricao=_txt(descricao))
    s.add(codigo)
    s.flush()
    auditar(s, "criar_codigo_qualitativo", "codigo_qualitativo", codigo.id, nome=nome)
    return codigo


def editar_codigo(s: Session, codigo_id: int, *, nome: str, descricao: str, ativo: bool) -> CodigoQualitativo:
    codigo = s.get(CodigoQualitativo, codigo_id)
    if codigo is None:
        raise ErroValidacao("Código não encontrado.")
    nome = _txt(nome)
    if not nome:
        raise ErroValidacao("O nome não pode ficar vazio.")
    outro = s.scalar(select(CodigoQualitativo.id).where(func.lower(CodigoQualitativo.nome) == nome.lower(),
                                                         CodigoQualitativo.id != codigo_id))
    if outro:
        raise ErroValidacao(f"Já existe um código chamado {nome!r}.")
    av.verificar_sem_identificadores(nome, descricao)
    codigo.nome, codigo.descricao, codigo.ativo = nome, _txt(descricao), ativo
    auditar(s, "editar_codigo_qualitativo", "codigo_qualitativo", codigo_id, nome=nome, ativo=ativo)
    return codigo


def codificar(s: Session, *, registro_id: int, codigo_id: int, trecho: str, comentario: str = "",
              origem: str = "manual") -> Codificacao:
    registro = s.get(RegistroAvaliacao, registro_id)
    if registro is None:
        raise ErroValidacao("Registro não encontrado.")
    if registro.avaliacao.status == av.CANCELADA:
        raise ErroValidacao("Avaliação cancelada.")
    codigo = s.get(CodigoQualitativo, codigo_id)
    if codigo is None or not codigo.ativo:
        raise ErroValidacao("Código inexistente ou desativado.")
    trecho = _txt(trecho)
    if not trecho:
        raise ErroValidacao("Cole o trecho a codificar.")
    if _norm(trecho) not in _norm(registro.conteudo):
        raise ErroValidacao("O trecho precisa ser cópia literal do registro selecionado.")
    if origem not in ("manual", "ia_aceita"):
        raise ErroValidacao("Origem inválida.")
    comentario = _txt(comentario)
    av.verificar_sem_identificadores(comentario)
    duplicada = s.scalar(select(Codificacao.id).where(Codificacao.registro_id == registro_id,
                                                      Codificacao.codigo_id == codigo_id,
                                                      Codificacao.trecho == trecho))
    if duplicada:
        raise ErroValidacao("Este trecho já está codificado com este código.")
    item = Codificacao(registro=registro, codigo=codigo, trecho=trecho, comentario=comentario, origem=origem)
    s.add(item)
    s.flush()
    auditar(s, "codificar_trecho", "codificacao", item.id, avaliacao=registro.avaliacao.codigo,
            codigo=codigo.nome, origem=origem)
    return item


def remover_codificacao(s: Session, codificacao_id: int) -> None:
    item = s.get(Codificacao, codificacao_id)
    if item is None:
        raise ErroValidacao("Codificação não encontrada.")
    auditar(s, "remover_codificacao", "codificacao", codificacao_id, codigo=item.codigo.nome,
            registro_id=item.registro_id)
    s.delete(item)


def codificacoes_da_avaliacao(s: Session, avaliacao_id: int) -> list[Codificacao]:
    return list(s.scalars(
        select(Codificacao).join(RegistroAvaliacao)
        .options(selectinload(Codificacao.codigo), selectinload(Codificacao.registro))
        .where(RegistroAvaliacao.avaliacao_id == avaliacao_id)
        .order_by(Codificacao.codigo_id, Codificacao.id)
    ))


@dataclass(frozen=True)
class Matriz:
    codigos: list[str]
    registros: list[str]
    contagens: dict[tuple[str, str], int]

    def total_codigo(self, codigo: str) -> int:
        return sum(v for (c, _), v in self.contagens.items() if c == codigo)


def matriz(s: Session, avaliacao_id: int) -> Matriz:
    a = s.get(Avaliacao, avaliacao_id)
    if a is None:
        raise ErroValidacao("Avaliação não encontrada.")
    rotulos = {r.id: f"{r.data:%d/%m} · {r.tipo} (#{r.id})" for r in a.registros}
    contagens: dict[tuple[str, str], int] = defaultdict(int)
    codigos = []
    for c in codificacoes_da_avaliacao(s, avaliacao_id):
        if c.codigo.nome not in codigos:
            codigos.append(c.codigo.nome)
        contagens[(c.codigo.nome, rotulos[c.registro_id])] += 1
    return Matriz(sorted(codigos), list(rotulos.values()), dict(contagens))
