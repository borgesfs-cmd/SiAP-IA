"""Utilidades de interface (Streamlit) compartilhadas pelas páginas."""

from __future__ import annotations

import hmac
from contextlib import contextmanager
from datetime import datetime, timezone

import streamlit as st

from . import satepsi
from .catalogo import FUSO
from .db import criar_engine, database_url, fabrica_sessoes
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
        carregar_inventario_inicial(s)
    return fabrica


@contextmanager
def transacao():
    """Sessão com commit automático ao final (ou rollback em caso de erro)."""
    with _fabrica(database_url()).begin() as s:
        yield s


def iniciar_pagina(titulo: str) -> None:
    exigir_acesso()  # redundante com app.py, mas protege caso a página seja aberta isoladamente
    st.title(titulo)


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
    st.title("SIAP-IA")
    with st.form("login"):
        digitada = st.text_input("Senha de acesso", type="password")
        entrar = st.form_submit_button("Entrar")
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
    st.divider()
    st.caption(AVISO)
