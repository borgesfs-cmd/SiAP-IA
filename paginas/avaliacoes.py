"""Etapa 3 — Avaliações: caso codificado, entrevistas/observações, instrumentos e resultados."""

import pandas as pd
import streamlit as st

from siap import avaliacoes as av
from siap import catalogo, finalidades, satepsi
from siap.models import Avaliacao
from siap.ui import data_br, executar, iniciar_pagina, rodape, selo, transacao

iniciar_pagina("Avaliações")
st.caption(
    "Cada avaliação é identificada só por código (AV-AAAA-NNN). Não registre nome, CPF, contato ou "
    "outros dados que identifiquem a pessoa: a correspondência código ↔ pessoa fica fora do sistema."
)

with transacao() as s:
    finalidades_ativas = {f.id: f.nome for f in finalidades.listar_finalidades(s, somente_ativas=True)}
    todas_finalidades = {f.id: f.nome for f in finalidades.listar_finalidades(s)}
    lista = [(a.id, a.codigo, a.finalidade.nome, a.status, a.faixa_etaria, a.idade, a.data_inicio,
              a.data_conclusao) for a in av.listar_avaliacoes(s)]


def selecionar(avaliacao):
    st.session_state["avaliacao_sel"] = avaliacao.id


# ------------------------------------------------------------- nova avaliação
with st.expander("➕ Nova avaliação", expanded=not lista):
    if not finalidades_ativas:
        st.warning("Nenhuma finalidade ativa. Inclua ou reative uma em **Finalidades**.")
    else:
        with st.form("nova_avaliacao", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            n_finalidade = c1.selectbox("Finalidade *", list(finalidades_ativas), format_func=finalidades_ativas.get)
            n_faixa = c2.selectbox("Faixa etária *", av.FAIXAS_ETARIAS, index=2)
            n_idade = c3.number_input("Idade (anos)", 0, 120, value=None, step=1)
            c4, c5 = st.columns(2)
            n_escolaridade = c4.selectbox("Escolaridade", av.ESCOLARIDADES)
            n_inicio = c5.date_input("Início", value=catalogo.hoje(), max_value=catalogo.hoje(), format="DD/MM/YYYY")
            n_contexto = st.text_input("Contexto / solicitante (sem identificar pessoas)",
                                       placeholder="ex.: encaminhamento escolar; processo seletivo interno")
            n_demanda = st.text_area("Demanda e objetivos da avaliação")
            st.caption("Finalidade não encontrada? Inclua-a na página **Finalidades**.")
            if st.form_submit_button("Criar avaliação"):
                executar(
                    lambda s: av.criar_avaliacao(
                        s, finalidade_id=n_finalidade, faixa_etaria=n_faixa,
                        idade=int(n_idade) if n_idade is not None else None, escolaridade=n_escolaridade,
                        data_inicio=n_inicio, contexto=n_contexto, demanda=n_demanda,
                    ),
                    "Avaliação criada.", ao_concluir=selecionar,
                )

if not lista:
    rodape()
    st.stop()

# ------------------------------------------------------------------ lista
f1, f2 = st.columns(2)
filtro_status = f1.selectbox("Situação", ["Todas", *av.STATUS.values()], index=1)
filtro_fin = f2.selectbox("Finalidade", ["Todas", *todas_finalidades.values()])
filtradas = [
    a for a in lista
    if (filtro_status == "Todas" or av.STATUS[a[3]] == filtro_status)
    and (filtro_fin == "Todas" or a[2] == filtro_fin)
]
st.dataframe(
    pd.DataFrame([{
        "Código": codigo, "Finalidade": fin, "Situação": av.STATUS[status], "Faixa etária": faixa,
        "Idade": idade if idade is not None else "—", "Início": data_br(inicio), "Conclusão": data_br(fim),
    } for _, codigo, fin, status, faixa, idade, inicio, fim in filtradas]),
    hide_index=True, width="stretch",
)

rotulos = {a[0]: f"{a[1]} · {a[2]} · {av.STATUS[a[3]]}" for a in lista}
ids = [a[0] for a in filtradas] or [a[0] for a in lista]
atual = st.session_state.get("avaliacao_sel")
avaliacao_id = st.selectbox("Abrir avaliação", ids, format_func=rotulos.get,
                            index=ids.index(atual) if atual in ids else 0)
st.session_state["avaliacao_sel"] = avaliacao_id

# ---------------------------------------------------------------- detalhe
with transacao() as s:
    a: Avaliacao = s.get(Avaliacao, avaliacao_id)
    dados = dict(codigo=a.codigo, finalidade_id=a.finalidade_id, finalidade=a.finalidade.nome, status=a.status,
                 faixa=a.faixa_etaria, idade=a.idade, escolaridade=a.escolaridade, contexto=a.contexto,
                 demanda=a.demanda, inicio=a.data_inicio, conclusao=a.data_conclusao, tem_aplicacoes=bool(a.aplicacoes))
    registros = [(r.id, r.data, r.tipo, r.conteudo, r.editado_em) for r in a.registros]
    aplicacoes = []
    for ap in a.aplicacoes:
        situacao_agora = catalogo.situacao_versao(ap.versao, finalidade=a.finalidade)
        aplicacoes.append(dict(
            id=ap.id, versao=ap.versao.rotulo, data=ap.data_aplicacao, modalidade=ap.modalidade,
            observacoes=ap.observacoes, status_registro=ap.satepsi_status_no_registro,
            motivo_registro=ap.satepsi_motivo_no_registro, situacao_agora=situacao_agora,
            resultados=[dict(id=r.id, medida=r.medida, escore_bruto=r.escore_bruto, escore_padrao=r.escore_padrao,
                             percentil=r.percentil, classificacao=r.classificacao, referencia=r.referencia,
                             editado=r.editado_em is not None) for r in ap.resultados],
        ))
    opcoes = av.opcoes_de_versao(s, avaliacao_id)

em_andamento = dados["status"] == av.EM_ANDAMENTO
st.divider()
st.subheader(f"{dados['codigo']} — {dados['finalidade']}")
st.markdown(
    f"**Situação:** {av.STATUS[dados['status']]} · **Faixa etária:** {dados['faixa']}"
    + (f" · **Idade:** {dados['idade']}" if dados["idade"] is not None else "")
    + f" · **Início:** {data_br(dados['inicio'])}"
    + (f" · **Conclusão:** {data_br(dados['conclusao'])}" if dados["conclusao"] else "")
)

b1, b2, b3, _ = st.columns([1, 1, 1, 3])
if em_andamento:
    if b1.button("Concluir avaliação"):
        executar(lambda s: av.alterar_status(s, avaliacao_id, av.CONCLUIDA), "Avaliação concluída.")
    if b2.button("Cancelar avaliação"):
        executar(lambda s: av.alterar_status(s, avaliacao_id, av.CANCELADA), "Avaliação cancelada.")
else:
    st.info("Avaliação encerrada: os dados estão somente para leitura.")
    if b1.button("Reabrir avaliação"):
        executar(lambda s: av.alterar_status(s, avaliacao_id, av.EM_ANDAMENTO), "Avaliação reaberta.")

for ap in aplicacoes:
    if em_andamento and not ap["situacao_agora"].liberado:
        st.warning(f"⚠️ **{ap['versao']}** deixou de estar elegível para esta finalidade: "
                   f"{ap['situacao_agora'].motivo} Os dados registrados foram mantidos; requer análise profissional.")

aba_dados, aba_registros, aba_instrumentos = st.tabs(
    ["Dados da avaliação", f"Entrevistas e observações ({len(registros)})", f"Instrumentos e resultados ({len(aplicacoes)})"]
)

# ---- dados
with aba_dados:
    with st.form(f"dados_{avaliacao_id}"):
        fins = dict(finalidades_ativas)
        fins.setdefault(dados["finalidade_id"], todas_finalidades[dados["finalidade_id"]])
        lista_fins = list(fins)
        e_fin = st.selectbox("Finalidade", lista_fins, index=lista_fins.index(dados["finalidade_id"]),
                             format_func=fins.get, disabled=dados["tem_aplicacoes"] or not em_andamento,
                             help="Não pode ser alterada depois de registrar instrumentos.")
        c1, c2, c3 = st.columns(3)
        e_faixa = c1.selectbox("Faixa etária", av.FAIXAS_ETARIAS, index=av.FAIXAS_ETARIAS.index(dados["faixa"]))
        e_idade = c2.number_input("Idade (anos)", 0, 120, value=dados["idade"], step=1)
        e_esc = c3.selectbox("Escolaridade", av.ESCOLARIDADES, index=av.ESCOLARIDADES.index(dados["escolaridade"]))
        e_contexto = st.text_input("Contexto / solicitante", dados["contexto"])
        e_demanda = st.text_area("Demanda e objetivos", dados["demanda"], height=150)
        if st.form_submit_button("Salvar dados", disabled=not em_andamento):
            executar(
                lambda s: av.atualizar_avaliacao(
                    s, avaliacao_id, finalidade_id=e_fin, faixa_etaria=e_faixa,
                    idade=int(e_idade) if e_idade is not None else None, escolaridade=e_esc,
                    contexto=e_contexto, demanda=e_demanda,
                ),
                "Dados atualizados.",
            )

# ---- entrevistas e observações
with aba_registros:
    if em_andamento:
        with st.form(f"novo_registro_{avaliacao_id}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            r_tipo = c1.selectbox("Tipo", av.TIPOS_REGISTRO)
            r_data = c2.date_input("Data", value=catalogo.hoje(), max_value=catalogo.hoje(), format="DD/MM/YYYY")
            r_conteudo = st.text_area("Conteúdo", height=180,
                                      help="Descreva sem identificar a pessoa avaliada ou terceiros.")
            if st.form_submit_button("Adicionar registro"):
                executar(lambda s: av.adicionar_registro(s, avaliacao_id, tipo=r_tipo, data=r_data,
                                                         conteudo=r_conteudo), "Registro adicionado.")
    if not registros:
        st.write("Nenhum registro ainda.")
    for rid, rdata, rtipo, rconteudo, reditado in reversed(registros):
        with st.expander(f"{data_br(rdata)} · {rtipo}" + (" · editado" if reditado else "")):
            if em_andamento:
                with st.form(f"editar_registro_{rid}"):
                    novo = st.text_area("Conteúdo", rconteudo, height=180, key=f"txt_reg_{rid}")
                    if st.form_submit_button("Salvar alteração"):
                        executar(lambda s, rid=rid, novo=novo: av.editar_registro(s, rid, conteudo=novo),
                                 "Registro atualizado (versão anterior guardada na auditoria).")
            else:
                st.write(rconteudo)

# ---- instrumentos e resultados
with aba_instrumentos:
    liberadas = [o for o in opcoes if o.situacao.liberado]
    bloqueadas = [o for o in opcoes if not o.situacao.liberado]
    if em_andamento:
        st.markdown(f"**Registrar instrumento aplicado** — somente versões elegíveis para *{dados['finalidade']}*.")
        if liberadas:
            rot = {o.versao_id: o.rotulo for o in liberadas}
            with st.form(f"nova_aplicacao_{avaliacao_id}", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                i_versao = c1.selectbox("Teste / versão", list(rot), format_func=rot.get)
                i_data = c2.date_input("Data da aplicação", value=catalogo.hoje(), min_value=dados["inicio"],
                                       max_value=catalogo.hoje(), format="DD/MM/YYYY")
                i_modalidade = c3.selectbox("Modalidade", av.MODALIDADES)
                i_obs = st.text_area("Observações da aplicação (condições, comportamento durante a testagem…)")
                if st.form_submit_button("Registrar aplicação"):
                    executar(lambda s: av.registrar_aplicacao(
                        s, avaliacao_id, versao_id=i_versao, data_aplicacao=i_data, modalidade=i_modalidade,
                        observacoes=i_obs), "Aplicação registrada.")
        else:
            st.error("Nenhuma versão está elegível para esta finalidade. Registre as consultas na **Verificação SATEPSI**.")
        with st.expander(f"Versões bloqueadas para esta finalidade ({len(bloqueadas)})"):
            st.dataframe(pd.DataFrame([{"Teste / versão": o.rotulo, "SATEPSI": o.situacao.rotulo,
                                        "Motivo": o.situacao.motivo} for o in bloqueadas]),
                         hide_index=True, width="stretch")

    if not aplicacoes:
        st.write("Nenhum instrumento registrado.")
    for ap in aplicacoes:
        st.markdown("---")
        st.markdown(f"#### {ap['versao']}")
        st.markdown(
            f"{data_br(ap['data'])} · {ap['modalidade']} · No registro: "
            f"**{satepsi.ROTULOS.get(ap['status_registro'], ap['status_registro'])}** · Agora: {selo(ap['situacao_agora'])}"
        )
        st.caption(f"Conformidade no registro: {ap['motivo_registro']}")
        if ap["observacoes"]:
            st.write(ap["observacoes"])
        if ap["resultados"]:
            st.dataframe(pd.DataFrame([{
                "Medida": r["medida"], "Escore bruto": r["escore_bruto"], "Escore padronizado": r["escore_padrao"],
                "Percentil": r["percentil"], "Classificação": r["classificacao"], "Referência": r["referencia"],
                "Editado": "sim" if r["editado"] else "",
            } for r in ap["resultados"]]), hide_index=True, width="stretch")
        if not em_andamento:
            continue
        with st.expander("➕ Registrar resultado (transcrito do manual ou da plataforma oficial)"):
            with st.form(f"novo_resultado_{ap['id']}", clear_on_submit=True):
                medida = st.text_input("Medida / escala *", placeholder="ex.: Concentração, Total, Fator I")
                c1, c2, c3, c4 = st.columns(4)
                bruto = c1.text_input("Escore bruto")
                padrao = c2.text_input("Escore padronizado")
                percentil = c3.text_input("Percentil")
                classificacao = c4.text_input("Classificação")
                referencia = st.text_input("Referência *", placeholder="ex.: Manual 2ª ed., tabela 12, norma adultos")
                if st.form_submit_button("Salvar resultado"):
                    executar(lambda s, apid=ap["id"], c=dict(medida=medida, escore_bruto=bruto, escore_padrao=padrao,
                                                            percentil=percentil, classificacao=classificacao,
                                                            referencia=referencia):
                             av.adicionar_resultado(s, apid, **c), "Resultado registrado.")
        if ap["resultados"]:
            with st.expander("✏️ Corrigir um resultado"):
                por_id = {r["id"]: r for r in ap["resultados"]}
                rid = st.selectbox("Resultado", list(por_id), format_func=lambda i: por_id[i]["medida"],
                                   key=f"sel_res_{ap['id']}")
                r = por_id[rid]
                with st.form(f"editar_resultado_{rid}"):
                    medida = st.text_input("Medida / escala *", r["medida"])
                    c1, c2, c3, c4 = st.columns(4)
                    bruto = c1.text_input("Escore bruto", r["escore_bruto"])
                    padrao = c2.text_input("Escore padronizado", r["escore_padrao"])
                    percentil = c3.text_input("Percentil", r["percentil"])
                    classificacao = c4.text_input("Classificação", r["classificacao"])
                    referencia = st.text_input("Referência *", r["referencia"])
                    if st.form_submit_button("Salvar correção"):
                        executar(lambda s, rid=rid, c=dict(medida=medida, escore_bruto=bruto, escore_padrao=padrao,
                                                           percentil=percentil, classificacao=classificacao,
                                                           referencia=referencia):
                                 av.editar_resultado(s, rid, **c), "Resultado corrigido (anterior na auditoria).")

rodape()
