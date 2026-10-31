"""Trilha de auditoria e cópia de segurança."""

import json

import pandas as pd
import streamlit as st

from siap import catalogo
from siap.ui import data_br, iniciar_pagina, rodape, transacao

iniciar_pagina("Auditoria e backup")

st.subheader("Cópia de segurança")
st.write(
    "Gera um arquivo JSON com todo o conteúdo do banco, incluindo as evidências. "
    "Guarde-o em local protegido (por exemplo, numa pasta criptografada)."
)
if st.button("Preparar backup"):
    with transacao() as s:
        dados = catalogo.exportar_backup(s)
    st.download_button(
        "Baixar backup (.json)",
        json.dumps(dados, ensure_ascii=False, indent=2).encode(),
        file_name=f"siap-ia-backup-{catalogo.hoje():%Y-%m-%d}.json",
        mime="application/json",
    )

st.subheader("Trilha de auditoria")
with transacao() as s:
    registros = [
        {"Nº": r.id, "Quando": data_br(r.quando), "Ação": r.acao, "Entidade": r.entidade,
         "ID": r.entidade_id, "Detalhes": r.detalhes}
        for r in catalogo.listar_auditoria(s)
    ]
st.caption("Últimos 500 registros, do mais recente para o mais antigo.")
st.dataframe(pd.DataFrame(registros), hide_index=True, width="stretch")

rodape()
