"""Conexão com o banco. SQLite em desenvolvimento/testes; PostgreSQL (ex.: Neon) na nuvem."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

SQLITE_PADRAO = "sqlite:///data/siap.db"


def database_url() -> str:
    """Ordem: variável de ambiente DATABASE_URL → secrets do Streamlit → SQLite local."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("DATABASE_URL")
        except Exception:  # sem secrets.toml: segue para o padrão
            url = None
    return normalizar_url(url or SQLITE_PADRAO)


def normalizar_url(url: str) -> str:
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo):]
    return url


def criar_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        caminho = url.split("///", 1)[-1]
        if caminho and caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _ativar_chaves_estrangeiras(conexao, _registro):
            conexao.execute("PRAGMA foreign_keys=ON")
    else:
        engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def fabrica_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
