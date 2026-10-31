"""Estatística de pesquisa (pós-MVP C): descritivas, TCT (alfa, ômega, análise de itens), AFE e TRI.

- Opera sobre conjuntos de dados ANONIMIZADOS importados pela pesquisadora (CSV/XLSX), nunca sobre
  normas ou chaves de testes comerciais (CLAUDE.md, regra 5).
- Tudo aqui é "calculado pelo sistema" com rotinas determinísticas; os pressupostos e limites de cada
  análise são devolvidos junto com os resultados (alertas).
- Validação: os testes recuperam parâmetros conhecidos de dados simulados (tests/test_estatistica.py).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from . import avaliacoes as av
from .catalogo import ErroValidacao

TAMANHO_MAX = 5 * 1024 * 1024
_COLUNAS_PROIBIDAS = re.compile(
    r"(^|[_\s.-])(nome|name|cpf|rg|e-?mail|telefone|celular|fone|whats|endere[cç]o|cep|nascimento|"
    r"data_?nasc|dt_?nasc|matr[ií]cula|cns|sus)([_\s.-]|$)", re.I)


# ------------------------------------------------------------- importação

def ler_arquivo(conteudo: bytes, nome_arquivo: str) -> pd.DataFrame:
    if len(conteudo) > TAMANHO_MAX:
        raise ErroValidacao("Arquivo maior que 5 MB.")
    nome = nome_arquivo.lower()
    try:
        if nome.endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(conteudo))
        elif nome.endswith((".csv", ".txt")):
            texto = conteudo.decode("utf-8-sig", errors="replace")
            primeira = texto.splitlines()[0] if texto else ""
            sep = ";" if primeira.count(";") > primeira.count(",") else ","
            df = pd.read_csv(io.StringIO(texto), sep=sep, decimal="," if sep == ";" else ".")
        else:
            raise ErroValidacao("Use arquivo .csv ou .xlsx.")
    except ErroValidacao:
        raise
    except Exception as erro:  # arquivo corrompido ou em formato inesperado
        raise ErroValidacao(f"Não foi possível ler o arquivo: {erro}") from erro
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) < 1:
        raise ErroValidacao("O arquivo não tem dados.")
    if len(set(df.columns)) != len(df.columns):
        raise ErroValidacao("Há colunas com nomes repetidos.")
    return df


def verificar_anonimizacao(df: pd.DataFrame) -> None:
    """Recusa colunas com nome de identificador e valores com padrão de CPF/e-mail/telefone."""
    suspeitas = [c for c in df.columns if _COLUNAS_PROIBIDAS.search(c)]
    if suspeitas:
        raise ErroValidacao("O arquivo parece conter dados de identificação (colunas: " + ", ".join(suspeitas)
                            + "). Remova-as e use apenas códigos.")
    for coluna in [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]:
        amostra = " ".join(df[coluna].dropna().astype(str).head(500))
        try:
            av.verificar_sem_identificadores(amostra)
        except ErroValidacao:
            raise ErroValidacao(f"A coluna “{coluna}” parece conter CPF, e-mail ou telefone. Anonimize antes de importar.")


def colunas_numericas(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and df[c].notna().sum() > 0]


# ------------------------------------------------------------ descritivas

def descritivas(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    linhas = []
    for c in colunas:
        x = pd.to_numeric(df[c], errors="coerce")
        v = x.dropna()
        linhas.append({
            "Variável": c, "N válido": int(v.size), "Ausentes (%)": round(100 * (1 - v.size / len(x)), 1) if len(x) else 0.0,
            "Média": v.mean(), "DP": v.std(ddof=1), "Mediana": v.median(), "Mínimo": v.min(), "Máximo": v.max(),
            "Assimetria": v.skew(), "Curtose": v.kurt(),
        })
    return pd.DataFrame(linhas)


def frequencias(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    contagem = df[coluna].value_counts(dropna=False).sort_index()
    total = contagem.sum()
    return pd.DataFrame({"Valor": contagem.index.astype(str), "Frequência": contagem.values,
                         "%": (100 * contagem.values / total).round(1)})


# ------------------------------------------------------------------- TCT

def _itens(df: pd.DataFrame, colunas: list[str], minimo: int = 2) -> tuple[pd.DataFrame, list[str]]:
    if len(colunas) < minimo:
        raise ErroValidacao(f"Selecione ao menos {minimo} itens.")
    dados = df[colunas].apply(pd.to_numeric, errors="coerce")
    completo = dados.dropna()
    alertas = []
    excluidos = len(dados) - len(completo)
    if excluidos:
        alertas.append(f"{excluidos} caso(s) com dados ausentes foram excluídos (exclusão listwise).")
    if len(completo) < 3:
        raise ErroValidacao("Casos completos insuficientes para a análise.")
    constantes = [c for c in colunas if completo[c].std(ddof=1) == 0]
    if constantes:
        raise ErroValidacao("Itens sem variabilidade: " + ", ".join(constantes) + ". Remova-os da seleção.")
    return completo, alertas


def _alfa(x: np.ndarray) -> float:
    k = x.shape[1]
    var_itens = x.var(axis=0, ddof=1).sum()
    var_total = x.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - var_itens / var_total))


@dataclass
class ResultadoPrecisao:
    n: int
    k: int
    alfa: float
    alfa_ic95: tuple[float, float]
    alfa_padronizado: float
    omega: float | None
    itens: pd.DataFrame
    alertas: list[str] = field(default_factory=list)


def precisao(df: pd.DataFrame, colunas: list[str]) -> ResultadoPrecisao:
    dados, alertas = _itens(df, colunas)
    x = dados.to_numpy(dtype=float)
    n, k = x.shape
    alfa = _alfa(x)
    # IC 95% de Feldt (1965)
    gl1, gl2 = n - 1, (n - 1) * (k - 1)
    ic = (1 - (1 - alfa) * stats.f.ppf(0.975, gl1, gl2), 1 - (1 - alfa) * stats.f.ppf(0.025, gl1, gl2))
    r = np.corrcoef(x, rowvar=False)
    r_media = (r.sum() - k) / (k * (k - 1))
    alfa_pad = float(k * r_media / (1 + (k - 1) * r_media))

    total = x.sum(axis=1)
    dicotomico = set(np.unique(x)) <= {0.0, 1.0}
    linhas = []
    for j, nome in enumerate(colunas):
        resto = total - x[:, j]
        linha = {"Item": nome, "Média": x[:, j].mean(), "DP": x[:, j].std(ddof=1),
                 "r item-total corrigida": float(np.corrcoef(x[:, j], resto)[0, 1]),
                 "Alfa se excluído": _alfa(np.delete(x, j, axis=1)) if k > 2 else np.nan}
        if dicotomico:
            linha["Dificuldade (p)"] = x[:, j].mean()
        linhas.append(linha)
    itens = pd.DataFrame(linhas)

    omega = None
    if k >= 3:
        try:
            omega = omega_mcdonald(dados)
        except Exception:  # convergência
            alertas.append("Não foi possível estimar o ômega (modelo de um fator não convergiu).")
    else:
        alertas.append("Ômega exige ao menos 3 itens.")

    fracos = itens.loc[itens["r item-total corrigida"] < 0.30, "Item"].tolist()
    if fracos:
        alertas.append("Itens com correlação item-total corrigida < 0,30 (examinar): " + ", ".join(fracos) + ".")
    negativos = itens.loc[itens["r item-total corrigida"] < 0, "Item"].tolist()
    if negativos:
        alertas.append("Correlação item-total negativa (item invertido não recodificado?): " + ", ".join(negativos) + ".")
    if n < 100:
        alertas.append(f"Amostra pequena (n = {n}): estimativas de precisão instáveis.")
    alertas.append("O alfa pressupõe tau-equivalência e unidimensionalidade; o ômega (1 fator) é preferível "
                   "quando as cargas diferem. Verifique a dimensionalidade com a AFE.")
    return ResultadoPrecisao(n, k, alfa, ic, alfa_pad, omega, itens, alertas)


def omega_mcdonald(dados: pd.DataFrame) -> float:
    """Ômega total a partir de um modelo de um fator (eixos principais) sobre a matriz de correlações."""
    cargas, _, _ = eixos_principais(np.corrcoef(dados.to_numpy(dtype=float), rowvar=False), 1)
    cargas = cargas[:, 0]
    unicidades = 1 - cargas ** 2
    soma = cargas.sum()
    return float(soma ** 2 / (soma ** 2 + unicidades.sum()))


# ------------------------------------------------------------------- AFE

def kmo(r: np.ndarray) -> tuple[float, np.ndarray]:
    """Kaiser-Meyer-Olkin geral e por item."""
    inv = np.linalg.inv(r)
    parcial = -inv / np.sqrt(np.outer(np.diag(inv), np.diag(inv)))
    np.fill_diagonal(parcial, 0)
    r2 = r.copy()
    np.fill_diagonal(r2, 0)
    r2, p2 = r2 ** 2, parcial ** 2
    por_item = r2.sum(0) / (r2.sum(0) + p2.sum(0))
    return float(r2.sum() / (r2.sum() + p2.sum())), por_item


def bartlett(r: np.ndarray, n: int) -> tuple[float, float]:
    p = r.shape[0]
    _, logdet = np.linalg.slogdet(r)
    qui2 = -(n - 1 - (2 * p + 5) / 6) * logdet
    gl = p * (p - 1) / 2
    return float(qui2), float(stats.chi2.sf(qui2, gl))


def eixos_principais(r: np.ndarray, m: int, max_iter: int = 500, tol: float = 1e-6) -> tuple[np.ndarray, np.ndarray, bool]:
    """Extração por eixos principais iterada (comunalidades iniciais = SMC).

    Devolve (cargas não rotacionadas, comunalidades, houve_heywood).
    """
    h2 = 1 - 1 / np.diag(np.linalg.inv(r))
    heywood = False
    for _ in range(max_iter):
        rr = r.copy()
        np.fill_diagonal(rr, h2)
        valores, vetores = np.linalg.eigh(rr)
        ordem = np.argsort(valores)[::-1][:m]
        cargas = vetores[:, ordem] * np.sqrt(np.clip(valores[ordem], 0, None))
        novo = (cargas ** 2).sum(1)
        if np.any(novo > 0.995):
            heywood = True
            novo = np.clip(novo, None, 0.995)
        if np.max(np.abs(novo - h2)) < tol:
            h2 = novo
            break
        h2 = novo
    sinais = np.sign(cargas.sum(0))
    sinais[sinais == 0] = 1
    return cargas * sinais, (cargas ** 2).sum(1), heywood


def varimax(cargas: np.ndarray, max_iter: int = 500, tol: float = 1e-8) -> tuple[np.ndarray, np.ndarray]:
    """Varimax com normalização de Kaiser. Devolve (cargas rotacionadas, matriz de rotação)."""
    h = np.sqrt((cargas ** 2).sum(1))
    a = cargas / h[:, None]
    p, k = a.shape
    rot, d = np.eye(k), 0.0
    for _ in range(max_iter):
        lam = a @ rot
        u, s, vh = np.linalg.svd(a.T @ (lam ** 3 - lam @ np.diag((lam ** 2).sum(0)) / p))
        rot, d_ant, d = u @ vh, d, s.sum()
        if d_ant and d / d_ant < 1 + tol:
            break
    return (a @ rot) * h[:, None], rot


def promax(cargas: np.ndarray, potencia: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Promax (como stats::promax do R). Devolve (matriz-padrão, correlações entre fatores)."""
    vmx, _ = varimax(cargas)
    alvo = vmx * np.abs(vmx) ** (potencia - 1)
    u = np.linalg.lstsq(vmx, alvo, rcond=None)[0]
    d = np.diag(np.linalg.inv(u.T @ u))
    u = u @ np.diag(np.sqrt(d))
    padrao = vmx @ u
    phi = np.linalg.inv(u.T @ u)
    return padrao, phi


