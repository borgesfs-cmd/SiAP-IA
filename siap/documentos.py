"""Etapa 4 — Documentos psicológicos (estrutura baseada na Resolução CFP nº 06/2019).

Fluxo: rascunho → revisado → aprovado → emitido.
- O sistema monta um RASCUNHO só com dados registrados (demanda, procedimentos, resultados transcritos).
  Análise e conclusão são redigidas pela(o) profissional: o sistema não interpreta nem conclui.
- Marcadores [[...]] indicam trechos a completar; enquanto existirem, o documento não pode ser aprovado.
- Aprovação exige confirmação explícita de revisão integral e autoria técnica.
- Emissão congela o conteúdo (JSON) e grava seu SHA-256. Documento emitido não muda: corrige-se por
  retificação (novo documento que substitui o anterior).
- O nome da pessoa avaliada NUNCA é gravado: o marcador {{NOME DA PESSOA AVALIADA}} é substituído
  apenas no arquivo .docx gerado no momento do download.

Antes do uso real, confira a redação dos modelos com a resolução vigente e suas alterações.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import avaliacoes as av
from .catalogo import ErroValidacao, _txt, auditar, hoje, situacao_versao
from .models import Avaliacao, DocumentoPsicologico, PerfilProfissional, SecaoDocumento, agora_utc

TOKEN_NOME = "{{NOME DA PESSOA AVALIADA}}"
_PENDENTE = re.compile(r"\[\[(.+?)\]\]", re.S)

RASCUNHO, REVISADO, APROVADO, EMITIDO = "rascunho", "revisado", "aprovado", "emitido"
STATUS = {RASCUNHO: "Rascunho", REVISADO: "Revisado", APROVADO: "Aprovado", EMITIDO: "Emitido"}

AVISO_SIGILO = (
    "Este documento é sigiloso, destina-se exclusivamente à finalidade indicada e não deve ser utilizado "
    "para fins diversos. [[Revise este aviso conforme a Resolução CFP nº 06/2019 vigente.]]"
)


@dataclass(frozen=True)
class ModeloSecao:
    chave: str
    titulo: str
    obrigatoria: bool = True


@dataclass(frozen=True)
class ModeloDocumento:
    tipo: str
    titulo: str
    sigla: str
    secoes: tuple[ModeloSecao, ...]
    descricao: str


_IDENT = ModeloSecao("identificacao", "Identificação")
_DEMANDA = ModeloSecao("demanda", "Descrição da demanda")
_PROCED = ModeloSecao("procedimento", "Procedimento")
_ANALISE = ModeloSecao("analise", "Análise")
_CONCL = ModeloSecao("conclusao", "Conclusão")
_REFS = ModeloSecao("referencias", "Referências")

MODELOS: dict[str, ModeloDocumento] = {
    m.tipo: m for m in (
        ModeloDocumento("laudo", "Laudo Psicológico", "LAU",
                        (_IDENT, _DEMANDA, _PROCED, _ANALISE, _CONCL, _REFS),
                        "Resultado de processo de avaliação psicológica, com referências obrigatórias."),
        ModeloDocumento("atestado", "Atestado Psicológico", "ATE",
                        (_IDENT, ModeloSecao("texto", "Texto do atestado")),
                        "Certifica condição psicológica a partir de avaliação, para a finalidade indicada."),
        ModeloDocumento("relatorio", "Relatório Psicológico", "REL",
                        (_IDENT, _DEMANDA, _PROCED, _ANALISE, _CONCL,
                         ModeloSecao("referencias", "Referências", obrigatoria=False)),
                        "Comunica a atuação profissional em diferentes processos de trabalho."),
        ModeloDocumento("parecer", "Parecer Psicológico", "PAR",
                        (_IDENT, _DEMANDA, _ANALISE, _CONCL, _REFS),
                        "Resposta técnica a questão específica do campo psicológico."),
        ModeloDocumento("declaracao", "Declaração", "DEC",
                        (ModeloSecao("texto", "Texto da declaração"),),
                        "Informações objetivas (ex.: comparecimento). Não descreve estado psicológico."),
    )
}


# ------------------------------------------------------------ perfil

def obter_perfil(s: Session) -> PerfilProfissional:
    perfil = s.get(PerfilProfissional, 1)
    if perfil is None:
        perfil = PerfilProfissional(id=1)
        s.add(perfil)
        s.flush()
    return perfil


def salvar_perfil(s: Session, *, nome: str, crp: str, titulacao: str = "", cidade_uf: str = "") -> PerfilProfissional:
    perfil = obter_perfil(s)
    novos = {"nome": _txt(nome), "crp": _txt(crp), "titulacao": _txt(titulacao), "cidade_uf": _txt(cidade_uf)}
    if not novos["nome"] or not novos["crp"]:
        raise ErroValidacao("Informe seu nome e seu número de CRP.")
    antes = {k: getattr(perfil, k) for k in novos if getattr(perfil, k) != novos[k]}
    if antes:
        for k in antes:
            setattr(perfil, k, novos[k])
        perfil.atualizado_em = agora_utc()
        auditar(s, "editar_perfil_profissional", "perfil", 1, campos=sorted(antes))
    return perfil


def _perfil_completo(perfil: PerfilProfissional) -> bool:
    return bool(perfil.nome and perfil.crp)


# ------------------------------------------------------- rascunho inicial

def _lista(itens: list[str]) -> str:
    return "\n".join(f"- {i}" for i in itens)


def _conteudo_inicial(s: Session, modelo: ModeloDocumento, a: Avaliacao, perfil: PerfilProfissional) -> dict[str, str]:
    autor = f"{perfil.nome} — CRP {perfil.crp}" if _perfil_completo(perfil) else "[[Preencha seus dados profissionais]]"
    solicitante = a.contexto or "[[Informe o solicitante]]"
    identificacao = "\n".join([
        f"Autor(a): {autor}",
        f"Interessado(a): {TOKEN_NOME}",
        f"Solicitante: {solicitante}",
        f"Finalidade: {a.finalidade.nome}",
        f"Código interno: {a.codigo}",
    ])

    datas_registros = [f"{r.tipo} — {r.data:%d/%m/%Y}" for r in a.registros]
    aplicacoes = [
        f"{ap.versao.rotulo} — aplicado em {ap.data_aplicacao:%d/%m/%Y} ({ap.modalidade.lower()})"
        for ap in a.aplicacoes
    ]
    procedimento = "Para atender à demanda, foram realizados os seguintes procedimentos:\n" + _lista(
        datas_registros + aplicacoes or ["[[Descreva os procedimentos realizados]]"]
    ) + "\n[[Revise: número de encontros, duração e pessoas ouvidas, se houver.]]"

    dados = []
    for ap in a.aplicacoes:
        for r in ap.resultados:
            valores = ", ".join(v for v in (
                f"escore bruto {r.escore_bruto}" if r.escore_bruto else "",
                f"escore padronizado {r.escore_padrao}" if r.escore_padrao else "",
                f"percentil {r.percentil}" if r.percentil else "",
                f"classificação {r.classificacao}" if r.classificacao else "",
            ) if v)
            dados.append(f"{ap.versao.rotulo} — {r.medida}: {valores}.")
    analise = (
        ("Resultados registrados no sistema (transcritos das fontes oficiais):\n" + _lista(dados) + "\n\n")
        if dados else ""
    ) + "[[Redija a análise integrando entrevistas, observações e resultados, sem extrapolar os dados.]]"

    referencias = sorted({r.referencia for ap in a.aplicacoes for r in ap.resultados if r.referencia})
    texto_refs = (_lista(referencias) + "\n" if referencias else "") + \
        "[[Complete as referências bibliográficas no formato adotado (ex.: ABNT).]]"

    datas_atendimento = sorted({r.data for r in a.registros} | {ap.data_aplicacao for ap in a.aplicacoes})
    datas_txt = ", ".join(f"{d:%d/%m/%Y}" for d in datas_atendimento) or "[[datas]]"

    return {
        "identificacao": identificacao,
        "demanda": a.demanda or "[[Descreva a demanda e os objetivos da avaliação.]]",
        "procedimento": procedimento,
        "analise": analise,
        "conclusao": "[[Redija a conclusão com base exclusivamente na análise acima.]]\n\n" + AVISO_SIGILO,
        "referencias": texto_refs,
        "texto": (
            f"Atesto, para fins de {a.finalidade.nome.lower()}, que {TOKEN_NOME} "
            "[[descreva a condição psicológica observada e, se for o caso, o período de afastamento]]."
            if modelo.tipo == "atestado" else
            f"Declaro, para os devidos fins, que {TOKEN_NOME} compareceu a atendimento psicológico "
            f"nas seguintes datas: {datas_txt}. [[Inclua apenas informações objetivas.]]"
        ),
    }


def _proximo_codigo(s: Session, a: Avaliacao, modelo: ModeloDocumento) -> str:
    prefixo = f"{a.codigo}/{modelo.sigla}-"
    existentes = s.scalars(select(DocumentoPsicologico.codigo).where(DocumentoPsicologico.codigo.like(f"{prefixo}%")))
    maior = max((int(c[len(prefixo):]) for c in existentes if c[len(prefixo):].isdigit()), default=0)
    return f"{prefixo}{maior + 1}"


def criar_documento(s: Session, avaliacao_id: int, tipo: str) -> DocumentoPsicologico:
    modelo = MODELOS.get(tipo)
    if modelo is None:
        raise ErroValidacao("Tipo de documento inválido.")
    a = s.get(Avaliacao, avaliacao_id)
    if a is None:
        raise ErroValidacao("Avaliação não encontrada.")
    if a.status == av.CANCELADA:
        raise ErroValidacao("Avaliação cancelada não gera documentos.")
    perfil = obter_perfil(s)
    conteudo = _conteudo_inicial(s, modelo, a, perfil)
    doc = DocumentoPsicologico(
        avaliacao=a, codigo=_proximo_codigo(s, a, modelo), tipo=tipo, titulo=modelo.titulo, status=RASCUNHO,
    )
    s.add(doc)
    for ordem, sec in enumerate(modelo.secoes, start=1):
        s.add(SecaoDocumento(documento=doc, chave=sec.chave, titulo=sec.titulo, ordem=ordem,
                             obrigatoria=sec.obrigatoria, conteudo=conteudo[sec.chave]))
    s.flush()
    auditar(s, "criar_documento", "documento", doc.id, codigo=doc.codigo, tipo=tipo, avaliacao=a.codigo)
    return doc


# ------------------------------------------------------------- edição

def _documento(s: Session, documento_id: int) -> DocumentoPsicologico:
    doc = s.get(DocumentoPsicologico, documento_id)
    if doc is None:
        raise ErroValidacao("Documento não encontrado.")
    return doc


def salvar_secoes(s: Session, documento_id: int, conteudos: dict[int, str]) -> DocumentoPsicologico:
    """Salva o texto das seções. Qualquer alteração em documento revisado/aprovado o devolve a rascunho."""
    doc = _documento(s, documento_id)
    if doc.status == EMITIDO:
        raise ErroValidacao("Documento emitido não pode ser alterado. Use “Retificar” para criar um novo.")
    por_id = {sec.id: sec for sec in doc.secoes}
    alteradas = []
    for secao_id, texto in conteudos.items():
        sec = por_id.get(secao_id)
        if sec is None:
            raise ErroValidacao("Seção não pertence a este documento.")
        texto = (texto or "").strip()
        av.verificar_sem_identificadores(texto)
        if texto != sec.conteudo:
            auditar(s, "editar_secao_documento", "documento", doc.id, codigo=doc.codigo, secao=sec.chave,
                    conteudo_anterior=sec.conteudo)
            sec.conteudo, sec.editado_em = texto, agora_utc()
            alteradas.append(sec.chave)
    if alteradas and doc.status in (REVISADO, APROVADO):
        anterior, doc.status, doc.aprovado_em = doc.status, RASCUNHO, None
        auditar(s, "documento_volta_a_rascunho", "documento", doc.id, codigo=doc.codigo, de=anterior,
                secoes=alteradas)
    return doc


# ------------------------------------------------------------ checagens

@dataclass(frozen=True)
class Checagem:
    bloqueios: tuple[str, ...]
    alertas: tuple[str, ...]

    @property
    def pode_aprovar(self) -> bool:
        return not self.bloqueios


def checar(s: Session, documento_id: int, referencia: date | None = None) -> Checagem:
    """Verificação de requisitos (bloqueiam a aprovação) e de consistência (alertas)."""
    doc = _documento(s, documento_id)
    bloqueios, alertas = [], []
    perfil = obter_perfil(s)
    if not _perfil_completo(perfil):
        bloqueios.append("Preencha seus dados profissionais (nome e CRP).")
    for sec in doc.secoes:
        if sec.obrigatoria and not sec.conteudo.strip():
            bloqueios.append(f"A seção “{sec.titulo}” é obrigatória e está vazia.")
        pendentes = _PENDENTE.findall(sec.conteudo)
        if pendentes:
            bloqueios.append(f"“{sec.titulo}” ainda tem {len(pendentes)} trecho(s) a completar [[...]].")
    texto_total = "\n".join(sec.conteudo for sec in doc.secoes)
    if doc.tipo in ("laudo", "atestado", "relatorio", "parecer") and TOKEN_NOME not in texto_total:
        alertas.append(f"O marcador {TOKEN_NOME} não aparece: o nome não será inserido no arquivo.")

    a = doc.avaliacao
    if doc.tipo in ("laudo", "relatorio") and not a.aplicacoes and not a.registros:
        alertas.append("A avaliação não tem procedimentos registrados (entrevistas ou instrumentos).")
    for ap in a.aplicacoes:
        sit = situacao_versao(ap.versao, referencia, a.finalidade)
        if not sit.liberado:
            alertas.append(f"{ap.versao.rotulo}: hoje não está elegível para esta finalidade ({sit.motivo}).")
        if not ap.resultados and doc.tipo == "laudo":
            alertas.append(f"{ap.versao.rotulo} não tem resultados registrados.")
    if doc.tipo == "declaracao" and re.search(r"\b(diagn[óo]stic|transtorno|CID|sintoma)", texto_total, re.I):
        alertas.append("Declaração não deve conter informações sobre estado psicológico, sintomas ou diagnóstico.")
    if a.status == av.EM_ANDAMENTO and doc.tipo in ("laudo", "atestado", "parecer"):
        alertas.append("A avaliação ainda está em andamento.")
    return Checagem(tuple(bloqueios), tuple(alertas))


# ------------------------------------------------------------- fluxo

def marcar_revisado(s: Session, documento_id: int) -> DocumentoPsicologico:
    doc = _documento(s, documento_id)
    if doc.status != RASCUNHO:
        raise ErroValidacao("Só um rascunho pode ser marcado como revisado.")
    doc.status = REVISADO
    auditar(s, "documento_revisado", "documento", doc.id, codigo=doc.codigo)
    return doc


def aprovar(s: Session, documento_id: int, *, confirmo_revisao_e_autoria: bool,
            referencia: date | None = None) -> DocumentoPsicologico:
    doc = _documento(s, documento_id)
    if doc.status != REVISADO:
        raise ErroValidacao("Marque o documento como revisado antes de aprovar.")
    if not confirmo_revisao_e_autoria:
        raise ErroValidacao("Confirme que revisou integralmente o documento e assume sua autoria técnica.")
    checagem = checar(s, documento_id, referencia)
    if not checagem.pode_aprovar:
        raise ErroValidacao("Não é possível aprovar: " + " ".join(checagem.bloqueios))
    doc.status, doc.aprovado_em = APROVADO, agora_utc()
    auditar(s, "documento_aprovado", "documento", doc.id, codigo=doc.codigo, alertas=list(checagem.alertas))
    return doc


def _conteudo_canonico(doc: DocumentoPsicologico, perfil: PerfilProfissional, data_emissao: date) -> dict:
    return {
        "codigo": doc.codigo,
        "tipo": doc.tipo,
        "titulo": doc.titulo,
        "avaliacao": doc.avaliacao.codigo,
        "autor": {"nome": perfil.nome, "crp": perfil.crp, "titulacao": perfil.titulacao},
        "local": perfil.cidade_uf,
        "data_emissao": data_emissao.isoformat(),
        "secoes": [{"titulo": sec.titulo, "conteudo": sec.conteudo} for sec in doc.secoes],
    }


def calcular_hash(conteudo: dict) -> str:
    bruto = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def emitir(s: Session, documento_id: int, referencia: date | None = None) -> DocumentoPsicologico:
    doc = _documento(s, documento_id)
    if doc.status != APROVADO:
        raise ErroValidacao("Só documentos aprovados podem ser emitidos.")
    checagem = checar(s, documento_id, referencia)
    if not checagem.pode_aprovar:
        raise ErroValidacao("Não é possível emitir: " + " ".join(checagem.bloqueios))
    perfil = obter_perfil(s)
    data_emissao = referencia or hoje()
    conteudo = _conteudo_canonico(doc, perfil, data_emissao)
    doc.conteudo_emitido = json.dumps(conteudo, ensure_ascii=False, sort_keys=True)
    doc.hash_conteudo = calcular_hash(conteudo)
    doc.status, doc.emitido_em, doc.data_emissao = EMITIDO, agora_utc(), data_emissao
    auditar(s, "documento_emitido", "documento", doc.id, codigo=doc.codigo, sha256=doc.hash_conteudo)
    return doc


def retificar(s: Session, documento_id: int) -> DocumentoPsicologico:
    """Cria novo rascunho a partir de um documento emitido; o original permanece intacto."""
    original = _documento(s, documento_id)
    if original.status != EMITIDO:
        raise ErroValidacao("Só documentos emitidos são retificados; edite o rascunho diretamente.")
    modelo = MODELOS[original.tipo]
    novo = DocumentoPsicologico(
        avaliacao=original.avaliacao, codigo=_proximo_codigo(s, original.avaliacao, modelo), tipo=original.tipo,
        titulo=original.titulo, status=RASCUNHO, substitui_id=original.id,
    )
    s.add(novo)
    for sec in original.secoes:
        s.add(SecaoDocumento(documento=novo, chave=sec.chave, titulo=sec.titulo, ordem=sec.ordem,
                             obrigatoria=sec.obrigatoria, conteudo=sec.conteudo))
    s.flush()
    auditar(s, "retificar_documento", "documento", novo.id, codigo=novo.codigo, substitui=original.codigo)
    return novo


# ------------------------------------------------------------ consultas

def listar_documentos(s: Session, avaliacao_id: int | None = None) -> list[DocumentoPsicologico]:
    consulta = (select(DocumentoPsicologico)
                .options(selectinload(DocumentoPsicologico.avaliacao))
                .order_by(DocumentoPsicologico.id.desc()))
    if avaliacao_id is not None:
        consulta = consulta.where(DocumentoPsicologico.avaliacao_id == avaliacao_id)
    return list(s.scalars(consulta))


def substituido_por(s: Session, documento_id: int) -> DocumentoPsicologico | None:
    return s.scalar(select(DocumentoPsicologico).where(DocumentoPsicologico.substitui_id == documento_id))


def conteudo_para_exportar(s: Session, documento_id: int) -> tuple[dict, bool]:
    """(conteúdo, é_final). Emitido → fotografia congelada; senão → prévia do estado atual."""
    doc = _documento(s, documento_id)
    if doc.status == EMITIDO:
        conteudo = json.loads(doc.conteudo_emitido)
        conteudo["hash"] = doc.hash_conteudo
        return conteudo, True
    perfil = obter_perfil(s)
    conteudo = _conteudo_canonico(doc, perfil, hoje())
    conteudo["hash"] = None
    return conteudo, False


def resumo_dados_registrados(a: Avaliacao) -> str:
    """Dados factuais da avaliação (para conferência pela IA). Sem nomes: só código e registros."""
    linhas = [f"Finalidade: {a.finalidade.nome}", f"Faixa etária: {a.faixa_etaria}"]
    if a.idade is not None:
        linhas.append(f"Idade: {a.idade} anos")
    if a.escolaridade:
        linhas.append(f"Escolaridade: {a.escolaridade}")
    if a.contexto:
        linhas.append(f"Contexto/solicitante: {a.contexto}")
    if a.demanda:
        linhas.append(f"Demanda: {a.demanda}")
    for r in a.registros:
        linhas.append(f"[{r.data:%d/%m/%Y}] {r.tipo}: {r.conteudo}")
    for ap in a.aplicacoes:
        linhas.append(f"Instrumento: {ap.versao.rotulo}, aplicado em {ap.data_aplicacao:%d/%m/%Y} ({ap.modalidade})")
        for r in ap.resultados:
            valores = "; ".join(f"{rot} {v}" for rot, v in (
                ("escore bruto", r.escore_bruto), ("escore padronizado", r.escore_padrao),
                ("percentil", r.percentil), ("classificação", r.classificacao)) if v)
            linhas.append(f"  - {r.medida}: {valores} (ref.: {r.referencia})")
    return "\n".join(linhas)
