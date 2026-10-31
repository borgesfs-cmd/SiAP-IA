"""Regra de bloqueio SATEPSI (critério de aceitação 2 do Documento Mestre)."""

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from siap import satepsi

HOJE = date(2026, 10, 31)


@dataclass
class V:
    id: int
    status: str
    data_consulta: date
    validade_dias: int = 90
    condicoes: str = ""


def test_sem_verificacao_fica_bloqueado():
    s = satepsi.avaliar([], HOJE)
    assert s.status == satepsi.NAO_VERIFICADO and not s.liberado


def test_favoravel_dentro_da_validade_fica_elegivel():
    s = satepsi.avaliar([V(1, satepsi.FAVORAVEL, HOJE - timedelta(days=10))], HOJE)
    assert s.liberado and s.vence_em == HOJE + timedelta(days=80)


@pytest.mark.parametrize("status", [satepsi.DESFAVORAVEL, satepsi.RESTRITO,
                                    satepsi.EM_AVALIACAO, satepsi.NAO_LOCALIZADO])
def test_demais_situacoes_bloqueiam(status):
    assert not satepsi.avaliar([V(1, status, HOJE)], HOJE).liberado


def test_status_desconhecido_bloqueia():
    assert not satepsi.avaliar([V(1, "qualquer", HOJE)], HOJE).liberado


def test_favoravel_vencido_bloqueia():
    s = satepsi.avaliar([V(1, satepsi.FAVORAVEL, HOJE - timedelta(days=91))], HOJE)
    assert not s.liberado and s.vencida


def test_ultimo_dia_de_validade_ainda_elegivel():
    assert satepsi.avaliar([V(1, satepsi.FAVORAVEL, HOJE - timedelta(days=90))], HOJE).liberado


def test_consulta_mais_recente_prevalece():
    hist = [V(1, satepsi.FAVORAVEL, HOJE - timedelta(days=20)), V(2, satepsi.DESFAVORAVEL, HOJE - timedelta(days=5))]
    assert not satepsi.avaliar(hist, HOJE).liberado
    hist = [V(1, satepsi.DESFAVORAVEL, HOJE - timedelta(days=20)), V(2, satepsi.FAVORAVEL, HOJE - timedelta(days=5))]
    assert satepsi.avaliar(hist, HOJE).liberado


def test_registro_tardio_de_consulta_antiga_nao_sobrepoe_a_recente():
    hist = [V(1, satepsi.DESFAVORAVEL, HOJE - timedelta(days=2)), V(2, satepsi.FAVORAVEL, HOJE - timedelta(days=30))]
    assert not satepsi.avaliar(hist, HOJE).liberado


def test_mesma_data_vale_o_registrado_por_ultimo():
    hist = [V(1, satepsi.FAVORAVEL, HOJE), V(2, satepsi.DESFAVORAVEL, HOJE)]
    assert not satepsi.avaliar(hist, HOJE).liberado


def test_data_futura_bloqueia():
    assert not satepsi.avaliar([V(1, satepsi.FAVORAVEL, HOJE + timedelta(days=1))], HOJE).liberado
