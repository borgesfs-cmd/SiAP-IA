"""Consultor IA (API do Claude) — apoio metodológico, revisão de redação e sugestão de códigos qualitativos.

Regras (CLAUDE.md, regras 1, 4 e 6):
- Desligado até o usuário consentir explicitamente (perfil.ia_habilitada) e haver ANTHROPIC_API_KEY.
- Todo texto é PSEUDONIMIZADO antes do envio: marcador de nome → [PESSOA AVALIADA], código do caso →
  [CASO], padrões de CPF/e-mail/telefone → [REMOVIDO]. Nomes próprios digitados por engano não são
  detectáveis: por isso a regra de nunca escrever nomes vale para todo o sistema.
- A IA SUGERE; nada é aplicado sem ação explícita da(o) profissional.
- Números presentes na resposta que não constam dos dados enviados são sinalizados ("IA não inventa números").
- A auditoria registra só metadados da chamada (função, modelo, tokens), nunca o conteúdo.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .catalogo import ErroValidacao, auditar
from .documentos import TOKEN_NOME, obter_perfil
from . import segredos
from .models import agora_utc

MODELO = "claude-opus-5-5"
BETAS = ["server-side-fallback-2026-07-01"]  # modelo reserva automático em caso de recusa

_SUBSTITUICOES = (
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[REMOVIDO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REMOVIDO]"),
    (re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]\d{4}\b"), "[REMOVIDO]"),
    (re.compile(r"\bAV-\d{4}-\d{3,}(?:/[A-Z]{3}-\d+)?\b"), "[CASO]"),
)
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")

SISTEMA_BASE = (
    "Você apoia uma psicóloga brasileira em avaliação psicológica. Escreva em português do Brasil, "
    "com linguagem técnica, clara e respeitosa. Você é um assistente: não decide aptidão, diagnóstico "
    "nem conclusões — apenas sugere, e a profissional decide. Use somente as informações fornecidas; "
    "quando faltar dado, diga o que falta em vez de supor. Nunca crie números, escores, percentis, datas "
    "ou referências que não estejam nos dados fornecidos. Respeite o Código de Ética Profissional do "
    "Psicólogo e a Resolução CFP nº 06/2019 (documentos psicológicos), sem citar artigos de memória. "
    "Os textos chegam pseudonimizados: não tente identificar a pessoa."
)


class ErroIA(ErroValidacao):
    """Falha ou indisponibilidade do consultor IA (mensagem pronta para exibir)."""


# ---------------------------------------------------------- esquemas de saída

class RevisaoRedacao(BaseModel):
    texto_sugerido: str = Field(description="Versão revisada da seção, mantendo os marcadores [PESSOA AVALIADA] e [[...]].")
    observacoes: list[str] = Field(description="Pontos de clareza, coesão, terminologia e extrapolações encontradas.")
    alertas: list[str] = Field(description="Riscos éticos/técnicos: afirmações sem base nos dados, juízos de valor, dados desnecessários.")


class RespostaConsultor(BaseModel):
    resposta: str = Field(description="Orientação metodológica fundamentada.")
    instrumentos_sugeridos: list[str] = Field(description="Somente nomes exatos da lista de instrumentos elegíveis fornecida.")
    cautelas: list[str] = Field(description="Limitações, pressupostos e cuidados.")


class ItemCodificacao(BaseModel):
    registro_id: int
    trecho: str = Field(description="Cópia LITERAL de um trecho do registro, sem alterações.")
    codigo: str = Field(description="Nome curto do código/categoria.")
    justificativa: str


class SugestaoCodificacao(BaseModel):
    itens: list[ItemCodificacao]
    observacoes: list[str] = Field(description="Temas gerais percebidos e limitações da análise.")


# ------------------------------------------------------------------ utilidades

def pseudonimizar(texto: str) -> str:
    texto = (texto or "").replace(TOKEN_NOME, "[PESSOA AVALIADA]")
    for padrao, troca in _SUBSTITUICOES:
        texto = padrao.sub(troca, texto)
    return texto


def numeros_novos(saida: str, *entradas: str) -> list[str]:
    """Números da resposta que não aparecem em nenhum dado enviado (para alerta)."""
    conhecidos = {n.replace(",", ".") for e in entradas for n in _NUMERO.findall(e or "")}
    vistos, novos = set(), []
    for n in _NUMERO.findall(saida or ""):
        chave = n.replace(",", ".")
        if chave not in conhecidos and chave not in vistos:
            vistos.add(chave)
            novos.append(n)
    return novos


def chave_dos_secrets() -> str | None:
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if chave:
        return chave
    try:
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def chave_api(s: Session) -> str | None:
    """Ordem: Secrets/ambiente → chave colada na aba “Chave da API” (cifrada no banco)."""
    return chave_dos_secrets() or segredos.ler(s, segredos.CHAVE_ANTHROPIC)


def situacao(s: Session) -> tuple[bool, str]:
    """(disponível, motivo)."""
    perfil = obter_perfil(s)
    if not perfil.ia_habilitada:
        return False, "O consultor IA está desligado. Ative-o na página Consultor IA, após ler o termo."
    if not chave_api(s):
        return False, "Falta a chave da API do Claude: cole-a na aba 🔑 Chave da API."
    return True, ""


def testar_chave(chave: str, cliente=None) -> str:
    """Confere a chave consultando o modelo usado (sem gerar texto nem custo de tokens)."""
    import anthropic

    cliente = cliente or anthropic.Anthropic(api_key=chave, max_retries=1, timeout=30.0)
    try:
        modelo = cliente.models.retrieve(MODELO)
    except anthropic.AuthenticationError:
        raise ErroIA("A chave foi recusada pela Anthropic. Confira se copiou a chave inteira.")
    except anthropic.PermissionDeniedError:
        raise ErroIA("A chave não tem permissão para usar o modelo. Verifique a conta na Anthropic.")
    except anthropic.APIConnectionError:
        raise ErroIA("Sem conexão com a Anthropic para testar a chave. Tente novamente.")
    except anthropic.APIStatusError as e:
        raise ErroIA(f"A Anthropic retornou erro ({e.status_code}) ao testar a chave.")
    return getattr(modelo, "display_name", None) or MODELO


def definir_consentimento(s: Session, habilitar: bool) -> None:
    perfil = obter_perfil(s)
    if perfil.ia_habilitada == habilitar:
        return
    perfil.ia_habilitada = habilitar
    perfil.ia_consentimento_em = agora_utc() if habilitar else None
    auditar(s, "ia_habilitada" if habilitar else "ia_desabilitada", "perfil", 1)


def _cliente_padrao(s: Session):
    import anthropic

    return anthropic.Anthropic(api_key=chave_api(s), max_retries=2, timeout=180.0)


@dataclass
class Resultado:
    dados: BaseModel
    numeros_nao_encontrados: list[str] = field(default_factory=list)


def _chamar(s: Session, funcao: str, instrucao: str, conteudo: str, esquema: type[BaseModel],
            esforco: str = "medium", cliente=None) -> BaseModel:
    disponivel, motivo = situacao(s) if cliente is None else (True, "")
    if not disponivel:
        raise ErroIA(motivo)
    import anthropic

    cliente = cliente or _cliente_padrao(s)
    try:
        resposta = cliente.beta.messages.parse(
            model=MODELO,
            max_tokens=16000,
            betas=BETAS,
            fallbacks="default",
            system=SISTEMA_BASE + "\n\n" + instrucao,
            output_config={"effort": esforco},
            output_format=esquema,
            messages=[{"role": "user", "content": conteudo}],
        )
    except anthropic.AuthenticationError:
        raise ErroIA("A chave ANTHROPIC_API_KEY foi recusada. Confira-a nos Secrets do Streamlit.")
    except anthropic.RateLimitError:
        raise ErroIA("Limite de uso da API atingido. Aguarde alguns minutos e tente de novo.")
    except anthropic.APIConnectionError:
        raise ErroIA("Sem conexão com a API do Claude. Tente novamente.")
    except anthropic.APIStatusError as e:
        raise ErroIA(f"A API do Claude retornou erro ({e.status_code}). Tente novamente mais tarde.")

    uso = getattr(resposta, "usage", None)
    auditar(s, "consulta_ia", "ia", None, funcao=funcao, modelo=getattr(resposta, "model", MODELO),
            tokens_entrada=getattr(uso, "input_tokens", None), tokens_saida=getattr(uso, "output_tokens", None),
            stop_reason=resposta.stop_reason)
    if resposta.stop_reason == "refusal":
        raise ErroIA("O modelo recusou este pedido. Reformule o texto ou a pergunta.")
    if resposta.stop_reason == "max_tokens" or resposta.parsed_output is None:
        raise ErroIA("A resposta ficou incompleta. Tente com um texto menor.")
    return resposta.parsed_output


# ------------------------------------------------------------------- funções

def revisar_secao(s: Session, *, tipo_documento: str, titulo_secao: str, texto: str,
                  dados_registrados: str, cliente=None) -> Resultado:
    texto_p, dados_p = pseudonimizar(texto), pseudonimizar(dados_registrados)
    instrucao = (
        "Revise a redação de UMA seção de documento psicológico. Melhore clareza, coesão e terminologia "
        "técnica, sem acrescentar fatos, resultados ou conclusões que não estejam no texto ou nos dados "
        "registrados. Preserve exatamente os marcadores [PESSOA AVALIADA] e os trechos [[...]] que ainda "
        "precisam ser completados pela profissional. Aponte extrapolações e afirmações sem base nos dados."
    )
    conteudo = (f"Tipo de documento: {tipo_documento}\nSeção: {titulo_secao}\n\n"
                f"<dados_registrados>\n{dados_p}\n</dados_registrados>\n\n<texto_da_secao>\n{texto_p}\n</texto_da_secao>")
    dados = _chamar(s, "revisar_secao", instrucao, conteudo, RevisaoRedacao, cliente=cliente)
    novos = numeros_novos(dados.texto_sugerido + " " + " ".join(dados.observacoes), texto_p, dados_p)
    return Resultado(dados, novos)


def consultar(s: Session, *, pergunta: str, contexto: str, instrumentos_elegiveis: list[str],
              cliente=None) -> Resultado:
    pergunta_p, contexto_p = pseudonimizar(pergunta), pseudonimizar(contexto)
    lista = "\n".join(f"- {i}" for i in instrumentos_elegiveis) or "(nenhum instrumento elegível no momento)"
    instrucao = (
        "Atue como consultor metodológico em avaliação psicológica: ajude a escolher técnicas, "
        "procedimentos e instrumentos, explicando pressupostos e limitações. Ao sugerir instrumentos "
        "psicológicos, use SOMENTE os da lista de elegíveis (já conferidos no SATEPSI para a finalidade); "
        "se nenhum servir, diga isso e sugira apenas procedimentos (entrevistas, observação, fontes "
        "complementares). Não reproduza itens, normas ou chaves de correção de testes."
    )
    conteudo = (f"<contexto_da_avaliacao>\n{contexto_p}\n</contexto_da_avaliacao>\n\n"
                f"<instrumentos_elegiveis>\n{lista}\n</instrumentos_elegiveis>\n\n<pergunta>\n{pergunta_p}\n</pergunta>")
    dados = _chamar(s, "consultor_metodologico", instrucao, conteudo, RespostaConsultor, esforco="high", cliente=cliente)
    permitidos = set(instrumentos_elegiveis)
    fora = [i for i in dados.instrumentos_sugeridos if i not in permitidos]
    dados.instrumentos_sugeridos = [i for i in dados.instrumentos_sugeridos if i in permitidos]
    if fora:
        dados.cautelas.append("Sugestões fora da lista de instrumentos elegíveis foram descartadas: " + "; ".join(fora))
    return Resultado(dados, numeros_novos(dados.resposta, pergunta_p, contexto_p, lista))


def sugerir_codificacao(s: Session, *, registros: list[tuple[int, str, str]], codigos_existentes: list[str],
                        cliente=None) -> Resultado:
    """registros: (id, tipo, conteúdo). Descarta itens cujo trecho não seja literal do registro."""
    pseudo = {rid: pseudonimizar(texto) for rid, _, texto in registros}
    blocos = "\n\n".join(f'<registro id="{rid}" tipo="{tipo}">\n{pseudo[rid]}\n</registro>' for rid, tipo, _ in registros)
    instrucao = (
        "Faça uma análise de conteúdo/temática exploratória dos registros (entrevistas e observações). "
        "Sugira códigos curtos e, para cada ocorrência, copie o trecho LITERALMENTE como está no registro "
        "(sem corrigir, resumir ou trocar palavras). Prefira reutilizar os códigos já existentes quando "
        "adequados. Não faça diagnóstico."
    )
    existentes = "\n".join(f"- {c}" for c in codigos_existentes) or "(nenhum)"
    conteudo = f"<codigos_existentes>\n{existentes}\n</codigos_existentes>\n\n{blocos}"
    dados = _chamar(s, "sugerir_codificacao", instrucao, conteudo, SugestaoCodificacao, cliente=cliente)

    def _norm(t: str) -> str:
        return " ".join(t.split())

    validos, descartados = [], 0
    for item in dados.itens:
        origem = pseudo.get(item.registro_id)
        if origem is not None and item.trecho.strip() and _norm(item.trecho) in _norm(origem) \
                and "[PESSOA AVALIADA]" not in item.trecho:
            validos.append(item)
        else:
            descartados += 1
    dados.itens = validos
    if descartados:
        dados.observacoes.append(f"{descartados} sugestão(ões) descartada(s) por não reproduzirem literalmente o registro.")
    return Resultado(dados, [])
