"""Etapa 3 — Gestão de avaliações.

- Avaliações identificadas apenas por código gerado (AV-AAAA-NNN).
- Instrumentos só podem ser registrados se `pode_uso_profissional` liberar a versão PARA A FINALIDADE
  da avaliação; a situação no momento do registro fica fotografada na aplicação.
- Resultados são transcritos do manual/plataforma oficial; o sistema não calcula normas protegidas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import satepsi
from .catalogo import ErroValidacao, _txt, auditar, hoje, pode_uso_profissional, situacao_versao
from .models import (
    AplicacaoInstrumento,
    Avaliacao,
    Finalidade,
    Instrumento,
    RegistroAvaliacao,
    ResultadoRegistrado,
    VersaoInstrumento,
    agora_utc,
)

FAIXAS_ETARIAS = ("Criança", "Adolescente", "Adulto", "Idoso")
ESCOLARIDADES = (
    "", "Não alfabetizado", "Educação infantil", "Fundamental incompleto", "Fundamental completo",
    "Médio incompleto", "Médio completo", "Superior incompleto", "Superior completo", "Pós-graduação",
)
TIPOS_REGISTRO = (
    "Entrevista inicial", "Anamnese", "Entrevista", "Observação", "Contato com fonte complementar",
    "Devolutiva", "Outro",
)
MODALIDADES = ("Individual presencial", "Coletiva presencial", "Individual informatizada", "Outra")

EM_ANDAMENTO, CONCLUIDA, CANCELADA = "em_andamento", "concluida", "cancelada"
STATUS = {EM_ANDAMENTO: "Em andamento", CONCLUIDA: "Concluída", CANCELADA: "Cancelada"}

# ------------------------------------------------------------ privacidade

_PADROES_IDENTIFICADORES = (
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("telefone", re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]\d{4}\b")),
)


def verificar_sem_identificadores(*textos: str) -> None:
    """Recusa textos com padrões de CPF, e-mail ou telefone. (Nomes próprios não são detectáveis:
    a responsabilidade de não digitá-los é do usuário.)"""
    for texto in textos:
        for rotulo, padrao in _PADROES_IDENTIFICADORES:
            if texto and padrao.search(texto):
                raise ErroValidacao(
                    f"O texto parece conter {rotulo}. O SIAP-IA não armazena identificação direta "
                    "de pessoas: remova o dado e use apenas o código da avaliação."
                )


# ------------------------------------------------------------ avaliações

def _proximo_codigo(s: Session, ano: int) -> str:
    prefixo = f"AV-{ano}-"
    codigos = s.scalars(select(Avaliacao.codigo).where(Avaliacao.codigo.like(f"{prefixo}%")))
    maior = max((int(c[len(prefixo):]) for c in codigos if c[len(prefixo):].isdigit()), default=0)
    return f"{prefixo}{maior + 1:03d}"


def _validar_perfil(faixa_etaria: str, idade: int | None, escolaridade: str) -> None:
    if faixa_etaria not in FAIXAS_ETARIAS:
        raise ErroValidacao("Selecione a faixa etária.")
    if idade is not None and not 0 <= int(idade) <= 120:
        raise ErroValidacao("Idade deve estar entre 0 e 120 anos.")
    if escolaridade not in ESCOLARIDADES:
        raise ErroValidacao("Escolaridade inválida.")


def _finalidade_ativa(s: Session, finalidade_id: int) -> Finalidade:
    finalidade = s.get(Finalidade, finalidade_id)
    if finalidade is None:
        raise ErroValidacao("Finalidade não encontrada.")
    if not finalidade.ativa:
        raise ErroValidacao(f"A finalidade {finalidade.nome!r} está desativada.")
    return finalidade


def criar_avaliacao(
    s: Session, *, finalidade_id: int, faixa_etaria: str, data_inicio: date,
    idade: int | None = None, escolaridade: str = "", contexto: str = "", demanda: str = "",
    referencia: date | None = None,
) -> Avaliacao:
    referencia = referencia or hoje()
    finalidade = _finalidade_ativa(s, finalidade_id)
    _validar_perfil(faixa_etaria, idade, escolaridade)
    if data_inicio > referencia:
        raise ErroValidacao("A data de início não pode estar no futuro.")
    contexto, demanda = _txt(contexto), _txt(demanda)
    verificar_sem_identificadores(contexto, demanda)

    avaliacao = Avaliacao(
        codigo=_proximo_codigo(s, data_inicio.year), finalidade=finalidade, faixa_etaria=faixa_etaria,
        idade=int(idade) if idade is not None else None, escolaridade=escolaridade,
        contexto=contexto, demanda=demanda, status=EM_ANDAMENTO, data_inicio=data_inicio,
    )
    s.add(avaliacao)
    s.flush()
    auditar(s, "criar_avaliacao", "avaliacao", avaliacao.id, codigo=avaliacao.codigo,
            finalidade=finalidade.nome)
    return avaliacao


def _avaliacao(s: Session, avaliacao_id: int, exigir_em_andamento: bool = True) -> Avaliacao:
    avaliacao = s.get(Avaliacao, avaliacao_id)
    if avaliacao is None:
        raise ErroValidacao("Avaliação não encontrada.")
    if exigir_em_andamento and avaliacao.status != EM_ANDAMENTO:
        raise ErroValidacao(
            f"A avaliação {avaliacao.codigo} está {STATUS[avaliacao.status].lower()}: reabra-a para alterar."
        )
    return avaliacao


def atualizar_avaliacao(
    s: Session, avaliacao_id: int, *, finalidade_id: int, faixa_etaria: str, idade: int | None,
    escolaridade: str, contexto: str, demanda: str,
) -> Avaliacao:
    avaliacao = _avaliacao(s, avaliacao_id)
    _validar_perfil(faixa_etaria, idade, escolaridade)
    contexto, demanda = _txt(contexto), _txt(demanda)
    verificar_sem_identificadores(contexto, demanda)
    if finalidade_id != avaliacao.finalidade_id:
        if avaliacao.aplicacoes:
            raise ErroValidacao(
                "Não é possível mudar a finalidade depois de registrar instrumentos: a liberação SATEPSI "
                "foi conferida para a finalidade original."
            )
        _finalidade_ativa(s, finalidade_id)

    novos = dict(finalidade_id=finalidade_id, faixa_etaria=faixa_etaria,
                 idade=int(idade) if idade is not None else None, escolaridade=escolaridade,
                 contexto=contexto, demanda=demanda)
    antes = {k: getattr(avaliacao, k) for k in novos if getattr(avaliacao, k) != novos[k]}
    if antes:
        for k in antes:
            setattr(avaliacao, k, novos[k])
        if "finalidade_id" in antes:
            avaliacao.finalidade = s.get(Finalidade, finalidade_id)
        auditar(s, "editar_avaliacao", "avaliacao", avaliacao_id, campos=sorted(antes))
    return avaliacao


def alterar_status(s: Session, avaliacao_id: int, novo_status: str, referencia: date | None = None) -> Avaliacao:
    if novo_status not in STATUS:
        raise ErroValidacao("Situação inválida.")
    avaliacao = _avaliacao(s, avaliacao_id, exigir_em_andamento=False)
    if avaliacao.status == novo_status:
        return avaliacao
    anterior = avaliacao.status
    avaliacao.status = novo_status
    avaliacao.data_conclusao = (referencia or hoje()) if novo_status == CONCLUIDA else None
    auditar(s, "alterar_status_avaliacao", "avaliacao", avaliacao_id, de=anterior, para=novo_status)
    return avaliacao


# ------------------------------------------------- entrevistas/observações

def adicionar_registro(
    s: Session, avaliacao_id: int, *, tipo: str, data: date, conteudo: str, referencia: date | None = None,
) -> RegistroAvaliacao:
    avaliacao = _avaliacao(s, avaliacao_id)
    if tipo not in TIPOS_REGISTRO:
        raise ErroValidacao("Tipo de registro inválido.")
    if data > (referencia or hoje()):
        raise ErroValidacao("A data não pode estar no futuro.")
    conteudo = _txt(conteudo)
    if not conteudo:
        raise ErroValidacao("Escreva o conteúdo do registro.")
    verificar_sem_identificadores(conteudo)
    registro = RegistroAvaliacao(avaliacao=avaliacao, tipo=tipo, data=data, conteudo=conteudo)
    s.add(registro)
    s.flush()
    auditar(s, "criar_registro_avaliacao", "registro_avaliacao", registro.id,
            avaliacao=avaliacao.codigo, tipo=tipo)
    return registro


def editar_registro(s: Session, registro_id: int, *, conteudo: str) -> RegistroAvaliacao:
    registro = s.get(RegistroAvaliacao, registro_id)
    if registro is None:
        raise ErroValidacao("Registro não encontrado.")
    _avaliacao(s, registro.avaliacao_id)
    conteudo = _txt(conteudo)
    if not conteudo:
        raise ErroValidacao("O conteúdo não pode ficar vazio.")
    verificar_sem_identificadores(conteudo)
    if conteudo != registro.conteudo:
        anterior = registro.conteudo
        registro.conteudo = conteudo
        registro.editado_em = agora_utc()
        auditar(s, "editar_registro_avaliacao", "registro_avaliacao", registro_id, conteudo_anterior=anterior)
    return registro


# -------------------------------------------------- instrumentos aplicados

@dataclass(frozen=True)
class OpcaoVersao:
    versao_id: int
    rotulo: str
    situacao: satepsi.Situacao


def opcoes_de_versao(s: Session, avaliacao_id: int, referencia: date | None = None) -> list[OpcaoVersao]:
    """Todas as versões do catálogo com a situação PARA A FINALIDADE desta avaliação."""
    avaliacao = _avaliacao(s, avaliacao_id, exigir_em_andamento=False)
    versoes = s.scalars(
        select(VersaoInstrumento)
        .options(selectinload(VersaoInstrumento.instrumento),
                 selectinload(VersaoInstrumento.verificacoes))
        .join(Instrumento).order_by(Instrumento.nome, VersaoInstrumento.nome_versao)
    )
    return [
        OpcaoVersao(v.id, v.rotulo, situacao_versao(v, referencia, avaliacao.finalidade))
        for v in versoes
    ]


def registrar_aplicacao(
    s: Session, avaliacao_id: int, *, versao_id: int, data_aplicacao: date, modalidade: str,
    observacoes: str = "", referencia: date | None = None,
) -> AplicacaoInstrumento:
    referencia = referencia or hoje()
    avaliacao = _avaliacao(s, avaliacao_id)
    if modalidade not in MODALIDADES:
        raise ErroValidacao("Modalidade inválida.")
    if data_aplicacao > referencia:
        raise ErroValidacao("A data de aplicação não pode estar no futuro.")
    if data_aplicacao < avaliacao.data_inicio:
        raise ErroValidacao("A data de aplicação é anterior ao início da avaliação.")
    observacoes = _txt(observacoes)
    verificar_sem_identificadores(observacoes)

    situacao = pode_uso_profissional(s, versao_id, referencia, avaliacao.finalidade_id)
    if not situacao.liberado:
        raise ErroValidacao(f"Uso profissional bloqueado: {situacao.motivo}")

    versao = s.get(VersaoInstrumento, versao_id)
    vigente = satepsi.verificacao_vigente(versao.verificacoes)
    aplicacao = AplicacaoInstrumento(
        avaliacao=avaliacao, versao=versao, data_aplicacao=data_aplicacao, modalidade=modalidade,
        observacoes=observacoes, satepsi_status_no_registro=situacao.status,
        satepsi_motivo_no_registro=situacao.motivo,
        verificacao_id_no_registro=vigente.id if vigente else None,
    )
    s.add(aplicacao)
    s.flush()
    auditar(s, "registrar_aplicacao", "aplicacao", aplicacao.id, avaliacao=avaliacao.codigo,
            versao=versao.rotulo, satepsi=situacao.status,
            verificacao_id=aplicacao.verificacao_id_no_registro)
    return aplicacao


_CAMPOS_RESULTADO = ("medida", "escore_bruto", "escore_padrao", "percentil", "classificacao", "referencia")


def _limpar_resultado(campos: dict) -> dict:
    limpos = {k: _txt(campos.get(k)) for k in _CAMPOS_RESULTADO}
    if not limpos["medida"]:
        raise ErroValidacao("Informe a medida/escala (ex.: “Total”, “Concentração”).")
    if not any(limpos[k] for k in ("escore_bruto", "escore_padrao", "percentil", "classificacao")):
        raise ErroValidacao("Informe ao menos um valor: escore bruto, padronizado, percentil ou classificação.")
    if not limpos["referencia"]:
        raise ErroValidacao("Informe a referência (manual, tabela/norma ou plataforma oficial de correção).")
    verificar_sem_identificadores(*limpos.values())
    return limpos


def adicionar_resultado(s: Session, aplicacao_id: int, **campos) -> ResultadoRegistrado:
    aplicacao = s.get(AplicacaoInstrumento, aplicacao_id)
    if aplicacao is None:
        raise ErroValidacao("Aplicação não encontrada.")
    _avaliacao(s, aplicacao.avaliacao_id)
    resultado = ResultadoRegistrado(aplicacao=aplicacao, **_limpar_resultado(campos))
    s.add(resultado)
    s.flush()
    auditar(s, "registrar_resultado", "resultado", resultado.id, aplicacao_id=aplicacao_id,
            medida=resultado.medida)
    return resultado


def editar_resultado(s: Session, resultado_id: int, **campos) -> ResultadoRegistrado:
    resultado = s.get(ResultadoRegistrado, resultado_id)
    if resultado is None:
        raise ErroValidacao("Resultado não encontrado.")
    _avaliacao(s, resultado.aplicacao.avaliacao_id)
    novos = _limpar_resultado(campos)
    antes = {k: getattr(resultado, k) for k in novos if getattr(resultado, k) != novos[k]}
    if antes:
        for k in antes:
            setattr(resultado, k, novos[k])
        resultado.editado_em = agora_utc()
        auditar(s, "editar_resultado", "resultado", resultado_id, antes=antes,
                depois={k: novos[k] for k in antes})
    return resultado


# --------------------------------------------------------------- consultas

def listar_avaliacoes(s: Session, status: str | None = None, finalidade_id: int | None = None) -> list[Avaliacao]:
    consulta = (select(Avaliacao).options(selectinload(Avaliacao.finalidade))
                .order_by(Avaliacao.data_inicio.desc(), Avaliacao.id.desc()))
    if status:
        consulta = consulta.where(Avaliacao.status == status)
    if finalidade_id:
        consulta = consulta.where(Avaliacao.finalidade_id == finalidade_id)
    return list(s.scalars(consulta))


@dataclass(frozen=True)
class AlertaConformidade:
    avaliacao_id: int
    codigo: str
    versao: str
    motivo: str


def alertas_conformidade(s: Session, referencia: date | None = None) -> list[AlertaConformidade]:
    """Avaliações EM ANDAMENTO com instrumento cuja versão deixou de estar elegível para a finalidade.

    Não altera nada já registrado: apenas sinaliza para análise profissional.
    """
    alertas = []
    for avaliacao in listar_avaliacoes(s, status=EM_ANDAMENTO):
        vistos = set()
        for aplicacao in avaliacao.aplicacoes:
            if aplicacao.versao_id in vistos:
                continue
            vistos.add(aplicacao.versao_id)
            situacao = situacao_versao(aplicacao.versao, referencia, avaliacao.finalidade)
            if not situacao.liberado:
                alertas.append(AlertaConformidade(avaliacao.id, avaliacao.codigo,
                                                  aplicacao.versao.rotulo, situacao.motivo))
    return alertas
