"""Conexão com o banco. SQLite em desenvolvimento/testes; PostgreSQL (ex.: Neon) na nuvem."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.orm import Session, sessionmaker


PASTA_MIGRACOES = Path(__file__).resolve().parent / "migracoes"

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


class ConfiguracaoBancoInvalida(RuntimeError):
    """DATABASE_URL ausente, malformada ou banco inacessível (mensagem sem expor a senha)."""


_AJUDA = (
    "Confira o segredo DATABASE_URL no painel do Streamlit (Manage app → Settings → Secrets): "
    "ele deve conter a connection string copiada do Neon, no formato "
    '"postgresql://usuario:senha@ep-xxxx.região.aws.neon.tech/neondb?sslmode=require".'
)


def validar_url(url: str) -> None:
    """Recusa endereços obviamente inválidos antes de tentar conectar."""
    if url.startswith("sqlite"):
        return
    try:
        partes = make_url(url)
    except ArgumentError:
        raise ConfiguracaoBancoInvalida("O endereço do banco (DATABASE_URL) não está num formato válido. " + _AJUDA)
    host = partes.host or ""
    if (not partes.drivername.startswith("postgresql") or not host or "." not in host
            or ".." in host or host.startswith(".") or " " in url or not partes.username):
        raise ConfiguracaoBancoInvalida(
            "O endereço do banco (DATABASE_URL) parece ser o texto de exemplo ou está incompleto. " + _AJUDA
        )


def normalizar_url(url: str) -> str:
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo):]
    return url


def criar_engine(url: str) -> Engine:
    validar_url(url)
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
    try:
        migrar(engine)
    except OperationalError as erro:
        engine.dispose()
        raise ConfiguracaoBancoInvalida(
            "Não foi possível conectar ao banco de dados. Verifique se a connection string está completa "
            "e se o projeto no Neon está ativo. " + _AJUDA
        ) from erro
    return engine


def configuracao_alembic():
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(PASTA_MIGRACOES))
    return cfg


def migrar(engine: Engine) -> None:
    """Atualiza o esquema do banco até a última migração (Alembic). Seguro de repetir."""
    from alembic import command

    cfg = configuracao_alembic()
    with engine.begin() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, "head")


def fabrica_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
