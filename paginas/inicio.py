"""Página inicial: boas-vindas, ações rápidas, primeiros passos, avisos e atividade recente."""

from datetime import datetime

import streamlit as st

from siap import inicio
from siap.catalogo import FUSO
from siap.ui import cartao_acao, data_br, exigir_acesso, rodape, transacao

exigir_acesso()
with transacao() as s:
    r = inicio.resumo(s)

hora = datetime.now(FUSO).hour
saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
nome = f", {r.nome.split()[0] if not r.nome.lower().startswith(('dra', 'dr.')) else r.nome}" if r.nome else ""
st.html(
    f'<div class="siap-heroi"><h2>{saudacao}{nome}! 👋</h2>'
    f'<p>{datetime.now(FUSO):%d/%m/%Y} · {r.avaliacoes_andamento} avaliação(ões) em andamento · '
    f'{r.versoes_elegiveis} de {r.versoes_total} versões de testes liberadas no SATEPSI</p></div>'
)
mensagem = st.session_state.pop("_mensagem_ok", None)
if mensagem:
    st.toast(mensagem, icon=":material/check_circle:")

st.write("")
st.markdown("#### O que você quer fazer agora?")
c = st.columns(4)
with c[0]:
    cartao_acao("nova_av", "🗂️", "Nova avaliação", "Abra um caso, registre entrevistas e testes.",
                "paginas/avaliacoes.py", "Ir para avaliações")
with c[1]:
    cartao_acao("doc", "📝", "Elaborar documento", "Laudo, atestado, relatório, parecer ou declaração.",
                "paginas/documentos.py", "Ir para documentos")
with c[2]:
    cartao_acao("satepsi", "✅", "Verificar teste", "Registre a consulta ao SATEPSI e libere o uso.",
                "paginas/verificacao_satepsi.py", "Ir para verificação")
with c[3]:
    cartao_acao("paineis", "📊", "Ver painéis", "Acompanhe seu trabalho em gráficos.",
                "paginas/paineis.py", "Ir para painéis")

st.write("")
esq, dir_ = st.columns([1.15, 1], gap="large")

with esq:
    with st.container(border=True):
        st.markdown("#### 🚀 Primeiros passos")
        st.progress(r.progresso, text=f"{round(r.progresso * 100)}% concluído")
        for p in r.passos:
            a, b = st.columns([0.8, 0.2], vertical_alignment="center")
            marca = "✅" if p.feito else ("➕" if p.opcional else "⬜")
            a.markdown(f"{marca} **{p.titulo}**{' · *opcional*' if p.opcional else ''}  \n"
                       f"<span style='opacity:.7;font-size:.9rem'>{p.descricao}</span>", unsafe_allow_html=True)
            if not p.feito:
                b.page_link(p.pagina, label="Fazer", icon=":material/arrow_forward:")

    with st.container(border=True):
        st.markdown("#### 🕒 Atividade recente")
        if not r.atividades:
            st.caption("Nenhuma atividade ainda. Comece pelos primeiros passos ao lado.")
        for at in r.atividades:
            st.markdown(f"{at.icone} {at.texto}  \n<span style='opacity:.6;font-size:.82rem'>{data_br(at.quando)}"
                        f"</span>", unsafe_allow_html=True)

with dir_:
    with st.container(border=True):
        st.markdown("#### 🔔 Avisos")
        if not r.avisos:
            st.success("Tudo em dia. Nenhum aviso no momento.", icon=":material/task_alt:")
        for i, aviso in enumerate(r.avisos):
            func = {"erro": st.error, "atencao": st.warning, "info": st.info}[aviso.nivel]
            icone = {"erro": ":material/error:", "atencao": ":material/schedule:", "info": ":material/info:"}[aviso.nivel]
            func(aviso.texto, icon=icone)
            st.page_link(aviso.pagina, label="Resolver", icon=":material/arrow_forward:")

    m1, m2 = st.columns(2)
    m1.metric("Em andamento", r.avaliacoes_andamento, border=True)
    m2.metric("Documentos pendentes", r.documentos_pendentes, border=True)
    m3, m4 = st.columns(2)
    m3.metric("Testes elegíveis", r.versoes_elegiveis, border=True)
    m4.metric("Testes no catálogo", r.versoes_total, border=True)

rodape()
