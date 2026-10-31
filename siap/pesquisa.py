"""Conjuntos de dados de pesquisa: importar (com checagem de anonimização), listar, carregar e remover."""

from __future__ import annotations

import hashlib
import io

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from . import estatistica as es
from .catalogo import ErroValidacao, _txt, auditar
from .models import ConjuntoDados


def importar(s: Session, *, nome: str, conteudo: bytes, nome_arquivo: str, descricao: str = "") -> ConjuntoDados:
    nome = _txt(nome)
    if not nome:
        raise ErroValidacao("Dê um nome ao conjunto de dados.")
    if s.scalar(select(ConjuntoDados.id).where(func.lower(ConjuntoDados.nome) == nome.lower())):
        raise ErroValidacao(f"Já existe um conjunto chamado {nome!r}.")
    df = es.ler_arquivo(conteudo, nome_arquivo)
    es.verificar_anonimizacao(df)
    csv = df.to_csv(index=False)
    conjunto = ConjuntoDados(
        nome=nome, descricao=_txt(descricao), arquivo_original=nome_arquivo[:200], conteudo_csv=csv,
        n_linhas=len(df), n_colunas=len(df.columns), sha256=hashlib.sha256(csv.encode("utf-8")).hexdigest(),
    )
    s.add(conjunto)
    s.flush()
    auditar(s, "importar_conjunto_dados", "conjunto_dados", conjunto.id, nome=nome, linhas=len(df),
            colunas=len(df.columns), sha256=conjunto.sha256)
    return conjunto


def listar(s: Session) -> list[ConjuntoDados]:
    return list(s.scalars(select(ConjuntoDados).order_by(ConjuntoDados.criado_em.desc())))


def carregar(s: Session, conjunto_id: int) -> pd.DataFrame:
    conjunto = s.scalar(select(ConjuntoDados).options(undefer(ConjuntoDados.conteudo_csv))
                        .where(ConjuntoDados.id == conjunto_id))
    if conjunto is None:
        raise ErroValidacao("Conjunto de dados não encontrado.")
    return pd.read_csv(io.StringIO(conjunto.conteudo_csv))


def remover(s: Session, conjunto_id: int) -> None:
    conjunto = s.get(ConjuntoDados, conjunto_id)
    if conjunto is None:
        raise ErroValidacao("Conjunto de dados não encontrado.")
    auditar(s, "remover_conjunto_dados", "conjunto_dados", conjunto_id, nome=conjunto.nome, sha256=conjunto.sha256)
    s.delete(conjunto)
    s.flush()


def criar_exemplo(s: Session, semente: int = 2026) -> ConjuntoDados:
    """Conjunto SIMULADO (não são dados reais) para experimentar as análises: 300 casos,
    8 itens Likert 1–5 em dois fatores (E1–E4, A1–A4) e 6 itens dicotômicos (D1–D6)."""
    import numpy as np

    rng = np.random.default_rng(semente)
    n = 300
    fatores = rng.standard_normal((n, 2))
    fatores[:, 1] = 0.3 * fatores[:, 0] + np.sqrt(1 - 0.09) * fatores[:, 1]
    dados = {"codigo": [f"P{i + 1:03d}" for i in range(n)], "grupo": rng.choice(["A", "B"], n)}
    for f, prefixo in ((0, "E"), (1, "A")):
        for j in range(4):
            latente = 0.7 * fatores[:, f] + np.sqrt(1 - 0.49) * rng.standard_normal(n)
            dados[f"{prefixo}{j + 1}"] = np.digitize(latente, [-1.2, -0.4, 0.4, 1.2]) + 1
    theta = fatores[:, 0]
    for j, (a, b) in enumerate(zip([0.9, 1.1, 1.3, 1.5, 1.2, 1.0], [-1.5, -0.8, -0.2, 0.3, 0.9, 1.5])):
        dados[f"D{j + 1}"] = (rng.random(n) < 1 / (1 + np.exp(-a * (theta - b)))).astype(int)
    csv = pd.DataFrame(dados).to_csv(index=False).encode("utf-8")
    nome = "Exemplo simulado"
    sufixo = 2
    while s.scalar(select(ConjuntoDados.id).where(ConjuntoDados.nome == nome)):
        nome, sufixo = f"Exemplo simulado {sufixo}", sufixo + 1
    return importar(s, nome=nome, conteudo=csv, nome_arquivo="exemplo_simulado.csv",
                    descricao="Dados SIMULADOS para demonstração (não são pessoas reais).")
