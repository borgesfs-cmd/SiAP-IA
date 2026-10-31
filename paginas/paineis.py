"""Painéis: visão geral, avaliação individual e comparativo."""

import altair as alt
import pandas as pd
import streamlit as st

from siap import avaliacoes as av
from siap import paineis as pn
from siap.ui import data_br, iniciar_pagina, rodape, transacao

COR = "#2a78d6"        # série única (paleta de referência, slot 1)
COR_REF = "#8a8984"    # marca de referência neutra (legível no claro e no escuro)

iniciar_pagina("Painéis")
st.caption("Contagens e valores transcritos. Os gráficos não calculam escores nem normas.")


MESES_PT = "['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'][month(datum.value)]"


def barras(df: pd.DataFrame, rotulo: str, valor: str, titulo_valor: str, altura_por_item: int = 36):
    """Barras horizontais finas, ordenadas, com rótulo de valor e dica ao passar o mouse."""
    base = alt.Chart(df).encode(
        y=alt.Y(f"{rotulo}:N", sort="-x", title=None, scale=alt.Scale(paddingInner=0.4, paddingOuter=0.3),
                axis=alt.Axis(labelLimit=260, labelPadding=6)),
        x=alt.X(f"{valor}:Q", title=None, axis=alt.Axis(tickMinStep=1, grid=True, gridOpacity=0.3)),
        tooltip=[alt.Tooltip(f"{rotulo}:N", title="Item"), alt.Tooltip(f"{valor}:Q", title=titulo_valor)],
    )
    graf = base.mark_bar(color=COR, cornerRadiusEnd=4, size=14) + base.mark_text(
        align="left", dx=4, color="gray").encode(text=f"{valor}:Q")
    return graf.properties(height=max(72, altura_por_item * len(df)))


def tabela(df: pd.DataFrame, chave: str):
    with st.expander("Ver dados em tabela"):
        st.dataframe(df, hide_index=True, width="stretch", key=chave)


aba_geral, aba_ind, aba_comp = st.tabs(["Visão geral", "Avaliação individual", "Comparativo"])

