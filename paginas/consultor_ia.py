"""Consultor IA: termo de uso, ativação e consultor metodológico."""

import streamlit as st

from siap import avaliacoes as av
from siap import documentos as dc
from siap import ia
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Consultor IA", "Sugestões de metodologia e redação. A IA sugere; quem decide é você.", "✨", ["Leia o termo e clique em **Ativar** (uma única vez).", "Escolha a avaliação e escreva sua pergunta.", "Confira **o que será enviado** — o texto é pseudonimizado.", "Avalie criticamente a resposta antes de usar."])

with transacao() as s:
    perfil = dc.obter_perfil(s)
    habilitada, consentido_em = perfil.ia_habilitada, perfil.ia_consentimento_em
    disponivel, motivo = ia.situacao(s)

st.markdown(
    """
**Como o Consultor IA funciona**

- Usa a API do Claude (Anthropic) para **sugerir**: escolha de técnicas e instrumentos, revisão de redação de documentos
  e códigos para a análise qualitativa. **Nada é aplicado sem a sua ação**, e nenhuma decisão técnica é tomada pela IA.
- Antes do envio, o texto é **pseudonimizado**: o marcador de nome vira `[PESSOA AVALIADA]`, o código do caso vira
  `[CASO]` e padrões de CPF, e-mail e telefone viram `[REMOVIDO]`. **Nomes próprios digitados por engano não são
  detectáveis automaticamente** — por isso, nunca escreva nomes nos textos do sistema.
- A IA é instruída a não inventar números. Mesmo assim, números da resposta que não constam dos dados enviados
  aparecem destacados para você conferir.
- A auditoria registra apenas que houve uma consulta (função, modelo e tamanho), nunca o conteúdo.
- Os dados enviados ficam sujeitos à política de privacidade e de retenção da Anthropic. Avalie se isso é
  compatível com o seu uso e com a LGPD antes de ativar.
"""
)

c1, c2 = st.columns([3, 1])
if habilitada:
    c1.success(f"Consultor IA **ativado** em {data_br(consentido_em)}.")
    if c2.button("Desativar"):
        executar(lambda s: ia.definir_consentimento(s, False), "Consultor IA desativado.")
else:
    li = c1.checkbox("Li e concordo com as condições acima e quero ativar o Consultor IA.")
    if c2.button("Ativar", disabled=not li):
        executar(lambda s: ia.definir_consentimento(s, True), "Consultor IA ativado.")

if habilitada and not disponivel:
    st.warning(motivo)
    st.page_link("paginas/chave_api.py", label="Ir para Chave da API", icon="🔑")

st.divider()
st.subheader("Consultor metodológico")
with transacao() as s:
    lista = [(a.id, f"{a.codigo} · {a.finalidade.nome} · {av.STATUS[a.status]}")
             for a in av.listar_avaliacoes(s) if a.status != av.CANCELADA]
if not lista:
    st.info("Crie uma avaliação para usar o consultor com o contexto do caso.")
    rodape()
    st.stop()

rot = dict(lista)
avaliacao_id = st.selectbox("Avaliação (contexto enviado de forma pseudonimizada)", list(rot), format_func=rot.get)
with transacao() as s:
    a = s.get(av.Avaliacao, avaliacao_id)
    contexto = dc.resumo_dados_registrados(a)
    elegiveis = [o.rotulo for o in av.opcoes_de_versao(s, avaliacao_id) if o.situacao.liberado]

with st.expander("Ver exatamente o que será enviado"):
    st.text(ia.pseudonimizar(contexto))
    st.caption("Instrumentos elegíveis para esta finalidade: " + (", ".join(elegiveis) or "nenhum"))

pergunta = st.text_area("Sua pergunta", placeholder="Ex.: Que procedimentos complementares você sugere para "
                        "investigar a queixa atencional, considerando os instrumentos disponíveis?")
if st.button("Consultar", disabled=not disponivel or not pergunta.strip(), type="primary"):
    with st.spinner("Consultando…"):
        try:
            with transacao() as s:
                st.session_state["ia_consulta"] = ia.consultar(
                    s, pergunta=pergunta, contexto=contexto, instrumentos_elegiveis=elegiveis)
        except ia.ErroIA as erro:
            st.error(str(erro))

resultado = st.session_state.get("ia_consulta")
if resultado:
    st.markdown("##### 💡 Sugestão da IA (interpretação, não cálculo — avalie criticamente)")
    st.write(resultado.dados.resposta)
    if resultado.dados.instrumentos_sugeridos:
        st.markdown("**Instrumentos sugeridos (todos elegíveis no SIAP-IA):** "
                    + "; ".join(resultado.dados.instrumentos_sugeridos))
    for c in resultado.dados.cautelas:
        st.caption(f"⚠️ {c}")
    if resultado.numeros_nao_encontrados:
        st.warning("Números na resposta que não constam dos dados enviados (confira): "
                   + ", ".join(resultado.numeros_nao_encontrados))

rodape()