@dataclass
class ResultadoAFE:
    n: int
    kmo_geral: float
    kmo_itens: pd.DataFrame
    bartlett_qui2: float
    bartlett_p: float
    autovalores: pd.DataFrame
    sugestao_kaiser: int
    sugestao_paralela: int
    cargas: pd.DataFrame
    variancia: pd.DataFrame
    correlacoes_fatores: pd.DataFrame | None
    alertas: list[str] = field(default_factory=list)


def analise_paralela(n: int, k: int, iteracoes: int = 100, semente: int = 2026) -> np.ndarray:
    """Percentil 95 dos autovalores de matrizes de correlação de dados aleatórios (Horn, 1965)."""
    rng = np.random.default_rng(semente)
    autov = np.empty((iteracoes, k))
    for i in range(iteracoes):
        aleatorio = rng.standard_normal((n, k))
        autov[i] = np.sort(np.linalg.eigvalsh(np.corrcoef(aleatorio, rowvar=False)))[::-1]
    return np.percentile(autov, 95, axis=0)


ROTACOES = {"promax": "Promax (oblíqua)", "varimax": "Varimax (ortogonal)", "nenhuma": "Sem rotação"}


def afe(df: pd.DataFrame, colunas: list[str], n_fatores: int | None = None, rotacao: str = "promax") -> ResultadoAFE:
    dados, alertas = _itens(df, colunas, minimo=3)
    x = dados.to_numpy(dtype=float)
    n, k = x.shape
    r = np.corrcoef(x, rowvar=False)
    if np.linalg.matrix_rank(r) < k:
        raise ErroValidacao("A matriz de correlações é singular (itens redundantes ou combinação linear de outros).")
    qui2, p = bartlett(r, n)
    kmo_geral, kmo_itens = kmo(r)
    autov = np.sort(np.linalg.eigvalsh(r))[::-1]
    paralela = analise_paralela(n, k)
    kaiser = int((autov > 1).sum())
    sug_paralela = 0
    for observado, aleatorio in zip(autov, paralela):
        if observado <= aleatorio:
            break
        sug_paralela += 1
    sug_paralela = max(sug_paralela, 1)
    n_fatores = n_fatores or sug_paralela
    if not 1 <= n_fatores < k:
        raise ErroValidacao(f"Número de fatores deve estar entre 1 e {k - 1}.")
    if rotacao not in ROTACOES:
        raise ErroValidacao("Rotação inválida.")

    cargas_brutas, comunalidades, heywood = eixos_principais(r, n_fatores)
    phi = None
    if n_fatores == 1 or rotacao == "nenhuma":
        final = cargas_brutas
    elif rotacao == "varimax":
        final, _ = varimax(cargas_brutas)
    else:
        final, phi = promax(cargas_brutas)
    nomes = [f"F{i + 1}" for i in range(n_fatores)]
    cargas = pd.DataFrame(final, columns=nomes)
    cargas.insert(0, "Item", colunas)
    cargas["Comunalidade"] = comunalidades
    ss = (final ** 2).sum(0)
    variancia = pd.DataFrame({"Fator": nomes, "Soma dos quadrados das cargas": ss, "Proporção": ss / k,
                              "Acumulada": np.cumsum(ss / k)})
    correlacoes = pd.DataFrame(phi, index=nomes, columns=nomes) if phi is not None else None

    if kmo_geral < 0.6:
        alertas.append(f"KMO = {kmo_geral:.2f} (< 0,60): adequação amostral baixa para fatoração.")
    if p >= 0.05:
        alertas.append("Teste de Bartlett não significativo: as correlações podem não justificar a fatoração.")
    if n < 200 or n / k < 5:
        alertas.append(f"Amostra n = {n} para {k} itens ({n / k:.1f} casos/item): resultados podem ser instáveis.")
    if heywood:
        alertas.append("Caso Heywood (comunalidade ≈ 1): reveja o número de fatores ou os itens.")
    if n_fatores != sug_paralela:
        alertas.append(f"A análise paralela sugere {sug_paralela} fator(es); foram extraídos {n_fatores}.")
    sem_carga = cargas.loc[(cargas[nomes].abs() < 0.30).all(axis=1), "Item"].tolist()
    if sem_carga:
        alertas.append("Itens sem carga ≥ 0,30 em nenhum fator: " + ", ".join(sem_carga) + ".")
    if rotacao == "promax" and n_fatores > 1:
        alertas.append("Rotação oblíqua: as cargas exibidas são da matriz-padrão; a variância por fator não é aditiva.")
    alertas.append("A AFE descreve a estrutura desta amostra; confirme-a em amostra independente (AFC).")
    return ResultadoAFE(
        n, kmo_geral, pd.DataFrame({"Item": colunas, "KMO": kmo_itens}), qui2, p,
        pd.DataFrame({"Componente": range(1, k + 1), "Autovalor observado": autov, "Paralela (P95)": paralela}),
        kaiser, sug_paralela, cargas, variancia, correlacoes, alertas,
    )


