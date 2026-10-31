"""SIAP-IA — ponto de entrada: acesso e navegação."""

import streamlit as st

from siap.ui import exigir_acesso

st.set_page_config(page_title="SIAP-IA", page_icon="🧠", layout="wide")
exigir_acesso()

st.navigation([
    st.Page("paginas/panorama.py", title="Panorama", icon="🏠", default=True),
    st.Page("paginas/avaliacoes.py", title="Avaliações", icon="🗒️"),
    st.Page("paginas/documentos.py", title="Documentos", icon="📄"),
    st.Page("paginas/catalogo.py", title="Catálogo de testes", icon="📚"),
    st.Page("paginas/verificacao_satepsi.py", title="Verificação SATEPSI", icon="✅"),
    st.Page("paginas/finalidades.py", title="Finalidades", icon="🎯"),
    st.Page("paginas/auditoria_backup.py", title="Auditoria e backup", icon="🗂️"),
]).run()
