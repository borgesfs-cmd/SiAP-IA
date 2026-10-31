"""Página inicial: primeiros passos, avisos e atividade recente."""

from datetime import date, timedelta

from sqlalchemy import select

from siap import avaliacoes as av
from siap import catalogo, finalidades, inicio, satepsi
from siap import documentos as dc
from siap.inventario import carregar_inventario_inicial
from siap.models import Finalidade

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_primeiros_passos_avancam(fabrica):
    with fabrica.begin() as s:
        finalidades.carregar_finalidades_padrao(s)
        carregar_inventario_inicial(s)
        r = inicio.resumo(s, HOJE)
        assert r.progresso == 0 and r.versoes_total == 15 and r.versoes_elegiveis == 0
        assert [p.feito for p in r.passos] == [False] * 6 and r.passos[-1].opcional

        dc.salvar_perfil(s, nome="Dra. Teste", crp="06/1")
        vid = catalogo.listar_catalogo(s, HOJE)[0].versao_id
        catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=80),
                                       evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
        fid = s.scalar(select(Finalidade.id).limit(1))
        a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, referencia=HOJE)
        dc.criar_documento(s, a.id, "declaracao")
        catalogo.exportar_backup(s)

        r = inicio.resumo(s, HOJE)
        assert [p.feito for p in r.passos[:5]] == [True, True, True, False, True]
        assert r.progresso == 0.8 and r.nome == "Dra. Teste"
        assert r.avaliacoes_andamento == 1 and r.documentos_pendentes == 1
        textos = [x.texto for x in r.avisos]
        assert any("vence em" in t for t in textos)  # verificação de 80 dias vence em 10
        assert any("em elaboração" in t for t in textos)
        atividades = [x.texto for x in r.atividades]
        assert atividades[0] == "Backup exportado"
        assert any(a.codigo in t for t in atividades)
