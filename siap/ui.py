"""Utilidades de interface (Streamlit) compartilhadas pelas páginas."""

from __future__ import annotations

import hmac
from contextlib import contextmanager
from datetime import datetime, timezone

import streamlit as st

from . import satepsi
from .catalogo import FUSO, ErroValidacao
from .db import ConfiguracaoBancoInvalida, criar_engine, database_url, fabrica_sessoes
from .finalidades import carregar_finalidades_padrao
from .inventario import carregar_inventario_inicial

AVISO = (
    "Uso pessoal e não comercial. Não registre nome, CPF ou qualquer dado que identifique "
    "diretamente uma pessoa: use apenas códigos. A IA e o sistema não substituem o julgamento "
    "profissional."
)

CORES = {
    satepsi.FAVORAVEL: "green",
    satepsi.DESFAVORAVEL: "red",
    satepsi.RESTRITO: "orange",
    satepsi.EM_AVALIACAO: "orange",
    satepsi.NAO_LOCALIZADO: "gray",
    satepsi.NAO_VERIFICADO: "gray",
}


def _segredo(chave: str) -> str | None:
    try:
        return st.secrets.get(chave)
    except Exception:
        return None


@st.cache_resource
def _fabrica(url: str):
    engine = criar_engine(url)
    fabrica = fabrica_sessoes(engine)
    with fabrica.begin() as s:
        carregar_finalidades_padrao(s)
        carregar_inventario_inicial(s)
    return fabrica


@contextmanager
def transacao():
    """Sessão com commit automático ao final (ou rollback em caso de erro)."""
    try:
        fabrica = _fabrica(database_url())
    except ConfiguracaoBancoInvalida as erro:
        st.error(f"**Banco de dados não configurado corretamente.** {erro}")
        st.stop()
    with fabrica.begin() as s:
        yield s


CSS = """
<style>
/* ---------- layout geral ---------- */
.block-container {padding-top: 4.6rem; max-width: 1240px;}
h1 {letter-spacing: -0.02em;}
/* ---------- cabeçalho de página ---------- */
.siap-cab {display:flex; gap:.9rem; align-items:center; margin-bottom:.15rem;}
.siap-cab .ic {width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  font-size:1.5rem; background:linear-gradient(135deg, rgba(109,106,240,.18), rgba(42,155,214,.18));}
.siap-cab h1 {margin:0; padding:0; font-size:1.85rem; line-height:1.15;}
.siap-sub {opacity:.72; margin:.15rem 0 0 0; font-size:.98rem;}
/* ---------- herói da página inicial ---------- */
.siap-heroi {border-radius:22px; padding:1.6rem 1.8rem; color:#fff;
  background:linear-gradient(120deg, #5552d9 0%, #6d6af0 45%, #2a9bd6 100%);
  box-shadow:0 10px 30px rgba(85,82,217,.25);}
.siap-heroi h2 {color:#fff; margin:0 0 .25rem 0; font-size:1.65rem;}
.siap-heroi p {color:rgba(255,255,255,.92); margin:0; font-size:1rem;}
/* ---------- cartões ---------- */
div[class*="st-key-cartao"] {transition: transform .15s ease, box-shadow .15s ease; border-radius:18px;}
div[class*="st-key-cartao"]:hover {transform: translateY(-2px); box-shadow:0 10px 24px rgba(29,33,64,.10);}
.siap-cartao-ic {font-size:1.7rem; line-height:1;}
.siap-cartao-tit {font-weight:650; font-size:1.05rem; margin:.45rem 0 .15rem 0;}
.siap-cartao-txt {opacity:.72; font-size:.9rem; min-height:2.6em;}
/* ---------- estado vazio ---------- */
.siap-vazio {text-align:center; padding:2.2rem 1rem; border:1.5px dashed rgba(127,127,160,.35); border-radius:18px;}
.siap-vazio .ic {font-size:2.4rem;}
.siap-vazio .tit {font-weight:650; font-size:1.1rem; margin:.4rem 0 .2rem;}
.siap-vazio .txt {opacity:.72;}
/* ---------- passos (stepper) ---------- */
.siap-passos {display:flex; gap:.5rem; flex-wrap:wrap; margin:.4rem 0 .8rem;}
.siap-passo {padding:.35rem .8rem; border-radius:999px; font-size:.85rem; border:1px solid rgba(127,127,160,.3);}
.siap-passo.ok {background:rgba(27,175,122,.14); border-color:rgba(27,175,122,.45);}
.siap-passo.atual {background:rgba(85,82,217,.14); border-color:rgba(85,82,217,.55); font-weight:600;}
/* ---------- métricas ---------- */
div[data-testid="stMetric"] {padding:.2rem .1rem;}
/* ---------- rodapé ---------- */
.siap-rodape {opacity:.6; font-size:.8rem; text-align:center; margin-top:2rem;}
</style>
"""