# ------------------------------------------------------------------- TRI

@dataclass
class ResultadoTRI:
    modelo: str
    n: int
    parametros: pd.DataFrame
    alertas: list[str] = field(default_factory=list)


def tri(df: pd.DataFrame, colunas: list[str], modelo: str = "2PL") -> ResultadoTRI:
    import girth

    dados, alertas = _itens(df, colunas, minimo=3)
    x = dados.to_numpy(dtype=float)
    if not np.all(np.mod(x, 1) == 0):
        raise ErroValidacao("A TRI exige respostas inteiras (categorias).")
    n = x.shape[0]
    if modelo == "2PL":
        if not set(np.unique(x)) <= {0.0, 1.0}:
            raise ErroValidacao("O modelo 2PL exige itens dicotômicos (0 = erro, 1 = acerto).")
        resultado = girth.twopl_mml(x.T.astype(int))
        a, b = resultado["Discrimination"], resultado["Difficulty"]
        parametros = pd.DataFrame({"Item": colunas, "Discriminação (a)": a, "Dificuldade (b)": b})
    elif modelo == "GRM":
        valores = np.unique(x)
        if len(valores) < 3:
            raise ErroValidacao("O modelo de resposta graduada exige ao menos 3 categorias de resposta.")
        mapa = {v: i + 1 for i, v in enumerate(valores)}  # girth: categorias 1..K
        codificado = np.vectorize(mapa.get)(x).T.astype(int)
        resultado = girth.grm_mml(codificado)
        a, b = resultado["Discrimination"], np.atleast_2d(resultado["Difficulty"])
        parametros = pd.DataFrame({"Item": colunas, "Discriminação (a)": a})
        for j in range(b.shape[1]):
            parametros[f"Limiar b{j + 1}"] = b[:, j]
    else:
        raise ErroValidacao("Modelo inválido.")
    if n < 200:
        alertas.append(f"Amostra pequena para TRI (n = {n}); recomenda-se ao menos 200–500 casos.")
    baixos = parametros.loc[parametros["Discriminação (a)"] < 0.65, "Item"].tolist()
    if baixos:
        alertas.append("Itens com discriminação baixa (a < 0,65): " + ", ".join(baixos) + ".")
    alertas.append("A TRI unidimensional pressupõe um único traço latente e independência local; "
                   "verifique a dimensionalidade (AFE) antes de interpretar.")
    return ResultadoTRI(modelo, n, parametros, alertas)
