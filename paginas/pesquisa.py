"""Estatística de pesquisa: dados anonimizados, descritivas, precisão (TCT), AFE e TRI."""

import altair as alt
import pandas as pd
import streamlit as st

from siap import estatistica as es
from siap import pesquisa as pq
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

COR_1, COR_2 = "#2a78d6", "#eb6834"  # paleta de referência, slots 1 e 2

iniciar_pagina("Pesquisa (estatística)", "Análises psicométricas para estudos com dados anonimizados.", "📐", ["Importe um arquivo CSV/Excel (uma linha por participante, sem nomes) ou crie o **exemplo simulado**.", "Explore os dados em **Descritivas**.", "Em **Precisão**, selecione os itens de uma escala e calcule alfa e ômega.", "Em **AFE**, veja quantos fatores reter e as cargas.", "Em **TRI**, estime os parâmetros dos itens."])


def baixar(df: pd.DataFrame, nome: str, chave: str):
    st.download_button("Baixar tabela (CSV)", df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"{nome}.csv", mime="text/csv", key=chave)


def mostrar_alertas(alertas):
    for a in alertas:
        st.warning(a)


# -------------------------------------------------------------- conjuntos
with transacao() as s:
    conjuntos = [(c.id, c.nome, c.descricao, c.n_linhas, c.n_colunas, c.criado_em, c.arquivo_original)
                 for c in pq.listar(s)]

