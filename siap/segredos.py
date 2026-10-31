"""Segredos digitados no próprio app (ex.: chave da API do Claude).

- Cifrados com Fernet (AES-128-CBC + HMAC) usando chave derivada por scrypt da senha do app (APP_PASSWORD,
  ou SIAP_CHAVE_MESTRA se definida). Sem essa senha nos Secrets, nada é guardado.
- Nunca aparecem inteiros na tela, nem vão para backup, auditoria ou logs (só os últimos 4 caracteres).
- Se a senha do app mudar, o segredo antigo fica ilegível: basta colar de novo.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .catalogo import ErroValidacao, auditar
from .models import SegredoCifrado, agora_utc

CHAVE_ANTHROPIC = "anthropic_api_key"


def senha_mestra() -> str | None:
    for nome in ("SIAP_CHAVE_MESTRA", "APP_PASSWORD"):
        valor = os.environ.get(nome)
        if valor:
            return valor
    try:
        import streamlit as st

        return st.secrets.get("SIAP_CHAVE_MESTRA") or st.secrets.get("APP_PASSWORD")
    except Exception:
        return None


def _fernet(senha: str, sal: bytes) -> Fernet:
    derivada = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=2**14, r=8, p=1, dklen=32)
    return Fernet(base64.urlsafe_b64encode(derivada))


@dataclass(frozen=True)
class Estado:
    existe: bool
    legivel: bool
    final: str = ""
    atualizado_em: datetime | None = None

    @property
    def mascarado(self) -> str:
        return f"••••••••{self.final}" if self.final else ""


def salvar(s: Session, nome: str, valor: str, senha: str | None = None) -> None:
    senha = senha or senha_mestra()
    if not senha:
        raise ErroValidacao(
            "Para guardar a chave com segurança, defina a senha do app (APP_PASSWORD) nos Secrets do Streamlit."
        )
    valor = (valor or "").strip()
    if not valor:
        raise ErroValidacao("Cole a chave.")
    sal = os.urandom(16)
    cifrado = _fernet(senha, sal).encrypt(valor.encode("utf-8")).decode("ascii")
    registro = s.get(SegredoCifrado, nome)
    if registro is None:
        registro = SegredoCifrado(nome=nome)
        s.add(registro)
    registro.cifrado, registro.sal, registro.final = cifrado, sal.hex(), valor[-4:]
    registro.atualizado_em = agora_utc()
    auditar(s, "salvar_segredo", "segredo", None, nome=nome)


def ler(s: Session, nome: str, senha: str | None = None) -> str | None:
    registro = s.get(SegredoCifrado, nome)
    senha = senha or senha_mestra()
    if registro is None or not senha:
        return None
    try:
        return _fernet(senha, bytes.fromhex(registro.sal)).decrypt(registro.cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def estado(s: Session, nome: str, senha: str | None = None) -> Estado:
    registro = s.get(SegredoCifrado, nome)
    if registro is None:
        return Estado(False, False)
    return Estado(True, ler(s, nome, senha) is not None, registro.final, registro.atualizado_em)


def remover(s: Session, nome: str) -> None:
    registro = s.get(SegredoCifrado, nome)
    if registro is not None:
        s.delete(registro)
        s.flush()
        auditar(s, "remover_segredo", "segredo", None, nome=nome)


def normalizar_chave_anthropic(texto: str) -> str:
    """Limpa o que costuma vir junto ao colar (espaços, aspas, 'ANTHROPIC_API_KEY =')."""
    chave = (texto or "").strip()
    if "=" in chave and chave.split("=", 1)[0].strip().upper() == "ANTHROPIC_API_KEY":
        chave = chave.split("=", 1)[1].strip()
    chave = chave.strip().strip('"').strip("'").strip()
    if not chave.startswith("sk-ant-") or len(chave) < 20 or any(c.isspace() for c in chave):
        raise ErroValidacao("Isso não parece uma chave da API do Claude (ela começa com “sk-ant-”).")
    return chave
