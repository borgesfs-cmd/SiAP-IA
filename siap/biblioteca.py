"""Biblioteca de modelos e frases: textos da profissional, reutilizáveis nos documentos com um clique.

- Textos não podem conter identificadores (CPF, e-mail, telefone); podem conter o marcador de nome e
  trechos [[a completar]] — estes bloqueiam a aprovação do documento até serem preenchidos.
- Inserir um trecho usa `documentos.salvar_secoes`, então valem as mesmas regras (auditoria, documento
  emitido não muda, revisado/aprovado volta a rascunho).
- Nada de conteúdo protegido de manuais de testes (CLAUDE.md, regra 5).
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import avaliacoes as av
from . import documentos as dc
from .catalogo import ErroValidacao, _txt, auditar
from .models import SecaoDocumento, TrechoModelo, agora_utc

CATEGORIAS = ("Identificação", "Procedimento", "Descrição de instrumento", "Análise", "Conclusão",
              "Encaminhamento", "Referência", "Outro")
SECOES = {
    "qualquer": "Qualquer seção", "identificacao": "Identificação", "demanda": "Descrição da demanda",
    "procedimento": "Procedimento", "analise": "Análise", "conclusao": "Conclusão",
    "referencias": "Referências", "texto": "Texto (atestado/declaração)",
}

EXEMPLOS = (
    ("Exemplo — cautela interpretativa", "Análise", "analise",
     "Os resultados devem ser compreendidos de forma integrada, considerando a história de vida, as condições "
     "da testagem e os demais procedimentos realizados, não devendo ser interpretados isoladamente."),
    ("Exemplo — temporalidade das conclusões", "Conclusão", "conclusao",
     "As conclusões deste documento referem-se ao momento da avaliação e às condições em que foi realizada, "
     "podendo modificar-se ao longo do tempo."),
    ("Exemplo — procedimento", "Procedimento", "procedimento",
     "A avaliação foi realizada em [[número]] encontros, com duração aproximada de [[tempo]] cada, incluindo "
     "entrevista inicial, aplicação de instrumentos psicológicos e entrevista devolutiva."),
    ("Exemplo — descrição de instrumento", "Descrição de instrumento", "procedimento",
     "[[Nome do instrumento]]: instrumento destinado a avaliar [[construto]], com parecer favorável no SATEPSI "
     "na data da aplicação."),
    ("Exemplo — encaminhamento", "Encaminhamento", "conclusao",
     "Recomenda-se [[descrever o encaminhamento ou acompanhamento indicado]]."),
)


def carregar_exemplos(s: Session) -> int:
    """Cria os exemplos apenas se a biblioteca estiver vazia."""
    if s.scalar(select(func.count(TrechoModelo.id))):
        return 0
    for titulo, categoria, secao, texto in EXEMPLOS:
        s.add(TrechoModelo(titulo=titulo, categoria=categoria, secao=secao, texto=texto, exemplo=True))
    s.flush()
    return len(EXEMPLOS)


def _validar(s: Session, titulo: str, categoria: str, secao: str, texto: str, exceto_id: int | None = None):
    titulo, texto = _txt(titulo), (texto or "").strip()
    if not titulo:
        raise ErroValidacao("Dê um título ao trecho.")
    if not texto:
        raise ErroValidacao("Escreva o texto do trecho.")
    if categoria not in CATEGORIAS:
        raise ErroValidacao("Categoria inválida.")
    if secao not in SECOES:
        raise ErroValidacao("Seção inválida.")
    av.verificar_sem_identificadores(titulo, texto)
    consulta = select(TrechoModelo.id).where(func.lower(TrechoModelo.titulo) == titulo.lower())
    if exceto_id is not None:
        consulta = consulta.where(TrechoModelo.id != exceto_id)
    if s.scalar(consulta):
        raise ErroValidacao(f"Já existe um trecho chamado {titulo!r}.")
    return titulo, texto


def criar(s: Session, *, titulo: str, categoria: str, secao: str, texto: str) -> TrechoModelo:
    titulo, texto = _validar(s, titulo, categoria, secao, texto)
    trecho = TrechoModelo(titulo=titulo, categoria=categoria, secao=secao, texto=texto)
    s.add(trecho)
    s.flush()
    auditar(s, "criar_trecho_modelo", "trecho_modelo", trecho.id, titulo=titulo)
    return trecho


def editar(s: Session, trecho_id: int, *, titulo: str, categoria: str, secao: str, texto: str,
           ativo: bool = True) -> TrechoModelo:
    trecho = s.get(TrechoModelo, trecho_id)
    if trecho is None:
        raise ErroValidacao("Trecho não encontrado.")
    titulo, texto = _validar(s, titulo, categoria, secao, texto, exceto_id=trecho_id)
    trecho.titulo, trecho.categoria, trecho.secao, trecho.texto, trecho.ativo = titulo, categoria, secao, texto, ativo
    trecho.atualizado_em = agora_utc()
    auditar(s, "editar_trecho_modelo", "trecho_modelo", trecho_id, titulo=titulo, ativo=ativo)
    return trecho


def listar(s: Session, *, secao: str | None = None, busca: str = "", somente_ativos: bool = True) -> list[TrechoModelo]:
    consulta = select(TrechoModelo).order_by(TrechoModelo.usos.desc(), TrechoModelo.titulo)
    if somente_ativos:
        consulta = consulta.where(TrechoModelo.ativo.is_(True))
    if secao:
        consulta = consulta.where(or_(TrechoModelo.secao == secao, TrechoModelo.secao == "qualquer"))
    termo = _txt(busca).lower()
    if termo:
        consulta = consulta.where(or_(func.lower(TrechoModelo.titulo).contains(termo),
                                      func.lower(TrechoModelo.texto).contains(termo)))
    return list(s.scalars(consulta))


def inserir_em_secao(s: Session, *, documento_id: int, secao_id: int, trecho_id: int):
    """Acrescenta o trecho ao fim da seção (com linha em branco), seguindo as regras do documento."""
    trecho = s.get(TrechoModelo, trecho_id)
    secao = s.get(SecaoDocumento, secao_id)
    if trecho is None or not trecho.ativo:
        raise ErroValidacao("Trecho não encontrado ou desativado.")
    if secao is None or secao.documento_id != documento_id:
        raise ErroValidacao("Seção não pertence a este documento.")
    novo = (secao.conteudo.rstrip() + "\n\n" + trecho.texto) if secao.conteudo.strip() else trecho.texto
    doc = dc.salvar_secoes(s, documento_id, {secao_id: novo})
    trecho.usos += 1
    auditar(s, "inserir_trecho_modelo", "documento", documento_id, codigo=doc.codigo, trecho=trecho.titulo,
            secao=secao.chave)
    return doc
