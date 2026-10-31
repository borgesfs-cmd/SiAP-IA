"""Validação das rotinas estatísticas: recuperam parâmetros conhecidos de dados simulados
(critério de aceitação "resultados reproduzem bases de referência")."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from siap import catalogo
from siap import estatistica as es
from siap import pesquisa as pq

N = 3000


@pytest.fixture(scope="module")
def um_fator():
    rng = np.random.default_rng(7)
    cargas = np.array([0.8, 0.7, 0.6, 0.7, 0.5, 0.6])
    f = rng.standard_normal(N)
    x = np.outer(f, cargas) + rng.standard_normal((N, 6)) * np.sqrt(1 - cargas ** 2)
    return pd.DataFrame(x, columns=[f"i{j}" for j in range(6)]), cargas


@pytest.fixture(scope="module")
def dois_fatores():
    rng = np.random.default_rng(11)
    f = rng.standard_normal((N, 2))
    f[:, 1] = 0.4 * f[:, 0] + np.sqrt(1 - 0.16) * f[:, 1]
    lam = np.zeros((8, 2))
    lam[:4, 0] = lam[4:, 1] = 0.7
    x = f @ lam.T + rng.standard_normal((N, 8)) * np.sqrt(1 - 0.49)
    return pd.DataFrame(x, columns=[f"q{j}" for j in range(8)])


def test_alfa_formula_exata():
    # exemplo pequeno calculado à mão: k=3, variâncias dos itens 1, 1, 1; variância do total 7 → alfa = 1,5·(1−3/7)
    x = np.array([[1, 1, 1], [2, 2, 3], [3, 3, 2]], dtype=float)
    v_itens, v_total = x.var(axis=0, ddof=1).sum(), x.sum(1).var(ddof=1)
    assert es._alfa(x) == pytest.approx(1.5 * (1 - v_itens / v_total))


def test_omega_recupera_valor_teorico(um_fator):
    df, cargas = um_fator
    teorico = cargas.sum() ** 2 / (cargas.sum() ** 2 + (1 - cargas ** 2).sum())
    r = es.precisao(df, list(df.columns))
    assert r.omega == pytest.approx(teorico, abs=0.01)
    assert r.alfa <= r.omega + 0.005  # alfa ≤ ômega quando cargas diferem
    assert r.alfa_ic95[0] < r.alfa < r.alfa_ic95[1]
    assert (r.itens["r item-total corrigida"] > 0.3).all()


def test_afe_recupera_dois_fatores(dois_fatores):
    a = es.afe(dois_fatores, list(dois_fatores.columns))
    assert a.sugestao_paralela == 2 and a.kmo_geral > 0.7 and a.bartlett_p < 0.001
    cargas = a.cargas[["F1", "F2"]].to_numpy()
    principal = np.abs(cargas).max(axis=1)
    assert np.allclose(principal, 0.7, atol=0.06)
    # cada bloco de 4 itens carrega no mesmo fator
    dono = np.abs(cargas).argmax(axis=1)
    assert len(set(dono[:4])) == 1 and len(set(dono[4:])) == 1 and dono[0] != dono[4]
    assert a.correlacoes_fatores.iloc[0, 1] == pytest.approx(0.4, abs=0.08)


def test_varimax_preserva_comunalidades(dois_fatores):
    r = np.corrcoef(dois_fatores.to_numpy(), rowvar=False)
    brutas, h2, _ = es.eixos_principais(r, 2)
    rot, matriz = es.varimax(brutas)
    assert np.allclose((rot ** 2).sum(1), h2) and np.allclose(matriz.T @ matriz, np.eye(2))


def test_kmo_e_bartlett_em_dados_independentes():
    x = np.random.default_rng(3).standard_normal((500, 6))
    r = np.corrcoef(x, rowvar=False)
    assert es.kmo(r)[0] < 0.6 and es.bartlett(r, 500)[1] > 0.01


def test_tri_2pl_recupera_parametros():
    import girth.synthetic as gs

    a = np.array([0.8, 1.0, 1.2, 1.5, 1.8, 1.0])
    b = np.array([-1.5, -0.5, 0.0, 0.5, 1.0, 1.5])
    resp = gs.create_synthetic_irt_dichotomous(b, a, np.random.default_rng(5).standard_normal(N), seed=3)
    df = pd.DataFrame(resp.T, columns=[f"d{j}" for j in range(6)])
    t = es.tri(df, list(df.columns), "2PL")
    # tolerância ≈ 2 erros-padrão do item mais extremo e menos discriminativo (b = −1,5; a = 0,8)
    assert np.allclose(t.parametros["Dificuldade (b)"], b, atol=0.3)
    assert np.allclose(t.parametros["Discriminação (a)"], a, atol=0.3)


def test_tri_grm_roda_e_valida_categorias():
    rng = np.random.default_rng(9)
    theta = rng.standard_normal(800)
    x = np.column_stack([np.digitize(theta + rng.normal(0, 0.8, 800), [-1, 0, 1]) + 1 for _ in range(5)])
    df = pd.DataFrame(x, columns=[f"L{j}" for j in range(5)])
    t = es.tri(df, list(df.columns), "GRM")
    assert {"Limiar b1", "Limiar b2", "Limiar b3"} <= set(t.parametros.columns)
    assert (t.parametros["Discriminação (a)"] > 0.65).all()
    with pytest.raises(catalogo.ErroValidacao, match="dicotômicos"):
        es.tri(df, list(df.columns), "2PL")


def test_itens_constantes_e_poucos_casos_recusados():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 1, 1, 1], "c": [2, 3, 4, 5]})
    with pytest.raises(catalogo.ErroValidacao, match="variabilidade"):
        es.precisao(df, ["a", "b", "c"])
    with pytest.raises(catalogo.ErroValidacao):
        es.precisao(pd.DataFrame({"a": [1, None], "c": [2, 3]}), ["a", "c"])


def test_descritivas_e_ausentes():
    df = pd.DataFrame({"x": [1, 2, 3, None]})
    d = es.descritivas(df, ["x"]).iloc[0]
    assert d["N válido"] == 3 and d["Ausentes (%)"] == 25.0 and d["Média"] == 2.0


# ----------------------------------------------- importação e anonimização

def test_le_csv_com_ponto_e_virgula_e_decimal_virgula():
    df = es.ler_arquivo("id;escore\nP1;1,5\nP2;2,5\n".encode(), "dados.csv")
    assert df["escore"].tolist() == [1.5, 2.5]


@pytest.mark.parametrize("csv", [
    "codigo,nome,item1\nP1,Maria,3\n",
    "codigo,E-mail,item1\nP1,x,3\n",
    "codigo,data_nascimento,item1\nP1,2000-01-01,3\n",
    "codigo,obs,item1\nP1,contato a@b.com,3\n",
    "codigo,obs,item1\nP1,123.456.789-09,3\n",
])
def test_recusa_dados_identificaveis(csv):
    df = es.ler_arquivo(csv.encode(), "d.csv")
    with pytest.raises(catalogo.ErroValidacao):
        es.verificar_anonimizacao(df)


def test_importar_carregar_remover_e_exemplo(fabrica):
    with fabrica.begin() as s:
        c = pq.importar(s, nome="Piloto", conteudo=b"codigo,i1,i2\nP1,1,2\nP2,3,4\n", nome_arquivo="p.csv")
        assert c.n_linhas == 2 and len(c.sha256) == 64
        assert pq.carregar(s, c.id)["i2"].tolist() == [2, 4]
        with pytest.raises(catalogo.ErroValidacao, match="Já existe"):
            pq.importar(s, nome="piloto", conteudo=b"a\n1\n", nome_arquivo="p.csv")
        pq.remover(s, c.id)
        assert pq.listar(s) == []
        ex = pq.criar_exemplo(s)
        df = pq.carregar(s, ex.id)
        assert len(df) == 300 and {"E1", "A4", "D6"} <= set(df.columns)
        a = es.afe(df, [f"E{i}" for i in range(1, 5)] + [f"A{i}" for i in range(1, 5)])
        assert a.sugestao_paralela == 2
        assert pq.criar_exemplo(s).nome == "Exemplo simulado 2"


# ------------------------------------------------- AFC × lavaan (referência)

HS = Path(__file__).parent / "dados" / "holzinger_swineford_1939.csv"
MODELO_HS = {"visual": ["x1", "x2", "x3"], "textual": ["x4", "x5", "x6"], "speed": ["x7", "x8", "x9"]}


def test_afc_reproduz_lavaan_holzinger_swineford():
    """Valores de referência: lavaan::cfa(HS.model, HolzingerSwineford1939), estimador ML."""
    r = es.afc(pd.read_csv(HS), MODELO_HS)
    assert r.convergiu and r.n == 301 and r.gl == 24
    assert r.qui2 == pytest.approx(85.306, abs=0.01)
    assert r.cfi == pytest.approx(0.931, abs=0.001)
    assert r.tli == pytest.approx(0.896, abs=0.001)
    assert r.rmsea == pytest.approx(0.092, abs=0.001)
    assert r.rmsea_ic90[0] == pytest.approx(0.071, abs=0.001) and r.rmsea_ic90[1] == pytest.approx(0.114, abs=0.001)
    assert r.srmr == pytest.approx(0.065, abs=0.001)
    lam = r.cargas["Carga"].to_numpy()
    # cargas não padronizadas na parametrização do lavaan (1º item de cada fator fixado em 1)
    marcador = [lam[1] / lam[0], lam[2] / lam[0], lam[4] / lam[3], lam[5] / lam[3], lam[7] / lam[6], lam[8] / lam[6]]
    assert np.allclose(marcador, [0.554, 0.729, 1.113, 0.926, 1.180, 1.082], atol=0.001)
    assert np.allclose(r.cargas["Carga padronizada"], [0.772, 0.424, 0.581, 0.852, 0.855, 0.838, 0.570, 0.723, 0.665],
                       atol=0.001)
    phi = r.correlacoes_fatores.to_numpy()
    assert np.allclose([phi[0, 1], phi[0, 2], phi[1, 2]], [0.459, 0.471, 0.283], atol=0.001)


def test_afc_validacoes():
    df = pd.read_csv(HS)
    with pytest.raises(catalogo.ErroValidacao, match="mais de um fator"):
        es.afc(df, {"a": ["x1", "x2", "x3"], "b": ["x3", "x4", "x5"]})
    with pytest.raises(catalogo.ErroValidacao, match="ao menos 2"):
        es.afc(df, {"a": ["x1"], "b": ["x2", "x3", "x4"]})
