"""Página inicial: panorama do catálogo e da conformidade SATEPSI."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from siap import avaliacoes, catalogo
from siap.ui import data_br, iniciar_pagina, rodape, transacao

iniciar_pagina("SIAP-IA — Panorama")
st.caption("Sistema Inteligente de Avaliação Psicológica · uso pessoal e não comercial")

hoje = catalogo.hoje()
with transacao() as s:
    linhas = catalogo.listar_catalogo(s, hoje)
    em_andamento = len(avaliacoes.listar_avaliacoes(s, status=avaliacoes.EM_ANDAMENTO))
    alertas = avaliacoes.alertas_conformidade(s, hoje)

elegiveis = [l for l in linhas if l.situacao.liberado]
bloqueadas = [l for l in linhas if not l.situacao.liberado]
vencendo = [l for l in elegiveis if l.situacao.vence_em and l.situacao.vence_em <= hoje + timedelta(days=15)]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Avaliações em andamento", em_andamento)
c2.metric("Testes no catálogo", len({l.instrumento_id for l in linhas}))
c3.metric("Versões", len(linhas))
c4.metric("Elegíveis a uso profissional", len(elegiveis))
c5.metric("Bloqueadas", len(bloqueadas))

for alerta in alertas:
    st.error(f"⚠️ Avaliação **{alerta.codigo}**: {alerta.versao} — {alerta.motivo}")

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
            "Uso profissional (geral)": l.situacao.rotulo_uso,
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
