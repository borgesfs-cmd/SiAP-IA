"""Página inicial: panorama do catálogo e da conformidade SATEPSI."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from siap import catalogo
from siap.ui import data_br, iniciar_pagina, rodape, transacao

iniciar_pagina("SIAP-IA — Panorama")
st.caption("Sistema Inteligente de Avaliação Psicológica · Etapas 1 e 2: catálogo e Monitor SATEPSI")

hoje = catalogo.hoje()
with transacao() as s:
    linhas = catalogo.listar_catalogo(s, hoje)

elegiveis = [l for l in linhas if l.situacao.liberado]
bloqueadas = [l for l in linhas if not l.situacao.liberado]
vencendo = [l for l in elegiveis if l.situacao.vence_em and l.situacao.vence_em <= hoje + timedelta(days=15)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Testes no catálogo", len({l.instrumento_id for l in linhas}))
c2.metric("Versões", len(linhas))
c3.metric("Elegíveis a uso profissional", len(elegiveis))
c4.metric("Bloqueadas", len(bloqueadas))

if vencendo:
    st.warning(
        "Verificações que vencem nos próximos 15 dias: "
        + ", ".join(f"**{l.instrumento} — {l.versao}** ({l.situacao.vence_em:%d/%m})" for l in vencendo)
    )
if bloqueadas:
    st.info(
        f"{len(bloqueadas)} versão(ões) bloqueada(s). Registre a consulta ao SATEPSI na página "
        "**Verificação SATEPSI** para liberar as que tiverem parecer favorável."
    )

st.subheader("Situação por versão")
if linhas:
    st.dataframe(
        pd.DataFrame([{
            "Uso profissional": l.situacao.rotulo_uso,
            "Teste": l.instrumento,
            "Versão": l.versao,
            "Categoria": l.categoria,
            "SATEPSI": l.situacao.rotulo,
            "Consulta": data_br(l.situacao.data_consulta),
            "Válida até": data_br(l.situacao.vence_em),
            "Motivo": l.situacao.motivo,
        } for l in linhas]),
        hide_index=True, width="stretch",
    )
else:
    st.write("Catálogo vazio.")

rodape()
