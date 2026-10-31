"""Restauração de backup: ida e volta completa, validações e preservação da chave da API."""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from siap import avaliacoes as av
from siap import backup, catalogo, finalidades, satepsi, segredos
from siap import documentos as dc
from siap import pesquisa as pq
from siap.models import Avaliacao, Finalidade, SegredoCifrado

HOJE = date(2026, 10, 31)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def _sem_auditoria(d):
    return {k: v for k, v in d.items() if k not in ("auditoria", "gerado_em")}


def _popular(s):
    finalidades.carregar_finalidades_padrao(s)
    dc.salvar_perfil(s, nome="Dra. Teste", crp="06/1")
    inst = catalogo.criar_instrumento(s, nome="Teste A", sigla="TA", categoria="Atenção")
    vid = inst.versoes[0].id
    catalogo.registrar_verificacao(s, vid, status=satepsi.FAVORAVEL, data_consulta=HOJE - timedelta(days=1),
                                   evidencia_nome="e.png", evidencia_tipo="image/png", evidencia=PNG, referencia=HOJE)
    fid = s.scalar(select(Finalidade.id).limit(1))
    a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, demanda="Queixa.",
                           referencia=HOJE)
    ap = av.registrar_aplicacao(s, a.id, versao_id=vid, data_aplicacao=HOJE, modalidade="Outra", referencia=HOJE)
    av.adicionar_resultado(s, ap.id, medida="Total", percentil="50", referencia="Manual")
    d = dc.criar_documento(s, a.id, "atestado")
    dc.salvar_secoes(s, d.id, {sec.id: dc._PENDENTE.sub("ok", sec.conteudo) for sec in d.secoes})
    dc.marcar_revisado(s, d.id)
    dc.aprovar(s, d.id, confirmo_revisao_e_autoria=True, referencia=HOJE)
    dc.emitir(s, d.id, referencia=HOJE)
    pq.criar_exemplo(s)


def test_ida_e_volta_restaura_exatamente(fabrica, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "senha")
    with fabrica.begin() as s:
        _popular(s)
        segredos.salvar(s, segredos.CHAVE_ANTHROPIC, "sk-ant-teste-backup-1234567890")
        original = json.loads(json.dumps(catalogo.exportar_backup(s, registrar=False)))
    with fabrica.begin() as s:  # mudanças posteriores que devem sumir
        fid = s.scalar(select(Finalidade.id).limit(1))
        av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Idoso", data_inicio=HOJE, referencia=HOJE)
        finalidades.criar_finalidade(s, nome="Nova finalidade")
    with fabrica.begin() as s:
        contagem = backup.restaurar(s, backup.ler_arquivo(json.dumps(original).encode()))
        assert contagem["avaliacoes"] == 1
    with fabrica.begin() as s:
        depois = catalogo.exportar_backup(s, registrar=False)
        assert _sem_auditoria(depois) == _sem_auditoria(original)
        assert s.scalar(select(func.count(Avaliacao.id))) == 1
        # chave da API preservada e evidência binária íntegra
        assert s.get(SegredoCifrado, segredos.CHAVE_ANTHROPIC) is not None
        assert catalogo.carregar_evidencia(s, 1).evidencia == PNG
        # a numeração continua funcionando após restaurar
        fid = s.scalar(select(Finalidade.id).limit(1))
        nova = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, referencia=HOJE)
        assert nova.codigo == "AV-2026-002"
        acoes = [r.acao for r in catalogo.listar_auditoria(s, limite=5)]
        assert "restaurar_backup" in acoes


@pytest.mark.parametrize("conteudo,trecho", [
    (b"isto nao e json", "JSON"),
    (json.dumps({"formato": "outro"}).encode(), "não é um backup"),
    (json.dumps({"formato": "siap-ia-backup", "versao_formato": 1}).encode(), "Versão"),
    (json.dumps({"formato": "siap-ia-backup", "versao_formato": 2}).encode(), "essenciais"),
])
def test_arquivos_invalidos_sao_recusados_sem_apagar_nada(fabrica, conteudo, trecho):
    with fabrica.begin() as s:
        finalidades.carregar_finalidades_padrao(s)
        with pytest.raises(catalogo.ErroValidacao, match=trecho):
            backup.ler_arquivo(conteudo)
        assert s.scalar(select(func.count(Finalidade.id))) > 0
