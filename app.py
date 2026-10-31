"""SIAP-IA — ponto de entrada: tema, acesso e navegação agrupada."""

import streamlit as st

from siap.ui import aplicar_estilo, exigir_acesso

st.set_page_config(page_title="SIAP-IA", page_icon="static/icone.svg", layout="wide",
                   initial_sidebar_state="expanded")
aplicar_estilo()
st.logo("static/logo.svg", size="large", icon_image="static/icone.svg")
exigir_acesso()

st.navigation({
    "": [
        st.Page("paginas/inicio.py", title="Início", icon=":material/home:", default=True),
    ],
    "Atendimento": [
        st.Page("paginas/avaliacoes.py", title="Avaliações", icon=":material/assignment_ind:"),
        st.Page("paginas/documentos.py", title="Documentos", icon=":material/description:"),
        st.Page("paginas/biblioteca.py", title="Biblioteca de textos", icon=":material/library_books:"),
        st.Page("paginas/qualitativo.py", title="Análise qualitativa", icon=":material/format_quote:"),
    ],
    "Testes e conformidade": [
        st.Page("paginas/catalogo.py", title="Catálogo de testes", icon=":material/menu_book:"),
        st.Page("paginas/verificacao_satepsi.py", title="Verificação SATEPSI", icon=":material/verified:"),
        st.Page("paginas/finalidades.py", title="Finalidades", icon=":material/target:"),
    ],
    "Análises": [
        st.Page("paginas/paineis.py", title="Painéis", icon=":material/monitoring:"),
        st.Page("paginas/pesquisa.py", title="Pesquisa (estatística)", icon=":material/query_stats:"),
    ],
    "Inteligência artificial": [
        st.Page("paginas/consultor_ia.py", title="Consultor IA", icon=":material/auto_awesome:"),
        st.Page("paginas/chave_api.py", title="Chave da API", icon=":material/key:"),
    ],
    "Sistema": [
        st.Page("paginas/auditoria_backup.py", title="Auditoria e backup", icon=":material/shield:"),
    ],
}).run()
