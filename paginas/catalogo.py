"""Biblioteca dinâmica: buscar, cadastrar e editar testes e versões."""

import pandas as pd
import streamlit as st

from siap import catalogo
from siap.ui import executar, iniciar_pagina, rodape, selo, transacao

iniciar_pagina("Catálogo de testes", "Sua biblioteca de instrumentos. Estar aqui não libera o uso: isso depende do SATEPSI.", "📚", ["Use a busca e os filtros para encontrar um teste.", "Clique numa linha para ver os detalhes e verificar no SATEPSI.", "Para incluir um teste novo, abra **Adicionar teste**.", "Cada versão (ex.: d2 e d2-R) é verificada separadamente."])

with transacao() as s:
    linhas = catalogo.listar_catalogo(s)
    instrumentos = [(i.id, i.nome, i.sigla, i.categoria, i.construto, i.descricao, i.observacoes)
                    for i in catalogo.listar_instrumentos(s)]

# ------------------------------------------------------------------ busca
busca = st.text_input("Buscar", placeholder="🔎 Nome, sigla ou construto (ex.: atenção, d2, BPA)")
f1, f2 = st.columns([3, 2])
categorias = f1.pills("Categoria", catalogo.CATEGORIAS, selection_mode="multi")
uso = f2.segmented_control("Uso profissional", ["Todos", "Elegível", "Bloqueado"], default="Todos") or "Todos"

termo = busca.strip().lower()
filtradas = [
    l for l in linhas
    if (not termo or termo in f"{l.instrumento} {l.sigla} {l.construto} {l.versao}".lower())
    and (not categorias or l.categoria in categorias)
    and (uso == "Todos" or l.situacao.rotulo_uso == uso)
]
st.caption(f"{len(filtradas)} de {len(linhas)} versões · 👆 clique numa linha para ver detalhes")
evento = st.dataframe(
    pd.DataFrame([{
        "": "✅" if l.situacao.liberado else "⛔", "Teste": l.instrumento, "Versão": l.versao,
        "Categoria": l.categoria, "Construto": l.construto, "SATEPSI": l.situacao.rotulo,
        "Uso profissional": l.situacao.rotulo_uso,
    } for l in filtradas]),
    hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="tabela_catalogo",
)
sel = getattr(getattr(evento, "selection", None), "rows", []) or []
if sel:
    l = filtradas[sel[0]]
    with st.container(border=True):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown(f"#### {l.instrumento} — {l.versao}")
        a.markdown(f"{selo(l.situacao)} :gray-badge[{l.categoria}]" + (f" :gray-badge[{l.construto}]" if l.construto else ""))
        a.caption(l.situacao.motivo)
        if b.button("Verificar no SATEPSI", icon=":material/verified:", type="primary", use_container_width=True):
            st.session_state["satepsi_versao"] = l.versao_id
            st.switch_page("paginas/verificacao_satepsi.py")


# --------------------------------------------------------------- cadastro
with st.expander("➕ Adicionar teste psicológico"):
    with st.form("novo_teste", clear_on_submit=False):
        nome = st.text_input("Nome completo *")
        c1, c2 = st.columns(2)
        sigla = c1.text_input("Sigla")
        categoria = c2.selectbox("Categoria *", catalogo.CATEGORIAS)
        construto = st.text_input("Construto avaliado")
        versoes = st.text_area("Versões/edições (uma por linha; vazio = usa a sigla)")
        descricao = st.text_area("Descrição")
        observacoes = st.text_area("Observações")
        if st.form_submit_button("Cadastrar"):
            executar(
                lambda s: catalogo.criar_instrumento(
                    s, nome=nome, sigla=sigla, categoria=categoria, construto=construto,
                    descricao=descricao, observacoes=observacoes, versoes=versoes.splitlines(),
                ),
                f"Teste {nome!r} cadastrado como não verificado.",
            )

opcoes = {i[0]: f"{i[1]} ({i[2]})" if i[2] else i[1] for i in instrumentos}

with st.expander("➕ Adicionar versão a um teste existente"):
    if opcoes:
        with st.form("nova_versao"):
            alvo = st.selectbox("Teste", list(opcoes), format_func=opcoes.get)
            nome_versao = st.text_input("Nome da versão *", placeholder="ex.: d2-R, 2ª edição")
            c1, c2 = st.columns(2)
            edicao = c1.text_input("Edição / ano")
            editora = c2.text_input("Editora")
            populacao = st.text_input("População / faixa etária")
            obs_versao = st.text_area("Observações da versão")
            if st.form_submit_button("Adicionar versão"):
                executar(
                    lambda s: catalogo.adicionar_versao(
                        s, alvo, nome_versao=nome_versao, edicao=edicao, editora=editora,
                        populacao=populacao, observacoes=obs_versao,
                    ),
                    "Versão adicionada como não verificada.",
                )

with st.expander("✏️ Editar dados de um teste"):
    if opcoes:
        alvo_ed = st.selectbox("Teste a editar", list(opcoes), format_func=opcoes.get, key="alvo_edicao")
        atual = next(i for i in instrumentos if i[0] == alvo_ed)
        with st.form(f"editar_{alvo_ed}"):
            e_nome = st.text_input("Nome", atual[1])
            c1, c2 = st.columns(2)
            e_sigla = c1.text_input("Sigla", atual[2])
            e_categoria = c2.selectbox("Categoria", catalogo.CATEGORIAS,
                                       index=catalogo.CATEGORIAS.index(atual[3]))
            e_construto = st.text_input("Construto", atual[4])
            e_descricao = st.text_area("Descrição", atual[5])
            e_observacoes = st.text_area("Observações", atual[6])
            if st.form_submit_button("Salvar alterações"):
                executar(
                    lambda s: catalogo.atualizar_instrumento(
                        s, alvo_ed, nome=e_nome, sigla=e_sigla, categoria=e_categoria,
                        construto=e_construto, descricao=e_descricao, observacoes=e_observacoes,
                    ),
                    "Alterações salvas (registradas na auditoria).",
                )

rodape()
