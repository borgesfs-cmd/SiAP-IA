"""Análise qualitativa de entrevistas e observações."""

import pandas as pd
import streamlit as st

from siap import avaliacoes as av
from siap import ia
from siap import qualitativo as q
from siap.ui import data_br, executar, iniciar_pagina, rodape, transacao

iniciar_pagina("Análise qualitativa", "Codifique trechos de entrevistas e observações e veja os temas que emergem.", "🧩", ["Escolha a avaliação.", "Em **Codificar**, escolha o registro, cole o trecho e atribua um código.", "Opcional: peça **sugestões à IA** e aceite as que fizerem sentido.", "Em **Resultados**, veja a matriz e as evidências de cada código."])

with transacao() as s:
    lista = [(a.id, f"{a.codigo} · {a.finalidade.nome} · {av.STATUS[a.status]}")
             for a in av.listar_avaliacoes(s) if a.status != av.CANCELADA]
    codigos = [(c.id, c.nome, c.descricao, c.ativo) for c in q.listar_codigos(s)]
    ia_ok, ia_motivo = ia.situacao(s)

# ---------------------------------------------------------- livro de códigos
with st.expander(f"📒 Livro de códigos ({len(codigos)})"):
    if codigos:
        st.dataframe(pd.DataFrame([{"Código": n, "Descrição": d, "Situação": "Ativo" if at else "Desativado"}
                                   for _, n, d, at in codigos]), hide_index=True, width="stretch")
    with st.form("novo_codigo", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        n_nome = c1.text_input("Novo código")
        n_desc = c2.text_input("Definição operacional")
        if st.form_submit_button("Criar código"):
            executar(lambda s: q.obter_ou_criar_codigo(s, n_nome, n_desc), "Código criado.")
    if codigos:
        rot_c = {c[0]: c[1] for c in codigos}
        alvo = st.selectbox("Editar código", list(rot_c), format_func=rot_c.get, key="cod_edit")
        _, e_n, e_d, e_a = next(c for c in codigos if c[0] == alvo)
        with st.form(f"editar_codigo_{alvo}"):
            nome = st.text_input("Nome", e_n)
            desc = st.text_input("Definição", e_d)
            ativo = st.checkbox("Ativo", e_a)
            if st.form_submit_button("Salvar código"):
                executar(lambda s: q.editar_codigo(s, alvo, nome=nome, descricao=desc, ativo=ativo), "Código salvo.")

if not lista:
    st.info("Crie uma avaliação e registre entrevistas/observações para analisar.")
    rodape()
    st.stop()

rot = dict(lista)
avaliacao_id = st.selectbox("Avaliação", list(rot), format_func=rot.get)
with transacao() as s:
    a = s.get(av.Avaliacao, avaliacao_id)
    registros = [(r.id, r.tipo, r.data, r.conteudo) for r in a.registros]
    itens = [(c.id, c.codigo.nome, c.registro_id, c.trecho, c.comentario, c.origem)
             for c in q.codificacoes_da_avaliacao(s, avaliacao_id)]
    m = q.matriz(s, avaliacao_id)

if not registros:
    st.info("Esta avaliação ainda não tem entrevistas ou observações registradas.")
    rodape()
    st.stop()

ativos = {c[0]: c[1] for c in codigos if c[3]}
rot_reg = {r[0]: f"{data_br(r[2])} · {r[1]} (#{r[0]})" for r in registros}

aba_cod, aba_ia, aba_res = st.tabs(["Codificar", "Sugestões da IA", f"Resultados ({len(itens)} trechos)"])

with aba_cod:
    reg_id = st.selectbox("Registro", list(rot_reg), format_func=rot_reg.get)
    st.text_area("Conteúdo do registro (copie daqui o trecho)", next(r[3] for r in registros if r[0] == reg_id),
                 height=200, disabled=True, key=f"ver_reg_{reg_id}")
    with st.form(f"codificar_{reg_id}", clear_on_submit=True):
        trecho = st.text_area("Trecho literal *")
        c1, c2 = st.columns(2)
        cod_existente = c1.selectbox("Código existente", [None, *ativos], format_func=lambda i: "—" if i is None else ativos[i])
        cod_novo = c2.text_input("…ou novo código")
        comentario = st.text_input("Memorando / comentário analítico")
        if st.form_submit_button("Codificar trecho"):
            def acao(s):
                cid = cod_existente
                if cod_novo.strip():
                    cid = q.obter_ou_criar_codigo(s, cod_novo).id
                if cid is None:
                    raise q.ErroValidacao("Escolha um código existente ou digite um novo.")
                return q.codificar(s, registro_id=reg_id, codigo_id=cid, trecho=trecho, comentario=comentario)
            executar(acao, "Trecho codificado.")

with aba_ia:
    if not ia_ok:
        st.info(ia_motivo)
    st.caption("A IA lê os registros desta avaliação (pseudonimizados) e sugere códigos com trechos literais. "
               "Sugestões cujo trecho não exista literalmente no registro são descartadas automaticamente.")
    if st.button("Sugerir códigos", disabled=not ia_ok, type="primary"):
        with st.spinner("Analisando registros…"):
            try:
                with transacao() as s:
                    st.session_state[f"ia_cod_{avaliacao_id}"] = ia.sugerir_codificacao(
                        s, registros=[(r[0], r[1], r[3]) for r in registros],
                        codigos_existentes=list(ativos.values()))
            except ia.ErroIA as erro:
                st.error(str(erro))
    sugestao = st.session_state.get(f"ia_cod_{avaliacao_id}")
    if sugestao:
        for obs in sugestao.dados.observacoes:
            st.caption(f"💡 {obs}")
        for i, item in enumerate(sugestao.dados.itens):
            with st.container(border=True):
                st.markdown(f"**{item.codigo}** · {rot_reg.get(item.registro_id, item.registro_id)}")
                st.markdown(f"> {item.trecho}")
                st.caption(item.justificativa)
                if st.button("Aceitar", key=f"aceitar_{avaliacao_id}_{i}"):
                    def aceitar(s, item=item):
                        cid = q.obter_ou_criar_codigo(s, item.codigo).id
                        return q.codificar(s, registro_id=item.registro_id, codigo_id=cid, trecho=item.trecho,
                                           comentario=item.justificativa, origem="ia_aceita")
                    executar(aceitar, "Sugestão aceita e codificada.")

with aba_res:
    if not itens:
        st.write("Nenhum trecho codificado ainda.")
    else:
        st.markdown("##### Matriz código × registro")
        st.dataframe(pd.DataFrame(
            [[m.contagens.get((c, r), 0) for r in m.registros] + [m.total_codigo(c)] for c in m.codigos],
            index=m.codigos, columns=[*m.registros, "Total"]), width="stretch")
        st.markdown("##### Evidências por código")
        for nome_cod in m.codigos:
            with st.expander(f"{nome_cod} ({m.total_codigo(nome_cod)})"):
                for cid, cnome, rid, tr, com, origem in itens:
                    if cnome != nome_cod:
                        continue
                    st.markdown(f"> {tr}")
                    st.caption(f"{rot_reg[rid]} · {'sugerido pela IA e aceito' if origem == 'ia_aceita' else 'manual'}"
                               + (f" · {com}" if com else ""))
                    if st.button("Remover", key=f"rm_{cid}"):
                        executar(lambda s, cid=cid: q.remover_codificacao(s, cid), "Codificação removida.")

rodape()
