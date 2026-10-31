"""Inventário inicial (Documento Mestre, seção 5).

São CANDIDATOS ao catálogo. Todos entram como "não verificado" e ficam bloqueados para
uso profissional até que a situação de cada versão seja conferida no SATEPSI.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .catalogo import auditar, criar_instrumento
from .models import Instrumento

NOTA = "Candidato do inventário inicial — conferir nome, edição/versão e situação no SATEPSI."

# (nome, sigla, categoria, construto, versões)
INVENTARIO_INICIAL: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("As Pirâmides Coloridas de Pfister", "Pfister", "Personalidade / expressivos", "Personalidade", ()),
    ("Teste de Zulliger", "Zulliger", "Personalidade / expressivos", "Personalidade", ()),
    ("Teste Palográfico", "Palográfico", "Personalidade / expressivos", "Personalidade", ()),
    ("Bateria Psicológica para Avaliação da Atenção", "BPA", "Atenção", "Atenção", ()),
    ("Teste de Atenção Concentrada", "AC", "Atenção", "Atenção concentrada", ()),
    ("Teste de Atenção Concentrada TEACO-FF", "TEACO-FF", "Atenção", "Atenção concentrada", ()),
    ("Teste de Atenção Dividida", "TEADI", "Atenção", "Atenção dividida", ()),
    ("Teste de Atenção Alternada", "TEALT", "Atenção", "Atenção alternada", ()),
    ("Teste d2 de Atenção", "d2", "Atenção", "Atenção concentrada", ("d2", "d2-R")),
    ("Teste Não Verbal de Inteligência R-1", "R-1", "Inteligência / raciocínio", "Inteligência geral", ()),
    ("Teste Não Verbal de Inteligência G-36", "G-36", "Inteligência / raciocínio", "Inteligência geral", ()),
    ("Teste Não Verbal de Inteligência G-38", "G-38", "Inteligência / raciocínio", "Inteligência geral", ()),
    ("Teste de Memória de Reconhecimento", "TEM-R", "Memória", "Memória de reconhecimento", ()),
    ("Teste Pictórico de Memória", "TEPIC-M", "Memória", "Memória visual", ()),
)


def carregar_inventario_inicial(s: Session) -> int:
    """Carrega o inventário apenas em banco vazio. Retorna quantos testes foram criados."""
    if s.scalar(select(func.count(Instrumento.id))):
        return 0
    for nome, sigla, categoria, construto, versoes in INVENTARIO_INICIAL:
        criar_instrumento(s, nome=nome, sigla=sigla, categoria=categoria, construto=construto,
                          observacoes=NOTA, versoes=list(versoes))
    auditar(s, "carregar_inventario_inicial", "sistema", None, quantidade=len(INVENTARIO_INICIAL))
    return len(INVENTARIO_INICIAL)