def aplicar_estilo() -> None:
    st.html(CSS)


def iniciar_pagina(titulo: str, descricao: str = "", icone: str = "", ajuda: list[str] | None = None) -> None:
    """Cabeçalho padrão: ícone + título + descrição, botão “Como usar” e mensagem de sucesso pendente."""
    exigir_acesso()  # redundante com app.py, mas protege caso a página seja aberta isoladamente
    col_tit, col_ajuda = st.columns([5, 1], vertical_alignment="center")
    with col_tit:
        st.html(
            f'<div class="siap-cab"><div class="ic">{icone or "🧠"}</div><h1>{titulo}</h1></div>'
            + (f'<p class="siap-sub">{descricao}</p>' if descricao else "")
        )
    if ajuda:
        with col_ajuda.popover("Como usar", icon=":material/help:", use_container_width=True):
            for i, passo in enumerate(ajuda, start=1):
                st.markdown(f"**{i}.** {passo}")
    mensagem = st.session_state.pop("_mensagem_ok", None)
    if mensagem:
        st.toast(mensagem, icon=":material/check_circle:")
        st.success(mensagem, icon=":material/check_circle:")


def cartao_acao(chave: str, icone: str, titulo: str, texto: str, pagina: str, rotulo: str = "Abrir") -> None:
    """Cartão clicável que leva a outra página."""
    with st.container(border=True, key=f"cartao_{chave}"):
        st.html(f'<div class="siap-cartao-ic">{icone}</div><div class="siap-cartao-tit">{titulo}</div>'
                f'<div class="siap-cartao-txt">{texto}</div>')
        st.page_link(pagina, label=rotulo, icon=":material/arrow_forward:")


def estado_vazio(icone: str, titulo: str, texto: str, pagina: str | None = None, rotulo: str = "") -> None:
    st.html(f'<div class="siap-vazio"><div class="ic">{icone}</div><div class="tit">{titulo}</div>'
            f'<div class="txt">{texto}</div></div>')
    if pagina:
        st.page_link(pagina, label=rotulo, icon=":material/arrow_forward:")


def passos(etapas: list[tuple[str, str]]) -> None:
    """Indicador de etapas. etapas = [(rótulo, 'ok'|'atual'|'')]."""
    itens = "".join(f'<span class="siap-passo {estado}">{"✓ " if estado == "ok" else ""}{rotulo}</span>'
                    for rotulo, estado in etapas)
    st.html(f'<div class="siap-passos">{itens}</div>')


def executar(acao, mensagem_ok: str, ao_concluir=None) -> None:
    """Executa `acao(sessao)` numa transação. Erro de validação → mensagem; sucesso → recarrega a página."""
    try:
        with transacao() as s:
            resultado = acao(s)
            if ao_concluir is not None:
                ao_concluir(resultado)
    except ErroValidacao as erro:
        st.error(str(erro))
        return
    st.session_state["_mensagem_ok"] = mensagem_ok
    st.rerun()


def data_br(valor) -> str:
    """Data/hora no formato brasileiro (horário de Brasília); vazio vira '—'."""
    if valor is None:
        return "—"
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")


def exigir_acesso() -> None:
    """Se APP_PASSWORD estiver nos secrets, exige a senha antes de mostrar qualquer dado."""
    senha = _segredo("APP_PASSWORD")
    if not senha or st.session_state.get("_autenticado"):
        return
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        st.html('<div style="text-align:center;margin-top:3rem"><img src="app/static/icone.svg" width="64">'
                '<h2 style="margin:.6rem 0 0">SIAP-IA</h2>'
                '<p style="opacity:.7">Sistema Inteligente de Avaliação Psicológica</p></div>')
        with st.form("login"):
            digitada = st.text_input("Senha de acesso", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        if hmac.compare_digest(digitada.encode(), senha.encode()):
            st.session_state["_autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


def selo(situacao: satepsi.Situacao) -> str:
    cor = "green" if situacao.liberado else CORES.get(situacao.status, "gray")
    extra = " · vencida" if situacao.vencida else ""
    return f":{cor}-badge[{situacao.rotulo}{extra}]"


def rodape() -> None:
    st.html(f'<div class="siap-rodape">🔒 {AVISO}</div>')
