"""Relatório de pesquisa (Word/PDF) com tabelas no padrão APA, a partir dos resultados já calculados.

Formatação: vírgula decimal; sem zero à esquerda em estatísticas que não excedem 1 (r, α, ω, p, cargas
padronizadas, CFI, TLI, RMSEA, SRMR); tabelas numeradas com título em itálico e nota. O texto de método
apenas descreve os procedimentos executados pelo sistema (não interpreta resultados).
"""

from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

from . import render
from .catalogo import FUSO
from .estatistica import ROTACOES, ResultadoAFC, ResultadoAFE, ResultadoPrecisao, ResultadoTRI

REFERENCIAS = {
    "alfa": "Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. Psychometrika, 16(3), 297–334.",
    "feldt": "Feldt, L. S. (1965). The approximate sampling distribution of Kuder-Richardson reliability coefficient twenty. Psychometrika, 30(3), 357–370.",
    "omega": "McDonald, R. P. (1999). Test theory: A unified treatment. Lawrence Erlbaum.",
    "horn": "Horn, J. L. (1965). A rationale and test for the number of factors in factor analysis. Psychometrika, 30(2), 179–185.",
    "varimax": "Kaiser, H. F. (1958). The varimax criterion for analytic rotation in factor analysis. Psychometrika, 23(3), 187–200.",
    "promax": "Hendrickson, A. E., & White, P. O. (1964). Promax: A quick method for rotation to oblique simple structure. British Journal of Statistical Psychology, 17(1), 65–70.",
    "hu_bentler": "Hu, L., & Bentler, P. M. (1999). Cutoff criteria for fit indexes in covariance structure analysis: Conventional criteria versus new alternatives. Structural Equation Modeling, 6(1), 1–55.",
    "birnbaum": "Birnbaum, A. (1968). Some latent trait models and their use in inferring an examinee's ability. In F. M. Lord & M. R. Novick (Eds.), Statistical theories of mental test scores (pp. 397–479). Addison-Wesley.",
    "samejima": "Samejima, F. (1969). Estimation of latent ability using a response pattern of graded scores. Psychometrika Monograph Supplement, 34(4, Pt. 2).",
}