# ------------------------------------------------------------- visão geral
with aba_geral:
    with transacao() as s:
        vg = pn.visao_geral(s)
    c = st.columns(6)
    c[0].metric("Avaliações", vg.total_avaliacoes)
    c[1].metric("Em andamento", vg.em_andamento)
    c[2].metric("Concluídas", vg.concluidas)
    c[3].metric("Documentos emitidos", vg.documentos_emitidos)
    c[4].metric("✅ Versões elegíveis", vg.versoes_elegiveis)
    c[5].metric("⛔ Versões bloqueadas", vg.versoes_bloqueadas)

    st.markdown("#### Avaliações iniciadas por mês (últimos 12 meses)")
    df_mes = pd.DataFrame(vg.por_mes)
    df_mes["mês"] = pd.to_datetime(df_mes["mes"] + "-01")
    linha = alt.Chart(df_mes).encode(
        x=alt.X("yearmonth(mês):T", title=None, axis=alt.Axis(labelExpr=MESES_PT + " + '/' + timeFormat(datum.value, '%y')", labelAngle=0)),
        y=alt.Y("quantidade:Q", title="Avaliações", axis=alt.Axis(tickMinStep=1, gridOpacity=0.3)),
        tooltip=[alt.Tooltip("yearmonth(mês):T", title="Mês", format="%m/%Y"),
                 alt.Tooltip("quantidade:Q", title="Avaliações")],
    )
    st.altair_chart((linha.mark_line(color=COR, strokeWidth=2) + linha.mark_point(color=COR, size=64, filled=True))
                    .properties(height=220), width="stretch")
    tabela(df_mes[["mes", "quantidade"]].rename(columns={"mes": "Mês", "quantidade": "Avaliações"}), "t_mes")

    col1, col2 = st.columns(2)
    for col, titulo, dados, chave in (
        (col1, "Avaliações por finalidade", vg.por_finalidade, "t_fin"),
        (col2, "Avaliações por situação", vg.por_status, "t_sit"),
        (col1, "Instrumentos mais aplicados", vg.instrumentos_mais_usados, "t_inst"),
        (col2, "Documentos por tipo", vg.documentos_por_tipo, "t_doc"),
        (col1, "Versões bloqueadas por motivo (SATEPSI)", vg.motivos_bloqueio, "t_bloq"),
    ):
        with col:
            st.markdown(f"#### {titulo}")
            if dados:
                df = pd.DataFrame(dados)
                st.altair_chart(barras(df, "categoria", "quantidade", "Quantidade"), width="stretch")
                tabela(df.rename(columns={"categoria": "Categoria", "quantidade": "Quantidade"}), chave)
            else:
                st.caption("Sem dados ainda.")
    with col2:
        st.markdown("#### Verificações SATEPSI a vencer (60 dias)")
        if vg.vencimentos:
            st.dataframe(pd.DataFrame([{"Versão": v["versao"], "Vence em": data_br(v["vence_em"])}
                                       for v in vg.vencimentos]), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma verificação vence nos próximos 60 dias.")

# ---------------------------------------------------------- individual
with aba_ind:
    with transacao() as s:
        lista = [(a.id, f"{a.codigo} · {a.finalidade.nome} · {av.STATUS[a.status]}") for a in av.listar_avaliacoes(s)]
    if not lista:
        st.info("Nenhuma avaliação registrada.")
    else:
        rot = dict(lista)
        aid = st.selectbox("Avaliação", list(rot), format_func=rot.get, key="painel_av")
        with transacao() as s:
            resultados = pn.resultados_da_avaliacao(s, aid)
            eventos = pn.linha_do_tempo(s, aid)

        st.markdown("#### Percentis registrados")
        com_p = [r for r in resultados if r["percentil"] is not None]
        if com_p:
            df = pd.DataFrame(com_p)
            base = alt.Chart(df).encode(
                y=alt.Y("rotulo:N", title=None, sort=None, scale=alt.Scale(paddingInner=0.4, paddingOuter=0.3),
                        axis=alt.Axis(labelLimit=260, labelPadding=6)),
                x=alt.X("percentil:Q", title="Percentil (transcrito)", scale=alt.Scale(domain=[0, 100]),
                        axis=alt.Axis(values=[0, 25, 50, 75, 100], gridOpacity=0.3)),
                tooltip=[alt.Tooltip("instrumento:N", title="Instrumento"), alt.Tooltip("medida:N", title="Medida"),
                         alt.Tooltip("percentil:Q", title="Percentil"),
                         alt.Tooltip("classificacao:N", title="Classificação"),
                         alt.Tooltip("referencia:N", title="Referência")],
            )
            # traço no percentil 50 em cada linha (o tema do Streamlit oculta mark_rule em camadas)
            ref = alt.Chart(df).mark_tick(color=COR_REF, thickness=2, size=26).encode(
                x=alt.datum(50), y=alt.Y("rotulo:N", sort=None))
            graf = base.mark_bar(color=COR, cornerRadiusEnd=4, size=14) + base.mark_text(
                align="left", dx=4, color="gray").encode(text=alt.Text("percentil:Q", format=".0f")) + ref
            st.altair_chart(graf.properties(height=max(72, 36 * len(df))), width="stretch")
            st.caption("Traço cinza: percentil 50. A interpretação depende da norma e do manual de cada teste.")
        else:
            st.caption("Nenhum resultado com percentil numérico registrado.")
        sem_p = [r for r in resultados if r["percentil"] is None]
        if sem_p:
            st.caption("Resultados sem percentil numérico (exibidos só na tabela): "
                       + "; ".join(f"{r['rotulo']} ({r['percentil_registrado'] or r['classificacao'] or '—'})" for r in sem_p))
        if resultados:
            tabela(pd.DataFrame([{"Instrumento": r["instrumento"], "Medida": r["medida"], "Escore bruto": r["escore_bruto"],
                                  "Percentil": r["percentil_registrado"], "Classificação": r["classificacao"],
                                  "Referência": r["referencia"]} for r in resultados]), "t_res")

        st.markdown("#### Linha do tempo")
        st.dataframe(pd.DataFrame([{"Data": data_br(e["data"]), "Tipo": e["tipo"], "Descrição": e["descricao"]}
                                   for e in eventos]), hide_index=True, width="stretch")

# ---------------------------------------------------------- comparativo
with aba_comp:
    st.caption("Compara percentis de uma mesma medida entre avaliações (identificadas só por código). "
               "Útil para pesquisa e acompanhamento; não é uma norma.")
    with transacao() as s:
        opcoes = pn.medidas_comparaveis(s)
    if not opcoes:
        st.info("É preciso ao menos duas avaliações com percentil numérico na mesma medida.")
    else:
        escolha = st.selectbox("Instrumento e medida", opcoes, format_func=lambda o: f"{o[0]} · {o[1]}")
        with transacao() as s:
            dados = pn.comparativo(s, *escolha)
        df = pd.DataFrame(dados)
        pontos = alt.Chart(df).mark_circle(color=COR, size=110, opacity=0.9, stroke="white", strokeWidth=2).encode(
            x=alt.X("percentil:Q", title="Percentil (transcrito)", scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(values=[0, 25, 50, 75, 100], gridOpacity=0.3)),
            y=alt.Y("finalidade:N", title=None),
            tooltip=[alt.Tooltip("avaliacao:N", title="Avaliação"), alt.Tooltip("percentil:Q", title="Percentil"),
                     alt.Tooltip("classificacao:N", title="Classificação")],
        )
        ref = alt.Chart(df).mark_tick(color=COR_REF, thickness=2, size=40).encode(x=alt.datum(50), y="finalidade:N")
        st.altair_chart((pontos + ref).properties(height=max(120, 60 * df["finalidade"].nunique())), width="stretch")
        st.caption(f"{len(df)} resultado(s). Mediana dos valores transcritos: {df['percentil'].median():.0f}.")
        tabela(df.rename(columns={"avaliacao": "Avaliação", "finalidade": "Finalidade", "percentil": "Percentil",
                                  "classificacao": "Classificação", "data": "Data"}), "t_comp")

rodape()
