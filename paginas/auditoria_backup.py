"""Backup, restauração e trilha de auditoria."""

import json

import pandas as pd
import streamlit as st

from siap import backup, catalogo
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina(
    "Auditoria e backup", "Cópias de segurança, restauração e o registro de tudo o que muda no sistema.", "🛡️",
    ["Em **Fazer backup**, baixe a cópia e guarde-a numa pasta protegida (repita todo mês).",
     "Em **Restaurar**, envie um arquivo de backup para voltar o sistema àquele estado.",
     "Antes de restaurar, baixe o backup atual — a restauração substitui todos os dados.",
     "Em **Auditoria**, pesquise qualquer ação registrada."],
)


def _json(dados) -> bytes:
    return json.dumps(dados, ensure_ascii=False, indent=2).encode()


aba_bkp, aba_rest, aba_aud = st.tabs([":material/download: Fazer backup", ":material/restore: Restaurar",
                                      ":material/history: Auditoria"])

with aba_bkp:
    st.markdown("Gera um arquivo com **todo o conteúdo** do sistema (avaliações, documentos, verificações e "
                "evidências). A chave da API **não** entra no backup.")
    if st.button("Preparar backup", type="primary", icon=":material/inventory_2:"):
        with transacao() as s:
            st.session_state["_bkp"] = _json(catalogo.exportar_backup(s))
    if st.session_state.get("_bkp"):
        st.download_button("Baixar backup (.json)", st.session_state["_bkp"],
                           file_name=f"siap-ia-backup-{catalogo.hoje():%Y-%m-%d}.json", mime="application/json",
                           icon=":material/download:", on_click=lambda: st.session_state.pop("_bkp", None))
        st.caption("No Mac, guarde numa imagem de disco criptografada (Utilitário de Disco → Nova Imagem → "
                   "Imagem de Pasta → criptografia AES-256).")

with aba_rest:
    st.warning("A restauração **substitui todos os dados atuais** pelos do arquivo. A chave da API é mantida.",
               icon=":material/warning:")
    arquivo = st.file_uploader("Arquivo de backup do SIAP-IA (.json)", type=["json"], key="arquivo_restauracao")
    if arquivo is not None:
        try:
            dados = backup.ler_arquivo(arquivo.getvalue())
        except backup.ErroValidacao as erro:
            st.error(str(erro))
        else:
            cont = backup.resumo(dados)
            st.success(f"Backup válido, gerado em **{str(dados.get('gerado_em', '—'))[:16].replace('T', ' ')}**.",
                       icon=":material/task_alt:")
            principais = {"avaliacoes": "Avaliações", "documentos": "Documentos", "instrumentos": "Testes",
                          "verificacoes_satepsi": "Verificações", "conjuntos_dados": "Pesquisas",
                          "auditoria": "Auditoria"}
            cols = st.columns(len(principais))
            for col, (tabela, rotulo) in zip(cols, principais.items()):
                col.metric(rotulo, cont.get(tabela, 0), border=True)

            st.markdown("**1. Baixe uma cópia do estado atual** (por segurança):")
            with transacao() as s:
                atual = _json(catalogo.exportar_backup(s, registrar=False))
            st.download_button("Baixar backup do estado atual", atual, icon=":material/download:",
                               file_name=f"siap-ia-antes-da-restauracao-{catalogo.hoje():%Y-%m-%d}.json",
                               mime="application/json", key="bkp_antes")
            st.markdown("**2. Confirme digitando RESTAURAR:**")
            confirma = st.text_input("Confirmação", placeholder="RESTAURAR", label_visibility="collapsed")
            if st.button("Restaurar agora", type="primary", icon=":material/restore:",
                         disabled=confirma.strip().upper() != "RESTAURAR"):
                executar(lambda s: backup.restaurar(s, dados),
                         "Backup restaurado com sucesso. Os dados agora correspondem ao arquivo enviado.")

with aba_aud:
    with transacao() as s:
        registros = [
            {"Nº": r.id, "Quando": data_br(r.quando), "Ação": r.acao, "Entidade": r.entidade,
             "ID": r.entidade_id, "Detalhes": r.detalhes}
            for r in catalogo.listar_auditoria(s)
        ]
    st.caption("Últimos 500 registros, do mais recente para o mais antigo. Use a lupa da tabela para pesquisar.")
    st.dataframe(pd.DataFrame(registros), hide_index=True, width="stretch")

rodape()