with st.expander("📥 Importar conjunto de dados", expanded=not conjuntos):
    st.markdown(
        "- Arquivo **.csv** (vírgula ou ponto e vírgula) ou **.xlsx**, até 5 MB, com cabeçalho na primeira linha.\n"
        "- **Sem nomes, CPF, e-mail, telefone, endereço ou data de nascimento**: o sistema recusa colunas e valores "
        "com esses padrões.\n"
        "- Itens invertidos devem ser recodificados antes da importação."
    )
    with st.form("importar", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome do conjunto *", placeholder="ex.: Estudo piloto escala X — 2026")
        descricao = c2.text_input("Descrição")
        arquivo = st.file_uploader("Arquivo", type=["csv", "txt", "xlsx"])
        if st.form_submit_button("Importar", type="primary"):
            if arquivo is None:
                st.error("Escolha um arquivo.")
            else:
                executar(lambda s: pq.importar(s, nome=nome, conteudo=arquivo.getvalue(), nome_arquivo=arquivo.name,
                                               descricao=descricao), "Conjunto importado.",
                         ao_concluir=lambda c: st.session_state.__setitem__("pq_sel", c.id))
    if st.button("Criar conjunto de exemplo (dados simulados)"):
        executar(pq.criar_exemplo, "Conjunto de exemplo criado.",
                 ao_concluir=lambda c: st.session_state.__setitem__("pq_sel", c.id))

if not conjuntos:
    rodape()
    st.stop()

rot = {c[0]: f"{c[1]} · {c[3]} casos × {c[4]} colunas" for c in conjuntos}
ids = list(rot)
atual = st.session_state.get("pq_sel")
cid = st.selectbox("Conjunto de dados", ids, format_func=rot.get, index=ids.index(atual) if atual in ids else 0)
st.session_state["pq_sel"] = cid
info = next(c for c in conjuntos if c[0] == cid)
with transacao() as s:
    df = pq.carregar(s, cid)
numericas = es.colunas_numericas(df)

aba_dados, aba_desc, aba_prec, aba_afe, aba_tri = st.tabs(
    ["Dados", "Descritivas", "Precisão (TCT)", "Análise fatorial (AFE)", "TRI"])

with aba_dados:
    st.caption(f"{info[2] or 'Sem descrição.'} · arquivo {info[6]} · importado em {data_br(info[5])}")
    st.dataframe(df.head(200), width="stretch", hide_index=True)
    st.caption(f"Mostrando até 200 de {len(df)} linhas. Colunas numéricas: {len(numericas)}.")
    if st.button("Remover este conjunto", key=f"rm_{cid}"):
        st.session_state.pop("pq_sel", None)
        executar(lambda s: pq.remover(s, cid), "Conjunto removido.")

with aba_desc:
    cols = st.multiselect("Variáveis numéricas", numericas, default=numericas[:12], key=f"desc_{cid}", placeholder="Selecione…")
    if cols:
        tabela = es.descritivas(df, cols)
        st.dataframe(tabela.round(3), hide_index=True, width="stretch")
        baixar(tabela, "descritivas", f"b_desc_{cid}")
    categ = st.selectbox("Frequências de uma variável", [None, *df.columns], key=f"freq_{cid}",
                         format_func=lambda c: "—" if c is None else c)
    if categ:
        freq = es.frequencias(df, categ)
        st.dataframe(freq, hide_index=True, width="stretch")

with aba_prec:
    itens = st.multiselect("Itens da escala (mesma direção)", numericas, key=f"prec_{cid}", placeholder="Selecione…")
    if st.button("Calcular precisão", disabled=len(itens) < 2, key=f"b_prec_{cid}"):
        try:
            st.session_state[f"res_prec_{cid}"] = es.precisao(df, itens)
        except es.ErroValidacao as erro:
            st.error(str(erro))
    r = st.session_state.get(f"res_prec_{cid}")
    if r:
        c = st.columns(4)
        c[0].metric("Alfa de Cronbach", f"{r.alfa:.3f}".replace(".", ","))
        c[1].metric("IC 95% (Feldt)", f"{r.alfa_ic95[0]:.2f} – {r.alfa_ic95[1]:.2f}".replace(".", ","))
        c[2].metric("Ômega de McDonald", "—" if r.omega is None else f"{r.omega:.3f}".replace(".", ","))
        c[3].metric("Casos / itens", f"{r.n} / {r.k}")
        st.caption(f"Alfa padronizado: {r.alfa_padronizado:.3f}. Calculado pelo sistema.")
        st.dataframe(r.itens.round(3), hide_index=True, width="stretch")
        baixar(r.itens, "analise_de_itens", f"b_prec2_{cid}")
        mostrar_alertas(r.alertas)

with aba_afe:
    itens_afe = st.multiselect("Itens", numericas, key=f"afe_{cid}", placeholder="Selecione…")
    c1, c2 = st.columns(2)
    nf = c1.number_input("Número de fatores (0 = sugerido pela análise paralela)", 0, 20, 0, key=f"nf_{cid}")
    rot_afe = c2.segmented_control("Rotação", list(es.ROTACOES), format_func=es.ROTACOES.get, default="promax",
                                   key=f"rot_{cid}") or "promax"
    if st.button("Rodar AFE", disabled=len(itens_afe) < 3, key=f"b_afe_{cid}"):
        try:
            with st.spinner("Calculando (inclui análise paralela)…"):
                st.session_state[f"res_afe_{cid}"] = es.afe(df, itens_afe, int(nf) or None, rot_afe)
        except es.ErroValidacao as erro:
            st.error(str(erro))
    a = st.session_state.get(f"res_afe_{cid}")
    if a:
        c = st.columns(4)
        c[0].metric("KMO", f"{a.kmo_geral:.2f}".replace(".", ","))
        c[1].metric("Bartlett (p)", "< 0,001" if a.bartlett_p < 0.001 else f"{a.bartlett_p:.3f}".replace(".", ","))
        c[2].metric("Fatores (paralela)", a.sugestao_paralela)
        c[3].metric("Fatores (Kaiser > 1)", a.sugestao_kaiser)

        st.markdown("##### Autovalores: observados × análise paralela")
        longo = a.autovalores.melt("Componente", var_name="Série", value_name="Autovalor")
        ordem = ["Autovalor observado", "Paralela (P95)"]
        base = alt.Chart(longo).encode(
            x=alt.X("Componente:O", title="Componente", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Autovalor:Q", axis=alt.Axis(gridOpacity=0.3)),
            color=alt.Color("Série:N", scale=alt.Scale(domain=ordem, range=[COR_1, COR_2]),
                            legend=alt.Legend(orient="top", title=None)),
            strokeDash=alt.StrokeDash("Série:N", scale=alt.Scale(domain=ordem, range=[[1, 0], [5, 4]]), legend=None),
            tooltip=["Componente", "Série", alt.Tooltip("Autovalor:Q", format=".2f")],
        )
        st.altair_chart((base.mark_line(strokeWidth=2) + base.mark_point(size=64, filled=True)).properties(height=240),
                        width="stretch")
        st.caption("Retenha os fatores cujo autovalor observado fica acima da curva da análise paralela.")

        st.markdown("##### Cargas fatoriais")
        nomes_f = [c for c in a.cargas.columns if c.startswith("F")]
        st.dataframe(a.cargas.style.format(precision=2).map(
            lambda v: "font-weight: 700" if isinstance(v, float) and abs(v) >= 0.40 else "", subset=nomes_f),
            hide_index=True, width="stretch")
        st.caption("Em negrito: |carga| ≥ 0,40. Extração por eixos principais.")
        baixar(a.cargas, "cargas_fatoriais", f"b_afe_c_{cid}")
        st.dataframe(a.variancia.round(3), hide_index=True, width="stretch")
        if a.correlacoes_fatores is not None:
            st.markdown("##### Correlações entre fatores")
            st.dataframe(a.correlacoes_fatores.round(2), width="stretch")
        with st.expander("KMO por item"):
            st.dataframe(a.kmo_itens.round(3), hide_index=True, width="stretch")
        mostrar_alertas(a.alertas)

with aba_tri:
    modelo = st.segmented_control("Modelo", ["2PL", "GRM"], default="2PL", key=f"mod_{cid}",
                                  format_func=lambda m: {"2PL": "2PL (itens 0/1)",
                                                         "GRM": "Resposta graduada (Likert)"}[m]) or "2PL"
    itens_tri = st.multiselect("Itens", numericas, key=f"tri_{cid}", placeholder="Selecione…")
    if st.button("Estimar parâmetros", disabled=len(itens_tri) < 3, key=f"b_tri_{cid}"):
        try:
            with st.spinner("Estimando (máxima verossimilhança marginal)…"):
                st.session_state[f"res_tri_{cid}"] = es.tri(df, itens_tri, modelo)
        except es.ErroValidacao as erro:
            st.error(str(erro))
    t = st.session_state.get(f"res_tri_{cid}")
    if t:
        st.caption(f"Modelo {t.modelo} · n = {t.n} · calculado pelo sistema (girth, MML).")
        st.dataframe(t.parametros.round(3), hide_index=True, width="stretch")
        baixar(t.parametros, f"parametros_{t.modelo}", f"b_tri_{cid}")
        mostrar_alertas(t.alertas)

rodape()