def num(valor, casas: int = 2, sem_zero: bool = False) -> str:
    """Formata número no padrão APA em português: vírgula decimal; opcionalmente sem zero à esquerda."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    texto = f"{float(valor):.{casas}f}"
    if sem_zero:
        if texto.startswith("0."):
            texto = texto[1:]
        elif texto.startswith("-0."):
            texto = "-" + texto[2:]
    return texto.replace(".", ",")


def valor_p(p: float) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "—"
    return "< ,001" if p < 0.001 else num(p, 3, sem_zero=True)


def montar(*, conjunto: str, n_total: int, descritivas: pd.DataFrame | None = None,
           precisao: ResultadoPrecisao | None = None, afe: ResultadoAFE | None = None, rotacao_afe: str = "",
           afc: ResultadoAFC | None = None, tri: ResultadoTRI | None = None) -> render.Documento:
    if all(x is None for x in (descritivas, precisao, afe, afc, tri)):
        from .catalogo import ErroValidacao
        raise ErroValidacao("Rode ao menos uma análise antes de gerar o relatório.")
    b: list = [render.Titulo("Relatório de análises psicométricas"),
               render.Paragrafo(f"Conjunto de dados: {conjunto} · {n_total} casos · gerado em "
                                f"{datetime.now(FUSO):%d/%m/%Y}", alinhamento="centro", italico=True)]
    refs: list[str] = []
    metodo: list[str] = []
    if descritivas is not None:
        metodo.append("Foram calculadas estatísticas descritivas (média, desvio-padrão, mínimo, máximo, assimetria e curtose).")
    if precisao is not None:
        metodo.append(f"A precisão foi estimada pelo coeficiente alfa de Cronbach, com intervalo de confiança de 95% "
                      f"pelo método de Feldt, e pelo ômega de McDonald a partir de um modelo de um fator "
                      f"(n = {precisao.n}; {precisao.k} itens; exclusão listwise).")
        refs += ["alfa", "feldt", "omega"]
    if afe is not None:
        rot = ROTACOES.get(rotacao_afe, "").split(" (")[0].lower() or "sem rotação"
        metodo.append(f"A estrutura interna foi investigada por análise fatorial exploratória com extração por eixos "
                      f"principais e rotação {rot}; a retenção de fatores considerou a análise paralela de Horn "
                      f"(percentil 95 de 100 matrizes aleatórias). A adequação da matriz foi verificada pelo KMO e "
                      f"pelo teste de esfericidade de Bartlett (n = {afe.n}).")
        refs += ["horn"] + (["promax", "varimax"] if rotacao_afe == "promax" else ["varimax"] if rotacao_afe == "varimax" else [])
    if afc is not None:
        metodo.append(f"O modelo foi testado por análise fatorial confirmatória com estimador de máxima "
                      f"verossimilhança (variância dos fatores fixada em 1; n = {afc.n}). O ajuste foi avaliado por "
                      f"χ², CFI, TLI, RMSEA (IC 90%) e SRMR, com pontos de referência usuais como orientação.")
        refs += ["hu_bentler"]
    if tri is not None:
        modelo = "logístico de dois parâmetros (2PL)" if tri.modelo == "2PL" else "de resposta graduada"
        metodo.append(f"Os parâmetros dos itens foram estimados pelo modelo {modelo} da Teoria de Resposta ao Item, "
                      f"por máxima verossimilhança marginal (n = {tri.n}).")
        refs += ["birnbaum"] if tri.modelo == "2PL" else ["samejima"]
    metodo.append("Todos os cálculos foram executados pelo SIAP-IA com rotinas validadas em dados de referência.")
    b += [render.Secao("Método"), render.Paragrafo(" ".join(metodo)), render.Secao("Resultados")]

    n_tab = 0
    observacoes: list[str] = []
    if descritivas is not None and not descritivas.empty:
        n_tab += 1
        b.append(render.Tabela(
            ["Variável", "N", "M", "DP", "Mín.", "Máx.", "Assimetria", "Curtose"],
            [[str(r["Variável"]), str(int(r["N válido"])), num(r["Média"]), num(r["DP"]), num(r["Mínimo"]),
              num(r["Máximo"]), num(r["Assimetria"]), num(r["Curtose"])] for _, r in descritivas.iterrows()],
            numero=n_tab, titulo="Estatísticas descritivas",
        ))
    if precisao is not None:
        n_tab += 1
        omega = f"; ω = {num(precisao.omega, 2, True)}" if precisao.omega is not None else ""
        b.append(render.Tabela(
            ["Item", "M", "DP", "r item-total corrigida", "α se excluído"],
            [[str(r["Item"]), num(r["Média"]), num(r["DP"]), num(r["r item-total corrigida"], 2, True),
              num(r["Alfa se excluído"], 2, True)] for _, r in precisao.itens.iterrows()],
            numero=n_tab, titulo="Análise de itens e precisão",
            nota=f"α = {num(precisao.alfa, 2, True)}, IC 95% [{num(precisao.alfa_ic95[0], 2, True)}; "
                 f"{num(precisao.alfa_ic95[1], 2, True)}]{omega}; n = {precisao.n}.",
        ))
        observacoes += precisao.alertas
    if afe is not None:
        n_tab += 1
        fatores = [c for c in afe.cargas.columns if c.startswith("F")]
        k = len(afe.cargas)
        b.append(render.Tabela(
            ["Item", *fatores, "h²"],
            [[str(r["Item"]), *[num(r[f], 2, True) for f in fatores], num(r["Comunalidade"], 2, True)]
             for _, r in afe.cargas.iterrows()],
            numero=n_tab, titulo="Cargas fatoriais da análise fatorial exploratória",
            nota=f"KMO = {num(afe.kmo_geral, 2, True)}; Bartlett χ²({k * (k - 1) // 2}) = {num(afe.bartlett_qui2)}, "
                 f"p {valor_p(afe.bartlett_p) if afe.bartlett_p < 0.001 else '= ' + valor_p(afe.bartlett_p)}. "
                 f"Análise paralela sugeriu {afe.sugestao_paralela} fator(es). h² = comunalidade.",
        ))
        if afe.correlacoes_fatores is not None:
            n_tab += 1
            phi = afe.correlacoes_fatores
            b.append(render.Tabela(["Fator", *phi.columns],
                                   [[i, *[("—" if i == j else num(phi.loc[i, j], 2, True)) for j in phi.columns]]
                                    for i in phi.index],
                                   numero=n_tab, titulo="Correlações entre fatores (AFE)"))
        observacoes += afe.alertas
    if afc is not None:
        n_tab += 1
        b.append(render.Tabela(
            ["χ²", "gl", "p", "CFI", "TLI", "RMSEA [IC 90%]", "SRMR"],
            [[num(afc.qui2), str(afc.gl), valor_p(afc.p), num(afc.cfi, 3, True), num(afc.tli, 3, True),
              f"{num(afc.rmsea, 3, True)} [{num(afc.rmsea_ic90[0], 3, True)}; {num(afc.rmsea_ic90[1], 3, True)}]",
              num(afc.srmr, 3, True)]],
            numero=n_tab, titulo="Índices de ajuste da análise fatorial confirmatória",
            nota=f"n = {afc.n}. Estimador de máxima verossimilhança.",
        ))
        n_tab += 1
        b.append(render.Tabela(
            ["Fator", "Item", "λ", "EP", "λ padronizada", "R²"],
            [[str(r["Fator"]), str(r["Item"]), num(r["Carga"]), num(r["EP"]), num(r["Carga padronizada"], 2, True),
              num(r["R²"], 2, True)] for _, r in afc.cargas.iterrows()],
            numero=n_tab, titulo="Cargas fatoriais da análise fatorial confirmatória",
            nota="λ = carga não padronizada; EP = erro-padrão. Todas as cargas foram estimadas livremente.",
        ))
        observacoes += afc.alertas
    if tri is not None:
        n_tab += 1
        cols = list(tri.parametros.columns)
        b.append(render.Tabela(
            cols, [[str(r[c]) if c == "Item" else num(r[c]) for c in cols] for _, r in tri.parametros.iterrows()],
            numero=n_tab, titulo=f"Parâmetros dos itens — modelo {'2PL' if tri.modelo == '2PL' else 'de resposta graduada'}",
            nota=f"n = {tri.n}. a = discriminação; b = dificuldade/limiar.",
        ))
        observacoes += tri.alertas

    if observacoes:
        b += [render.Secao("Observações sobre pressupostos e limites"), render.Lista(list(dict.fromkeys(observacoes)))]
    if refs:
        b += [render.Secao("Referências"), *[render.Paragrafo(REFERENCIAS[r], alinhamento="esquerda")
                                             for r in sorted(set(refs), key=lambda x: REFERENCIAS[x])]]
    return render.Documento(b, rodape=f"Relatório — {conjunto}", tamanho_fonte=11, entrelinha=1.3,
                            metadados={"titulo": f"Relatório de análises — {conjunto}"})
