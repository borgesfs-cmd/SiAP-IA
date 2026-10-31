"""Consultor IA (com cliente simulado — nenhuma chamada real) e análise qualitativa."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from siap import avaliacoes as av
from siap import catalogo, finalidades, ia
from siap import documentos as dc
from siap import qualitativo as q
from siap.models import Finalidade, RegistroAuditoria

HOJE = date(2026, 10, 31)
RELATO = "Relata dificuldade para manter a atenção em reuniões longas. Diz que dorme pouco desde março."


class ClienteFalso:
    """Imita client.beta.messages.parse e guarda o pedido enviado."""

    def __init__(self, resposta, stop_reason="end_turn"):
        self.pedidos, self._resposta, self._stop = [], resposta, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.pedidos.append(kwargs)
        return SimpleNamespace(parsed_output=self._resposta, stop_reason=self._stop, model=kwargs["model"],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=20))

    @property
    def enviado(self) -> str:
        p = self.pedidos[-1]
        return p["system"] + "\n" + "\n".join(m["content"] for m in p["messages"])


@pytest.fixture
def s(fabrica):
    with fabrica.begin() as sessao:
        finalidades.carregar_finalidades_padrao(sessao)
        yield sessao


@pytest.fixture
def avaliacao(s):
    fid = s.scalar(select(Finalidade.id).where(Finalidade.nome == "Avaliação neuropsicológica"))
    a = av.criar_avaliacao(s, finalidade_id=fid, faixa_etaria="Adulto", data_inicio=HOJE, demanda="Queixa atencional.",
                           referencia=HOJE)
    av.adicionar_registro(s, a.id, tipo="Entrevista inicial", data=HOJE, conteudo=RELATO, referencia=HOJE)
    return a


# ------------------------------------------------------------- IA: regras

def test_pseudonimizacao():
    texto = f"{dc.TOKEN_NOME}, caso AV-2026-001/LAU-2, CPF 123.456.789-09, a@b.com, (11) 98765-4321."
    p = ia.pseudonimizar(texto)
    assert "[PESSOA AVALIADA]" in p and "[CASO]" in p and p.count("[REMOVIDO]") == 3
    for proibido in ("AV-2026", "123.456", "a@b.com", "98765"):
        assert proibido not in p


def test_numeros_novos():
    assert ia.numeros_novos("Percentil 55 e QI 112", "percentil 55") == ["112"]
    assert ia.numeros_novos("escore 4,5", "escore 4.5") == []


def test_ia_desligada_por_padrao_e_exige_chave(s, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ok, motivo = ia.situacao(s)
    assert not ok and "desligado" in motivo
    ia.definir_consentimento(s, True)
    ok, motivo = ia.situacao(s)
    assert not ok and "ANTHROPIC_API_KEY" in motivo
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste")
    assert ia.situacao(s) == (True, "")
    with pytest.raises(ia.ErroIA):
        ia.definir_consentimento(s, False)
        ia.revisar_secao(s, tipo_documento="Laudo", titulo_secao="Análise", texto="x", dados_registrados="y")


def test_revisao_envia_texto_pseudonimizado_e_audita_so_metadados(s, avaliacao):
    falso = ClienteFalso(ia.RevisaoRedacao(texto_sugerido="Texto revisado com percentil 99.",
                                           observacoes=["ok"], alertas=[]))
    r = ia.revisar_secao(s, tipo_documento="Laudo", titulo_secao="Análise",
                         texto=f"{dc.TOKEN_NOME} obteve percentil 55 ({avaliacao.codigo}).",
                         dados_registrados="CPF 123.456.789-09; percentil 55", cliente=falso)
    pedido = falso.pedidos[-1]
    assert pedido["model"] == "claude-opus-5-5" and pedido["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in pedido["betas"]
    assert dc.TOKEN_NOME not in falso.enviado and avaliacao.codigo not in falso.enviado
    assert "123.456.789-09" not in falso.enviado
    assert r.numeros_nao_encontrados == ["99"]
    log = s.scalars(select(RegistroAuditoria).where(RegistroAuditoria.acao == "consulta_ia")).one()
    detalhes = json.loads(log.detalhes)
    assert detalhes["funcao"] == "revisar_secao" and "percentil" not in log.detalhes


def test_recusa_vira_erro_amigavel(s):
    falso = ClienteFalso(None, stop_reason="refusal")
    with pytest.raises(ia.ErroIA, match="recusou"):
        ia.revisar_secao(s, tipo_documento="Laudo", titulo_secao="Análise", texto="x", dados_registrados="y",
                         cliente=falso)


def test_consultor_descarta_instrumentos_fora_da_lista(s):
    falso = ClienteFalso(ia.RespostaConsultor(resposta="Use entrevista e o BPA.",
                                              instrumentos_sugeridos=["BPA — BPA", "Teste Inventado"],
                                              cautelas=[]))
    r = ia.consultar(s, pergunta="O que usar?", contexto="Adulto", instrumentos_elegiveis=["BPA — BPA"],
                     cliente=falso)
    assert r.dados.instrumentos_sugeridos == ["BPA — BPA"]
    assert any("Teste Inventado" in c for c in r.dados.cautelas)


def test_sugestao_de_codigos_so_aceita_trechos_literais(s, avaliacao):
    rid = avaliacao.registros[0].id
    falso = ClienteFalso(ia.SugestaoCodificacao(itens=[
        ia.ItemCodificacao(registro_id=rid, trecho="dificuldade para manter a atenção", codigo="Atenção",
                           justificativa="queixa"),
        ia.ItemCodificacao(registro_id=rid, trecho="problemas graves de memória", codigo="Memória",
                           justificativa="inventado"),
        ia.ItemCodificacao(registro_id=999, trecho="dorme pouco", codigo="Sono", justificativa="id errado"),
    ], observacoes=[]))
    r = ia.sugerir_codificacao(s, registros=[(rid, "Entrevista inicial", RELATO)], codigos_existentes=[],
                               cliente=falso)
    assert [i.codigo for i in r.dados.itens] == ["Atenção"]
    assert any("2 sugestão" in o for o in r.dados.observacoes)


# ------------------------------------------------------------ qualitativo

def test_codificacao_manual_e_matriz(s, avaliacao):
    rid = avaliacao.registros[0].id
    cod = q.obter_ou_criar_codigo(s, "Sono", "Queixas sobre sono")
    assert q.obter_ou_criar_codigo(s, "sono").id == cod.id  # sem duplicar
    q.codificar(s, registro_id=rid, codigo_id=cod.id, trecho="dorme   pouco desde março")  # espaços normalizados
    with pytest.raises(catalogo.ErroValidacao, match="literal"):
        q.codificar(s, registro_id=rid, codigo_id=cod.id, trecho="não dorme nunca")
    with pytest.raises(catalogo.ErroValidacao, match="já está"):
        q.codificar(s, registro_id=rid, codigo_id=cod.id, trecho="dorme   pouco desde março")
    m = q.matriz(s, avaliacao.id)
    assert m.codigos == ["Sono"] and m.total_codigo("Sono") == 1


def test_codigo_desativado_nao_codifica_e_remocao_audita(s, avaliacao):
    rid = avaliacao.registros[0].id
    cod = q.obter_ou_criar_codigo(s, "Atenção")
    item = q.codificar(s, registro_id=rid, codigo_id=cod.id, trecho="manter a atenção", origem="ia_aceita")
    q.remover_codificacao(s, item.id)
    assert q.codificacoes_da_avaliacao(s, avaliacao.id) == []
    q.editar_codigo(s, cod.id, nome="Atenção", descricao="", ativo=False)
    with pytest.raises(catalogo.ErroValidacao, match="desativado"):
        q.codificar(s, registro_id=rid, codigo_id=cod.id, trecho="manter a atenção")
    acoes = {r.acao for r in s.scalars(select(RegistroAuditoria))}
    assert {"codificar_trecho", "remover_codificacao", "editar_codigo_qualitativo"} <= acoes


def test_comentario_com_identificador_recusado(s, avaliacao):
    cod = q.obter_ou_criar_codigo(s, "Sono")
    with pytest.raises(catalogo.ErroValidacao, match="identificação direta"):
        q.codificar(s, registro_id=avaliacao.registros[0].id, codigo_id=cod.id, trecho="dorme pouco",
                    comentario="ligar 11 98765-4321")
