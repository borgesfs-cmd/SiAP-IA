"""Finalidades de avaliação: padrões do sistema + cadastradas manualmente pelo usuário."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalogo import ErroValidacao, _txt, auditar
from .models import Finalidade

FINALIDADES_PADRAO: tuple[tuple[str, str], ...] = (
    ("Psicodiagnóstico", "Avaliação clínica para compreensão diagnóstica (criança, adolescente, adulto ou idoso)."),
    ("Avaliação neuropsicológica", "Investigação de funções cognitivas e comportamentais e suas relações cerebrais."),
    ("Trânsito (CNH)", "Avaliação psicológica para obtenção, renovação ou mudança de categoria da CNH."),
    ("Porte/posse de arma de fogo", "Avaliação de aptidão psicológica para manuseio de arma de fogo."),
    ("Seleção de pessoal", "Avaliação para processos seletivos."),
    ("Treinamento e desenvolvimento de pessoal", "Avaliação para desenvolvimento, treinamento e acompanhamento."),
    ("Pesquisa", "Uso em estudos científicos (dados anonimizados)."),
)


def carregar_finalidades_padrao(s: Session) -> int:
    """Insere as finalidades padrão que ainda não existem (idempotente). Retorna quantas foram criadas."""
    existentes = {n.lower() for n in s.scalars(select(Finalidade.nome))}
    criadas = 0
    for nome, descricao in FINALIDADES_PADRAO:
        if nome.lower() not in existentes:
            s.add(Finalidade(nome=nome, descricao=descricao, padrao=True, ativa=True))
            criadas += 1
    if criadas:
        s.flush()
        auditar(s, "carregar_finalidades_padrao", "sistema", None, quantidade=criadas)
    return criadas


def _nome_em_uso(s: Session, nome: str, exceto_id: int | None = None) -> bool:
    consulta = select(Finalidade.id).where(func.lower(Finalidade.nome) == nome.lower())
    if exceto_id is not None:
        consulta = consulta.where(Finalidade.id != exceto_id)
    return s.scalar(consulta) is not None


def criar_finalidade(s: Session, *, nome: str, descricao: str = "") -> Finalidade:
    nome = _txt(nome)
    if not nome:
        raise ErroValidacao("Informe o nome da finalidade.")
    if len(nome) > 120:
        raise ErroValidacao("Nome da finalidade muito longo (máximo 120 caracteres).")
    if _nome_em_uso(s, nome):
        raise ErroValidacao(f"A finalidade {nome!r} já existe.")
    finalidade = Finalidade(nome=nome, descricao=_txt(descricao), padrao=False, ativa=True)
    s.add(finalidade)
    s.flush()
    auditar(s, "criar_finalidade", "finalidade", finalidade.id, nome=nome)
    return finalidade


def atualizar_finalidade(s: Session, finalidade_id: int, *, nome: str, descricao: str) -> Finalidade:
    finalidade = s.get(Finalidade, finalidade_id)
    if finalidade is None:
        raise ErroValidacao("Finalidade não encontrada.")
    nome, descricao = _txt(nome), _txt(descricao)
    if not nome:
        raise ErroValidacao("O nome não pode ficar vazio.")
    if _nome_em_uso(s, nome, exceto_id=finalidade_id):
        raise ErroValidacao(f"A finalidade {nome!r} já existe.")
    antes = {"nome": finalidade.nome, "descricao": finalidade.descricao}
    if antes != {"nome": nome, "descricao": descricao}:
        finalidade.nome, finalidade.descricao = nome, descricao
        auditar(s, "editar_finalidade", "finalidade", finalidade_id, antes=antes,
                depois={"nome": nome, "descricao": descricao})
    return finalidade


def definir_ativa(s: Session, finalidade_id: int, ativa: bool) -> Finalidade:
    """Finalidades não são apagadas (há avaliações e verificações ligadas a elas): só desativadas."""
    finalidade = s.get(Finalidade, finalidade_id)
    if finalidade is None:
        raise ErroValidacao("Finalidade não encontrada.")
    if finalidade.ativa != ativa:
        finalidade.ativa = ativa
        auditar(s, "ativar_finalidade" if ativa else "desativar_finalidade", "finalidade", finalidade_id,
                nome=finalidade.nome)
    return finalidade


def listar_finalidades(s: Session, somente_ativas: bool = False) -> list[Finalidade]:
    consulta = select(Finalidade).order_by(Finalidade.padrao.desc(), Finalidade.id)
    if somente_ativas:
        consulta = consulta.where(Finalidade.ativa.is_(True))
    return list(s.scalars(consulta))
