"""Etapa 4 — Documentos psicológicos: rascunho → revisado → aprovado → emitido → .docx."""

import streamlit as st

from siap import avaliacoes as av
from siap import documentos as dc
from siap import biblioteca, ia
from siap.exportar_docx import gerar_docx, gerar_pdf
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Documentos", "Laudos, atestados, relatórios, pareceres e declarações conforme a Resolução CFP 06/2019.", "📝", ["Preencha seus **dados profissionais** (uma vez).", "Escolha a avaliação e clique no tipo de documento para gerar o rascunho.", "Complete os trechos marcados com [[...]] e salve.", "Marque como **revisado**, **aprove** e **emita**.", "Para baixar o Word, digite o nome da pessoa no campo indicado — ele não é gravado."])

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

ICONES_DOC = {"laudo": "📋", "atestado": "🩺", "relatorio": "🗒️", "parecer": "⚖️", "declaracao": "✉️"}
with st.expander("➕ Novo documento para esta avaliação", expanded=False):
    st.caption("Clique no tipo para gerar o rascunho com os dados já registrados da avaliação.")
    colunas_tipo = st.columns(len(dc.MODELOS))
    for coluna, (chave_tipo, modelo) in zip(colunas_tipo, dc.MODELOS.items()):
        with coluna, st.container(border=True, key=f"cartao_doc_{chave_tipo}"):
            st.html(f'<div class="siap-cartao-ic">{ICONES_DOC[chave_tipo]}</div>'
                    f'<div class="siap-cartao-tit">{modelo.titulo}</div>'
                    f'<div class="siap-cartao-txt">{modelo.descricao}</div>')
            if st.button("Gerar rascunho", key=f"gerar_{chave_tipo}", use_container_width=True):
                executar(lambda s, t_=chave_tipo: dc.criar_documento(s, avaliacao_id, t_), "Rascunho criado.",
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
    secoes_info = [(sec.id, sec.titulo, sec.conteudo, sec.obrigatoria, sec.chave) for sec in d.secoes]
    checagem = dc.checar(s, documento_id)
    dados_registrados = dc.resumo_dados_registrados(d.avaliacao)
    ia_ok, ia_motivo = ia.situacao(s)

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

# ------------------------------------------------- biblioteca de textos
if not emitido:
    with st.expander("📚 Inserir trecho da biblioteca"):
        chaves_sec = {sid: (titulo, chave) for sid, titulo, _, _, chave in secoes_info}
        ids_sec = list(chaves_sec)
        preferida = next((i for i in ids_sec if chaves_sec[i][1] in ("analise", "conclusao", "texto")), ids_sec[0])
        sec_alvo = st.selectbox("Seção", ids_sec, format_func=lambda i: chaves_sec[i][0],
                                index=ids_sec.index(preferida), key=f"bib_sec_{documento_id}")
        with transacao() as s:
            disponiveis = [(tr.id, tr.titulo, tr.texto) for tr in biblioteca.listar(s, secao=chaves_sec[sec_alvo][1])]
        if not disponiveis:
            st.caption("Nenhum trecho para esta seção.")
        for tid, titulo_tr, texto_tr in disponiveis:
            c_txt, c_btn = st.columns([5, 1], vertical_alignment="center")
            c_txt.markdown(f"**{titulo_tr}**  \n<span style='opacity:.7;font-size:.88rem'>"
                           f"{texto_tr[:160] + ('…' if len(texto_tr) > 160 else '')}</span>", unsafe_allow_html=True)
            if c_btn.button("Inserir", key=f"ins_{documento_id}_{tid}", icon=":material/add:"):
                executar(lambda s, tid=tid: biblioteca.inserir_em_secao(s, documento_id=documento_id,
                                                                         secao_id=sec_alvo, trecho_id=tid),
                         "Trecho inserido no fim da seção.",
                         ao_concluir=lambda _: st.session_state.pop(f"sec_{sec_alvo}", None))
        st.page_link("paginas/biblioteca.py", label="Gerenciar a biblioteca", icon=":material/library_books:")

# --------------------------------------------------------- revisão por IA
if not emitido:
    with st.expander("💡 Revisar redação com o Consultor IA"):
        if not ia_ok:
            st.info(ia_motivo)
        rot_sec = {sid: titulo for sid, titulo, _, _ in secoes}
        sec_id = st.selectbox("Seção", list(rot_sec), format_func=rot_sec.get, key=f"ia_sec_{documento_id}")
        st.caption("Envia a seção e os dados registrados da avaliação, pseudonimizados. A sugestão só substitui "
                   "o texto se você clicar em “Usar sugestão”.")
        if st.button("Pedir revisão", disabled=not ia_ok, key=f"ia_rev_{documento_id}"):
            texto_atual = next(c for sid, _, c, _ in secoes if sid == sec_id)
            with st.spinner("Revisando…"):
                try:
                    with transacao() as s:
                        st.session_state[f"ia_rev_{sec_id}"] = ia.revisar_secao(
                            s, tipo_documento=info["titulo"], titulo_secao=rot_sec[sec_id], texto=texto_atual,
                            dados_registrados=dados_registrados)
                except ia.ErroIA as erro:
                    st.error(str(erro))
        rev = st.session_state.get(f"ia_rev_{sec_id}")
        if rev:
            st.markdown("**Texto sugerido** (o marcador de nome volta ao formato do sistema ao usar):")
            sugerido = rev.dados.texto_sugerido.replace("[PESSOA AVALIADA]", dc.TOKEN_NOME)
            st.text_area("Sugestão", sugerido, height=220, disabled=True, key=f"ia_txt_{sec_id}")
            for o in rev.dados.observacoes:
                st.caption(f"📝 {o}")
            for a in rev.dados.alertas:
                st.warning(a)
            if rev.numeros_nao_encontrados:
                st.warning("Números na sugestão que não constam do texto nem dos dados registrados: "
                           + ", ".join(rev.numeros_nao_encontrados) + ". Confira antes de usar.")
            if st.button("Usar sugestão nesta seção", key=f"ia_usar_{sec_id}"):
                st.session_state.pop(f"ia_rev_{sec_id}", None)
                executar(lambda s: dc.salvar_secoes(s, documento_id, {sec_id: sugerido}),
                         "Sugestão aplicada à seção (texto anterior guardado na auditoria).",
                         ao_concluir=lambda _: st.session_state.pop(f"sec_{sec_id}", None))  # recarrega o editor

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
st.markdown("#### Baixar o documento")
nome_pessoa = st.text_input(
    "Nome da pessoa avaliada (usado só para gerar o arquivo; não é gravado)",
    key=f"nome_{documento_id}", type="default",
)
with transacao() as s:
    conteudo, final = dc.conteudo_para_exportar(s, documento_id)
base = f"{info['codigo'].replace('/', '_')}{'' if final else '_RASCUNHO'}"


def _descartar_nome():
    st.session_state[f"nome_{documento_id}"] = ""  # descarta o nome após baixar


b_pdf, b_doc = st.columns(2)
b_pdf.download_button(
    "Baixar PDF" if final else "Prévia em PDF (RASCUNHO)", gerar_pdf(conteudo, final=final, nome_pessoa=nome_pessoa),
    file_name=f"{base}.pdf", mime="application/pdf", icon=":material/picture_as_pdf:", type="primary",
    use_container_width=True, on_click=_descartar_nome,
)
b_doc.download_button(
    "Baixar Word (.docx)" if final else "Prévia em Word (RASCUNHO)", gerar_docx(conteudo, final=final, nome_pessoa=nome_pessoa),
    file_name=f"{base}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    icon=":material/description:", use_container_width=True, on_click=_descartar_nome,
)
st.caption("O PDF já sai pronto para assinatura (física ou digital, ex.: gov.br). Use o Word se precisar "
           "ajustar a formatação. Assine e rubrique conforme a norma.")
rodape()
