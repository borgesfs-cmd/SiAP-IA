"""Etapa 4 — Documentos psicológicos: rascunho → revisado → aprovado → emitido → .docx."""

import streamlit as st

from siap import avaliacoes as av
from siap import documentos as dc
from siap.exportar_docx import gerar_docx
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Documentos psicológicos")

st.info(
    "**Como o nome da pessoa avaliada é tratado**\n\n"
    f"- O SIAP-IA **não grava** o nome de quem é avaliado. Nos textos, ele aparece como `{dc.TOKEN_NOME}`.\n"
    "- Ao **baixar o arquivo Word**, digite o nome no campo indicado: ele é inserido **somente no arquivo "
    "gerado** e descartado em seguida. Nada é salvo no banco, no backup ou na auditoria.\n"
    "- Para baixar de novo, digite o nome outra vez. Se deixar em branco, o marcador sai destacado em "
    "vermelho para você preencher no Word.\n"
    "- Nunca escreva o nome (nem CPF, telefone ou e-mail) dentro das seções do documento.",
    icon="🔒",
)
st.caption(
    "Estrutura baseada na Resolução CFP nº 06/2019. O sistema monta o rascunho apenas com dados "
    "registrados; análise e conclusão são redigidas por você. Trechos [[entre colchetes duplos]] precisam "
    "ser completados antes da aprovação. Confira os modelos com a norma vigente antes do uso real."
)

# ------------------------------------------------------------ perfil
with transacao() as s:
    perfil = dc.obter_perfil(s)
    p_dados = (perfil.nome, perfil.crp, perfil.titulacao, perfil.cidade_uf)

with st.expander("👤 Seus dados profissionais (aparecem na assinatura)", expanded=not (p_dados[0] and p_dados[1])):
    with st.form("perfil"):
        c1, c2 = st.columns([2, 1])
        nome = c1.text_input("Seu nome completo *", p_dados[0])
        crp = c2.text_input("CRP *", p_dados[1], placeholder="00/00000")
        c3, c4 = st.columns(2)
        titulacao = c3.text_input("Titulação / especialidade (opcional)", p_dados[2])
        cidade = c4.text_input("Cidade/UF (para local e data)", p_dados[3], placeholder="São Paulo/SP")
        if st.form_submit_button("Salvar dados profissionais"):
            executar(lambda s: dc.salvar_perfil(s, nome=nome, crp=crp, titulacao=titulacao, cidade_uf=cidade),
                     "Dados profissionais salvos.")

# ------------------------------------------------------- avaliação
with transacao() as s:
    avaliacoes = [(a.id, f"{a.codigo} · {a.finalidade.nome} · {av.STATUS[a.status]}")
                  for a in av.listar_avaliacoes(s) if a.status != av.CANCELADA]
if not avaliacoes:
    st.warning("Crie uma avaliação na página **Avaliações** antes de elaborar documentos.")
    rodape()
    st.stop()

rot_av = dict(avaliacoes)
ids_av = list(rot_av)
atual_av = st.session_state.get("doc_avaliacao")
avaliacao_id = st.selectbox("Avaliação", ids_av, format_func=rot_av.get,
                            index=ids_av.index(atual_av) if atual_av in ids_av else 0)
st.session_state["doc_avaliacao"] = avaliacao_id

with st.expander("➕ Novo documento para esta avaliação"):
    with st.form("novo_doc"):
        tipo = st.selectbox("Tipo", list(dc.MODELOS), format_func=lambda t: dc.MODELOS[t].titulo)
        st.caption(" · ".join(f"**{m.titulo}**: {m.descricao}" for m in dc.MODELOS.values()))
        if st.form_submit_button("Gerar rascunho"):
            executar(lambda s: dc.criar_documento(s, avaliacao_id, tipo), "Rascunho criado.",
                     ao_concluir=lambda d: st.session_state.__setitem__("doc_sel", d.id))

with transacao() as s:
    docs = [(d.id, d.codigo, d.titulo, d.status, d.criado_em) for d in dc.listar_documentos(s, avaliacao_id)]
if not docs:
    st.write("Nenhum documento para esta avaliação.")
    rodape()
    st.stop()

rot_doc = {d[0]: f"{d[1]} · {d[2]} · {dc.STATUS[d[3]]}" for d in docs}
ids_doc = list(rot_doc)
atual_doc = st.session_state.get("doc_sel")
documento_id = st.selectbox("Documento", ids_doc, format_func=rot_doc.get,
                            index=ids_doc.index(atual_doc) if atual_doc in ids_doc else 0)
st.session_state["doc_sel"] = documento_id

