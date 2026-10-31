"""Aba “Chave da API”: colar, testar, guardar (cifrada) ou remover a chave do Claude."""

import streamlit as st

from siap import ia, segredos
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Chave da API", "Cole aqui a chave do Claude para usar o Consultor IA. Ela fica criptografada.", "🔑", ["Crie a chave em console.anthropic.com → **API keys**.", "Cole no campo abaixo e clique em **Testar e salvar**.", "Depois, ative o Consultor IA aceitando o termo."])

with transacao() as s:
    est = segredos.estado(s, segredos.CHAVE_ANTHROPIC)
    habilitada = ia.obter_perfil(s).ia_habilitada
vem_dos_secrets = bool(ia.chave_dos_secrets())
tem_senha = bool(segredos.senha_mestra())

# ----------------------------------------------------------------- situação
if vem_dos_secrets:
    st.success("Chave configurada pelos Secrets do Streamlit — ela tem prioridade sobre a colada aqui.")
elif est.existe and est.legivel:
    st.success(f"Chave salva: **{est.mascarado}** · atualizada em {data_br(est.atualizado_em)}")
elif est.existe:
    st.warning("Há uma chave salva, mas ela não pode ser lida (a senha do app foi alterada). Cole a chave de novo.")
else:
    st.info("Nenhuma chave salva.")

if not habilitada:
    st.caption("Depois de salvar a chave, ative o Consultor IA na página **💡 Consultor IA** (termo de uso).")

# ------------------------------------------------------------------- colar
if not tem_senha:
    st.error("Para guardar a chave com segurança é preciso ter a senha do app (APP_PASSWORD) definida nos "
             "Secrets do Streamlit. Ela é usada para cifrar a chave.")
else:
    with st.form("chave_api", clear_on_submit=True):
        colada = st.text_input("Cole aqui a sua chave (começa com sk-ant-)", type="password",
                               placeholder="sk-ant-…")
        enviar = st.form_submit_button("Testar e salvar", type="primary")
    if enviar:
        try:
            chave = segredos.normalizar_chave_anthropic(colada)
            with st.spinner("Testando a chave com a Anthropic…"):
                modelo = ia.testar_chave(chave)
        except ia.ErroValidacao as erro:
            st.error(str(erro))
        else:
            executar(lambda s: segredos.salvar(s, segredos.CHAVE_ANTHROPIC, chave),
                     f"Chave válida (modelo {modelo} disponível) e salva com criptografia.")

if est.existe and st.button("Remover chave salva"):
    executar(lambda s: segredos.remover(s, segredos.CHAVE_ANTHROPIC), "Chave removida.")

with st.expander("Como conseguir a chave"):
    st.markdown(
        "1. Acesse <https://console.anthropic.com> e entre (ou crie a conta).\n"
        "2. Em **Settings → Billing**, adicione créditos e defina um **limite de gastos** mensal.\n"
        "3. Em **API keys**, clique em **Create Key**, dê um nome (ex.: SIAP-IA) e copie a chave.\n"
        "4. Volte aqui, cole no campo acima e clique em **Testar e salvar**."
    )
with st.expander("Como a chave é protegida"):
    st.markdown(
        "- É **testada** antes de ser salva (consulta gratuita à lista de modelos).\n"
        "- Fica **criptografada no banco**, com uma chave derivada da senha do app. Sem a senha, é ilegível.\n"
        "- **Nunca** é exibida inteira, **não** entra no backup, na auditoria nem nos registros do sistema.\n"
        "- Se você trocar a senha do app, a chave antiga deixa de abrir: basta colar de novo."
    )
rodape()
