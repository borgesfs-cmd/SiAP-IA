"""Monitor SATEPSI em modo assistido: você consulta o site oficial e registra o resultado."""

import pandas as pd
import streamlit as st

from siap import catalogo, finalidades, satepsi
from siap.ui import data_br, iniciar_pagina, rodape, selo, transacao

iniciar_pagina("Verificação SATEPSI", "Registre a consulta ao SATEPSI para liberar (ou bloquear) cada versão de teste.", "✅", ["Escolha o teste e a versão.", "Abra o site do SATEPSI e localize a versão exata.", "Salve uma captura de tela ou PDF do resultado.", "Registre a situação e anexe a evidência — favorável exige evidência.", "A liberação vale por 90 dias (ajustável)."])
st.link_button("Abrir o site do SATEPSI", "https://satepsi.cfp.org.br/", icon=":material/open_in_new:")

with transacao() as s:
    linhas = catalogo.listar_catalogo(s)
    fins = {f.id: f.nome for f in finalidades.listar_finalidades(s, somente_ativas=True)}

if not linhas:
    st.info("Catálogo vazio. Cadastre um teste primeiro.")
    st.stop()

rotulos = {l.versao_id: f"{l.instrumento} — {l.versao}" for l in linhas}
pre = st.session_state.pop("satepsi_versao", None)
pendentes = st.toggle("Mostrar apenas versões bloqueadas", value=pre is None)
ids = [l.versao_id for l in linhas if not (pendentes and l.situacao.liberado) or l.versao_id == pre]
if not ids:
    st.success("Nenhuma versão bloqueada. 🎉")
    st.stop()
versao_id = st.selectbox("Versão do teste", ids, format_func=rotulos.get,
                         index=ids.index(pre) if pre in ids else 0)

with transacao() as s:
    versao = s.get(catalogo.VersaoInstrumento, versao_id)
    situacao = catalogo.situacao_versao(versao)
    historico = [
        {
            "Nº": v.id, "Consulta": data_br(v.data_consulta), "Situação": satepsi.ROTULOS[v.status],
            "Validade (dias)": v.validade_dias,
            "Finalidades": "Todas" if v.abrange_todas_finalidades else ", ".join(f.nome for f in v.finalidades),
            "Fonte": v.fonte, "Condições": v.condicoes,
            "Observações": v.observacoes, "Evidência": v.evidencia_nome or "—",
            "SHA-256": (v.evidencia_sha256 or "")[:12], "Registrado em": data_br(v.registrado_em),
        }
        for v in sorted(versao.verificacoes, key=lambda v: v.id, reverse=True)
    ]
    com_evidencia = [v.id for v in versao.verificacoes if v.evidencia_sha256]

st.subheader("Situação atual")
st.markdown(f"{selo(situacao)} &nbsp; **{situacao.rotulo_uso} para uso profissional**")
(st.success if situacao.liberado else st.error)(situacao.motivo)
if situacao.condicoes:
    st.warning(f"Condições registradas: {situacao.condicoes}")

st.subheader("Registrar nova consulta")
with st.form("nova_verificacao", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    status = c1.selectbox("Situação no SATEPSI", satepsi.STATUS_REGISTRAVEIS, format_func=satepsi.ROTULOS.get)
    data_consulta = c2.date_input("Data da consulta", value=catalogo.hoje(), max_value=catalogo.hoje(),
                                  format="DD/MM/YYYY")
    validade = c3.number_input("Revalidar após (dias)", 1, satepsi.VALIDADE_MAXIMA_DIAS,
                               satepsi.VALIDADE_PADRAO_DIAS)
    fonte = st.text_input("Fonte", satepsi.FONTE_PADRAO)
    abrangencia = st.radio("Válida para", ["Todas as finalidades", "Somente as finalidades selecionadas"],
                           horizontal=True)
    selecionadas = st.multiselect("Finalidades cobertas (se “somente as selecionadas”)", list(fins),
                                  format_func=fins.get, placeholder="Selecione")
    condicoes = st.text_area("Condições/restrições informadas (população, modalidade, normas específicas…)")
    observacoes = st.text_area("Observações")
    arquivo = st.file_uploader("Evidência (PNG, JPG ou PDF, até 5 MB) — obrigatória para favorável",
                               type=["png", "jpg", "jpeg", "pdf"])
    if st.form_submit_button("Registrar verificação"):
        try:
            with transacao() as s:
                catalogo.registrar_verificacao(
                    s, versao_id, status=status, data_consulta=data_consulta, fonte=fonte,
                    validade_dias=int(validade), condicoes=condicoes, observacoes=observacoes,
                    evidencia_nome=arquivo.name if arquivo else None,
                    evidencia_tipo=arquivo.type if arquivo else None,
                    evidencia=arquivo.getvalue() if arquivo else None,
                    abrange_todas_finalidades=abrangencia == "Todas as finalidades",
                    finalidades_ids=selecionadas,
                )
        except catalogo.ErroValidacao as erro:
            st.error(str(erro))
        else:
            st.success("Verificação registrada.")
            st.rerun()

st.subheader("Histórico de verificações")
st.caption("Registros nunca são editados nem apagados. Para corrigir, registre uma nova consulta.")
if historico:
    st.dataframe(pd.DataFrame(historico), hide_index=True, width="stretch")
    if com_evidencia:
        escolhida = st.selectbox("Baixar evidência do registro nº", com_evidencia)
        with transacao() as s:
            ver = catalogo.carregar_evidencia(s, escolhida)
            dados, nome, tipo = ver.evidencia, ver.evidencia_nome, ver.evidencia_tipo
        st.download_button("Baixar evidência", dados, file_name=nome, mime=tipo)
else:
    st.write("Nenhuma verificação registrada para esta versão.")

rodape()
