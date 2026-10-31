"""Restauração de backup (arquivo JSON gerado por catalogo.exportar_backup).

Segurança:
- Valida formato, versão e tabelas ANTES de apagar qualquer coisa; tudo ocorre numa única transação
  (se algo falhar, nada muda).
- Substitui TODO o conteúdo do banco pelo do arquivo. A chave da API (segredos_cifrados) não está no
  backup e é preservada.
- Recomenda-se baixar um backup do estado atual antes de restaurar (a tela faz isso).
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, LargeBinary, delete, func, insert, select, text
from sqlalchemy.orm import Session

from .catalogo import ErroValidacao, auditar
from .models import Base

PRESERVADAS = {"segredos_cifrados"}
VERSOES_ACEITAS = {2}


def _tabelas():
    return [t for t in Base.metadata.sorted_tables if t.name not in PRESERVADAS]


def ler_arquivo(conteudo: bytes) -> dict:
    try:
        dados = json.loads(conteudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as erro:
        raise ErroValidacao("O arquivo não é um backup válido do SIAP-IA (JSON ilegível).") from erro
    validar(dados)
    return dados


def validar(dados: dict) -> None:
    if not isinstance(dados, dict) or dados.get("formato") != "siap-ia-backup":
        raise ErroValidacao("O arquivo não é um backup do SIAP-IA.")
    if dados.get("versao_formato") not in VERSOES_ACEITAS:
        raise ErroValidacao("Versão de backup não suportada. Gere um backup novo pela versão atual do sistema.")
    faltando = [t.name for t in _tabelas() if t.name not in dados]
    # tabelas criadas depois do backup podem faltar (ficam vazias); mas o núcleo precisa existir
    nucleo = {"instrumentos", "versoes_instrumento", "verificacoes_satepsi", "auditoria"}
    if nucleo & set(faltando):
        raise ErroValidacao("Backup incompleto: faltam tabelas essenciais (" + ", ".join(sorted(nucleo & set(faltando))) + ").")
    for t in _tabelas():
        if t.name in dados and not isinstance(dados[t.name], list):
            raise ErroValidacao(f"Tabela {t.name} malformada no backup.")


def resumo(dados: dict) -> dict[str, int]:
    return {t.name: len(dados.get(t.name, [])) for t in _tabelas()}


def _converter(coluna, valor):
    if valor is None:
        return None
    tipo = coluna.type
    if isinstance(tipo, LargeBinary):
        return base64.b64decode(valor["base64"]) if isinstance(valor, dict) else None
    if isinstance(tipo, DateTime):
        return datetime.fromisoformat(valor)
    if isinstance(tipo, Date):
        return date.fromisoformat(valor)
    if isinstance(tipo, Boolean):
        return valor if isinstance(valor, bool) else str(valor).lower() in ("1", "true", "t")
    if isinstance(tipo, Integer):
        return int(valor)
    return valor


def restaurar(s: Session, dados: dict) -> dict[str, int]:
    """Substitui o conteúdo do banco pelo backup. Retorna a contagem restaurada por tabela."""
    validar(dados)
    tabelas = _tabelas()
    for tabela in reversed(tabelas):
        s.execute(delete(tabela))
    contagem = {}
    for tabela in tabelas:
        linhas = []
        for registro in dados.get(tabela.name, []):
            linhas.append({c.name: _converter(c, registro.get(c.name)) for c in tabela.columns if c.name in registro})
        if linhas:
            s.execute(insert(tabela), linhas)
        contagem[tabela.name] = len(linhas)
    s.flush()
    if s.bind.dialect.name == "postgresql":  # ajusta as sequências dos ids
        for tabela in tabelas:
            pk = list(tabela.primary_key.columns)
            if len(pk) == 1 and isinstance(pk[0].type, Integer) and pk[0].autoincrement in (True, "auto"):
                maximo = s.scalar(select(func.max(pk[0]))) or 0
                s.execute(text("SELECT setval(pg_get_serial_sequence(:t, :c), :v, :chamado)"),
                          {"t": tabela.name, "c": pk[0].name, "v": max(maximo, 1), "chamado": maximo > 0})
    auditar(s, "restaurar_backup", "sistema", None, gerado_em=dados.get("gerado_em"),
            registros=sum(contagem.values()))
    return contagem