# ------------------------------------------------------------ editor
with transacao() as s:
    d = s.get(dc.DocumentoPsicologico, documento_id)
    info = dict(codigo=d.codigo, titulo=d.titulo, status=d.status, emitido_em=d.emitido_em, hash=d.hash_conteudo,
                substitui=s.get(dc.DocumentoPsicologico, d.substitui_id).codigo if d.substitui_id else None)
    sucessor = dc.substituido_por(s, documento_id)
    info["substituido_por"] = sucessor.codigo if sucessor else None
    secoes = [(sec.id, sec.titulo, sec.conteudo, sec.obrigatoria) for sec in d.secoes]
    checagem = dc.checar(s, documento_id)

st.divider()
st.subheader(f"{info['titulo']} — {info['codigo']}")
etapas = [dc.RASCUNHO, dc.REVISADO, dc.APROVADO, dc.EMITIDO]
st.markdown(" → ".join(f"**{dc.STATUS[e]}**" if e == info["status"] else dc.STATUS[e] for e in etapas))
if info["substitui"]:
    st.caption(f"Retificação do documento {info['substitui']}.")
if info["substituido_por"]:
    st.warning(f"Este documento foi substituído pela retificação {info['substituido_por']}.")

emitido = info["status"] == dc.EMITIDO
with st.form(f"secoes_{documento_id}"):
    novos = {}
    for sid, titulo, conteudo, obrigatoria in secoes:
        novos[sid] = st.text_area(f"{titulo}{' *' if obrigatoria else ''}", conteudo, height=220,
                                  disabled=emitido, key=f"sec_{sid}")
    salvar = st.form_submit_button("Salvar texto", disabled=emitido)
if salvar:
    executar(lambda s: dc.salvar_secoes(s, documento_id, novos),
             "Texto salvo." + (" O documento voltou a rascunho." if info["status"] in (dc.REVISADO, dc.APROVADO) else ""))

# ----------------------------------------------------------- checagem
st.markdown("#### Verificação")
for b in checagem.bloqueios:
    st.error(b)
for a in checagem.alertas:
    st.warning(a)
if checagem.pode_aprovar and not checagem.alertas:
    st.success("Nenhuma pendência encontrada.")

# -------------------------------------------------------------- fluxo
c1, c2, c3 = st.columns(3)
if info["status"] == dc.RASCUNHO:
    if c1.button("Marcar como revisado"):
        executar(lambda s: dc.marcar_revisado(s, documento_id), "Documento marcado como revisado.")
elif info["status"] == dc.REVISADO:
    confirmo = c1.checkbox("Revisei integralmente este documento e assumo sua autoria técnica.")
    if c2.button("Aprovar", disabled=not checagem.pode_aprovar):
        executar(lambda s: dc.aprovar(s, documento_id, confirmo_revisao_e_autoria=confirmo), "Documento aprovado.")
elif info["status"] == dc.APROVADO:
    c1.write("Após emitido, o conteúdo fica congelado e recebe um código de integridade.")
    if c2.button("Emitir documento", type="primary"):
        executar(lambda s: dc.emitir(s, documento_id), "Documento emitido.")
else:
    c1.write(f"Emitido em {data_br(info['emitido_em'])}.")
    c1.caption(f"SHA-256: `{info['hash']}`")
    if not info["substituido_por"] and c2.button("Retificar (criar novo rascunho)"):
        executar(lambda s: dc.retificar(s, documento_id), "Retificação criada como rascunho.",
                 ao_concluir=lambda novo: st.session_state.__setitem__("doc_sel", novo.id))

# ------------------------------------------------------------ download
st.markdown("#### Arquivo Word")
nome_pessoa = st.text_input(
    "Nome da pessoa avaliada (usado só para gerar este arquivo; não é gravado)",
    key=f"nome_{documento_id}", type="default",
)
with transacao() as s:
    conteudo, final = dc.conteudo_para_exportar(s, documento_id)
arquivo = gerar_docx(conteudo, final=final, nome_pessoa=nome_pessoa)
st.download_button(
    "Baixar documento final (.docx)" if final else "Baixar prévia com marca de RASCUNHO (.docx)",
    arquivo, file_name=f"{info['codigo'].replace('/', '_')}{'' if final else '_RASCUNHO'}.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    on_click=lambda: st.session_state.__setitem__(f"nome_{documento_id}", ""),  # descarta o nome após baixar
)
st.caption("Para PDF: abra o arquivo no Word ou Pages e use “Exportar/Salvar como PDF”. Assine e rubrique "
           "conforme a norma.")
rodape()
