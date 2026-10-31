"""Biblioteca de modelos e frases."""

import pandas as pd
import streamlit as st

from siap import biblioteca as bb
from siap.ui import estado_vazio, executar, iniciar_pagina, rodape, transacao

iniciar_pagina(
    "Biblioteca de textos", "Seus modelos e frases para inserir nos documentos com um clique.", "📚",
    ["Clique em **Novo trecho** e escreva o texto (pode usar [[trechos a completar]]).",
     "Escolha a **seção** em que ele costuma entrar (ou “qualquer seção”).",
     "Na página **Documentos**, abra **Inserir trecho da biblioteca** e clique no trecho.",
     "Clique numa linha da lista para editar ou desativar."],
)
st.caption("Use apenas textos seus. Não copie trechos de manuais de testes. O nome da pessoa avaliada pode "
           "aparecer só como marcador {{NOME DA PESSOA AVALIADA}}.")

with transacao() as s:
    bb.carregar_exemplos(s)
    trechos = [(t.id, t.titulo, t.categoria, t.secao, t.texto, t.ativo, t.usos, t.exemplo)
               for t in bb.listar(s, somente_ativos=False)]


@st.dialog("Novo trecho", width="large")
def novo_trecho():
    titulo = st.text_input("Título *", placeholder="ex.: Cautela interpretativa — crianças")
    c1, c2 = st.columns(2)
    categoria = c1.selectbox("Categoria", bb.CATEGORIAS)
    secao = c2.selectbox("Seção do documento", list(bb.SECOES), format_func=bb.SECOES.get)
    texto = st.text_area("Texto *", height=200)
    if st.button("Salvar trecho", type="primary", icon=":material/save:", use_container_width=True):
        executar(lambda s: bb.criar(s, titulo=titulo, categoria=categoria, secao=secao, texto=texto),
                 "Trecho incluído na biblioteca.")


if st.button("Novo trecho", type="primary", icon=":material/add:"):
    novo_trecho()

if not trechos:
    estado_vazio("📚", "Biblioteca vazia", "Clique em **Novo trecho** para criar o primeiro.")
    rodape()
    st.stop()

c1, c2 = st.columns([2, 1])
busca = c1.text_input("Buscar", placeholder="🔎 Título ou texto")
filtro = c2.selectbox("Seção", ["todas", *bb.SECOES], format_func=lambda k: "Todas" if k == "todas" else bb.SECOES[k])
termo = busca.strip().lower()
filtrados = [t for t in trechos if (not termo or termo in (t[1] + " " + t[4]).lower())
             and (filtro == "todas" or t[3] in (filtro, "qualquer"))]
st.caption(f"{len(filtrados)} trecho(s) · 👆 clique numa linha para editar")
evento = st.dataframe(
    pd.DataFrame([{"": "✅" if at else "⏸️", "Título": ti, "Categoria": ca, "Seção": bb.SECOES[se], "Usos": us,
                   "Prévia": (tx[:90] + "…") if len(tx) > 90 else tx}
                  for _, ti, ca, se, tx, at, us, _ in filtrados]),
    hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="tabela_trechos",
)
sel = getattr(getattr(evento, "selection", None), "rows", []) or []
if sel:
    tid, ti, ca, se, tx, at, us, ex = filtrados[sel[0]]
    with st.container(border=True), st.form(f"editar_trecho_{tid}"):
        st.markdown(f"#### ✏️ {ti}")
        e_titulo = st.text_input("Título", ti)
        e1, e2, e3 = st.columns([2, 2, 1])
        e_cat = e1.selectbox("Categoria", bb.CATEGORIAS, index=bb.CATEGORIAS.index(ca))
        e_sec = e2.selectbox("Seção", list(bb.SECOES), index=list(bb.SECOES).index(se), format_func=bb.SECOES.get)
        e_ativo = e3.toggle("Ativo", at)
        e_texto = st.text_area("Texto", tx, height=180)
        if st.form_submit_button("Salvar alterações", type="primary"):
            executar(lambda s: bb.editar(s, tid, titulo=e_titulo, categoria=e_cat, secao=e_sec, texto=e_texto,
                                         ativo=e_ativo), "Trecho atualizado.")
rodape()
