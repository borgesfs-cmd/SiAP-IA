"""Finalidades de avaliação: padrões + inclusão manual."""

import pandas as pd
import streamlit as st

from siap import finalidades
from siap.ui import executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Finalidades", "Os contextos de avaliação. Você pode incluir novas finalidades a qualquer momento.", "🎯", ["Veja as finalidades padrão na lista.", "Para incluir uma nova, abra **Incluir nova finalidade**.", "Finalidades não são apagadas: desative as que não usa."])

with transacao() as s:
    lista = [(f.id, f.nome, f.descricao, f.ativa, f.padrao) for f in finalidades.listar_finalidades(s)]

st.dataframe(
    pd.DataFrame([{
        "Finalidade": nome, "Descrição": desc, "Situação": "Ativa" if ativa else "Desativada",
        "Origem": "Padrão do sistema" if padrao else "Incluída por você",
    } for _, nome, desc, ativa, padrao in lista]),
    hide_index=True, width="stretch",
)

with st.expander("➕ Incluir nova finalidade", expanded=False):
    with st.form("nova_finalidade", clear_on_submit=True):
        nome = st.text_input("Nome *", placeholder="ex.: Avaliação para cirurgia bariátrica")
        descricao = st.text_area("Descrição")
        if st.form_submit_button("Incluir"):
            executar(lambda s: finalidades.criar_finalidade(s, nome=nome, descricao=descricao),
                     f"Finalidade {nome.strip()!r} incluída.")

opcoes = {f[0]: f[1] for f in lista}
with st.expander("✏️ Editar, ativar ou desativar"):
    if opcoes:
        alvo = st.selectbox("Finalidade", list(opcoes), format_func=opcoes.get, key="finalidade_alvo")
        _, a_nome, a_desc, a_ativa, _ = next(f for f in lista if f[0] == alvo)
        with st.form(f"editar_finalidade_{alvo}"):
            e_nome = st.text_input("Nome", a_nome)
            e_desc = st.text_area("Descrição", a_desc)
            if st.form_submit_button("Salvar"):
                executar(lambda s: finalidades.atualizar_finalidade(s, alvo, nome=e_nome, descricao=e_desc),
                         "Finalidade atualizada.")
        rotulo = "Desativar finalidade" if a_ativa else "Reativar finalidade"
        if st.button(rotulo, key=f"ativa_{alvo}"):
            executar(lambda s: finalidades.definir_ativa(s, alvo, not a_ativa),
                     "Finalidade desativada." if a_ativa else "Finalidade reativada.")

st.info(
    "Lembrete: para trânsito e porte de arma de fogo há normas específicas que indicam os testes "
    "aceitos. Registre essas restrições na **Verificação SATEPSI**, marcando as finalidades cobertas."
)
rodape()
