"""Modelo de dados do SIAP-IA (Etapas 1 e 2: catálogo, SATEPSI e auditoria)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


verificacao_finalidades = Table(
    "verificacao_finalidades",
    Base.metadata,
    Column("verificacao_id", ForeignKey("verificacoes_satepsi.id"), primary_key=True),
    Column("finalidade_id", ForeignKey("finalidades.id"), primary_key=True),
)


class Finalidade(Base):
    """Finalidade da avaliação (padrões + cadastradas pelo usuário). Nunca apagada: só desativada."""

    __tablename__ = "finalidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    padrao: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class Instrumento(Base):
    """Teste psicológico do catálogo. Estar no catálogo NÃO autoriza uso profissional."""

    __tablename__ = "instrumentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    sigla: Mapped[str] = mapped_column(String(40), default="")
    categoria: Mapped[str] = mapped_column(String(60))
    construto: Mapped[str] = mapped_column(String(200), default="")
    descricao: Mapped[str] = mapped_column(Text, default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    versoes: Mapped[list[VersaoInstrumento]] = relationship(
        back_populates="instrumento", order_by="VersaoInstrumento.id"
    )


class VersaoInstrumento(Base):
    """Versão/edição específica. A situação SATEPSI é sempre avaliada por versão."""

    __tablename__ = "versoes_instrumento"
    __table_args__ = (UniqueConstraint("instrumento_id", "nome_versao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrumento_id: Mapped[int] = mapped_column(ForeignKey("instrumentos.id"))
    nome_versao: Mapped[str] = mapped_column(String(80))
    edicao: Mapped[str] = mapped_column(String(80), default="")
    editora: Mapped[str] = mapped_column(String(120), default="")
    populacao: Mapped[str] = mapped_column(String(200), default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    instrumento: Mapped[Instrumento] = relationship(back_populates="versoes")
    verificacoes: Mapped[list[VerificacaoSATEPSI]] = relationship(
        back_populates="versao", order_by="VerificacaoSATEPSI.id"
    )

    @property
    def rotulo(self) -> str:
        return f"{self.instrumento.nome} — {self.nome_versao}"


class VerificacaoSATEPSI(Base):
    """Registro de uma consulta ao SATEPSI. Somente inclusão: nunca é editado nem apagado.

    Correções são feitas registrando uma nova verificação; o histórico fica preservado.
    """

    __tablename__ = "verificacoes_satepsi"

    id: Mapped[int] = mapped_column(primary_key=True)
    versao_id: Mapped[int] = mapped_column(ForeignKey("versoes_instrumento.id"))
    status: Mapped[str] = mapped_column(String(20))
    data_consulta: Mapped[date] = mapped_column(Date)
    validade_dias: Mapped[int] = mapped_column(Integer)
    fonte: Mapped[str] = mapped_column(String(300))
    condicoes: Mapped[str] = mapped_column(Text, default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    evidencia_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidencia_tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidencia_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidencia: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    # Vazio = válida para todas as finalidades; preenchido = somente as listadas.
    abrange_todas_finalidades: Mapped[bool] = mapped_column(Boolean, default=True)

    versao: Mapped[VersaoInstrumento] = relationship(back_populates="verificacoes")
    finalidades: Mapped[list[Finalidade]] = relationship(secondary=verificacao_finalidades)

    @property
    def finalidades_ids(self) -> frozenset[int] | None:
        """None = todas as finalidades."""
        if self.abrange_todas_finalidades:
            return None
        return frozenset(f.id for f in self.finalidades)


class RegistroAuditoria(Base):
    """Trilha de auditoria (somente inclusão)."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    acao: Mapped[str] = mapped_column(String(60))
    entidade: Mapped[str] = mapped_column(String(60))
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[str] = mapped_column(Text, default="{}")


class Avaliacao(Base):
    """Processo de avaliação psicológica. Identificado SOMENTE por código (sem nome/CPF/contato)."""

    __tablename__ = "avaliacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    finalidade_id: Mapped[int] = mapped_column(ForeignKey("finalidades.id"))
    faixa_etaria: Mapped[str] = mapped_column(String(30))
    idade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escolaridade: Mapped[str] = mapped_column(String(60), default="")
    contexto: Mapped[str] = mapped_column(String(200), default="")
    demanda: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="em_andamento")
    data_inicio: Mapped[date] = mapped_column(Date)
    data_conclusao: Mapped[date | None] = mapped_column(Date, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    finalidade: Mapped[Finalidade] = relationship()
    registros: Mapped[list[RegistroAvaliacao]] = relationship(
        back_populates="avaliacao", order_by="RegistroAvaliacao.data, RegistroAvaliacao.id"
    )
    aplicacoes: Mapped[list[AplicacaoInstrumento]] = relationship(
        back_populates="avaliacao", order_by="AplicacaoInstrumento.data_aplicacao, AplicacaoInstrumento.id"
    )


class RegistroAvaliacao(Base):
    """Entrevista, anamnese, observação, devolutiva etc."""

    __tablename__ = "registros_avaliacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id"))
    data: Mapped[date] = mapped_column(Date)
    tipo: Mapped[str] = mapped_column(String(40))
    conteudo: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    editado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    avaliacao: Mapped[Avaliacao] = relationship(back_populates="registros")


class AplicacaoInstrumento(Base):
    """Uso profissional de uma versão de teste numa avaliação. Só é criada se a versão estiver elegível."""

    __tablename__ = "aplicacoes_instrumento"

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id"))
    versao_id: Mapped[int] = mapped_column(ForeignKey("versoes_instrumento.id"))
    data_aplicacao: Mapped[date] = mapped_column(Date)
    modalidade: Mapped[str] = mapped_column(String(40), default="")
    observacoes: Mapped[str] = mapped_column(Text, default="")
    # Fotografia da conformidade no momento do registro (para rastreabilidade).
    satepsi_status_no_registro: Mapped[str] = mapped_column(String(20))
    satepsi_motivo_no_registro: Mapped[str] = mapped_column(Text)
    verificacao_id_no_registro: Mapped[int | None] = mapped_column(
        ForeignKey("verificacoes_satepsi.id"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    avaliacao: Mapped[Avaliacao] = relationship(back_populates="aplicacoes")
    versao: Mapped[VersaoInstrumento] = relationship()
    resultados: Mapped[list[ResultadoRegistrado]] = relationship(
        back_populates="aplicacao", order_by="ResultadoRegistrado.id"
    )


class ResultadoRegistrado(Base):
    """Resultado transcrito do manual/plataforma oficial. O sistema NÃO calcula normas protegidas."""

    __tablename__ = "resultados_registrados"

    id: Mapped[int] = mapped_column(primary_key=True)
    aplicacao_id: Mapped[int] = mapped_column(ForeignKey("aplicacoes_instrumento.id"))
    medida: Mapped[str] = mapped_column(String(200))
    escore_bruto: Mapped[str] = mapped_column(String(40), default="")
    escore_padrao: Mapped[str] = mapped_column(String(40), default="")
    percentil: Mapped[str] = mapped_column(String(40), default="")
    classificacao: Mapped[str] = mapped_column(String(120), default="")
    referencia: Mapped[str] = mapped_column(String(300), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    editado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    aplicacao: Mapped[AplicacaoInstrumento] = relationship(back_populates="resultados")


class PerfilProfissional(Base):
    """Dados da(o) psicóloga(o) autora(or) dos documentos (registro único, id=1)."""

    __tablename__ = "perfil_profissional"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), default="")
    crp: Mapped[str] = mapped_column(String(30), default="")
    titulacao: Mapped[str] = mapped_column(String(200), default="")
    cidade_uf: Mapped[str] = mapped_column(String(120), default="")
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    # Consultor IA: desligado até consentimento explícito do usuário.
    ia_habilitada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    ia_consentimento_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentoPsicologico(Base):
    """Documento psicológico (Res. CFP 06/2019). Rascunho → revisado → aprovado → emitido.

    O nome da pessoa avaliada NUNCA é gravado: é informado só ao gerar o arquivo .docx.
    """

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes.id"))
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))
    titulo: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="rascunho")
    substitui_id: Mapped[int | None] = mapped_column(ForeignKey("documentos.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    emitido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_emissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Fotografia imutável do conteúdo emitido (JSON) e seu SHA-256.
    conteudo_emitido: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash_conteudo: Mapped[str | None] = mapped_column(String(64), nullable=True)

    avaliacao: Mapped[Avaliacao] = relationship()
    secoes: Mapped[list[SecaoDocumento]] = relationship(
        back_populates="documento", order_by="SecaoDocumento.ordem"
    )


class SecaoDocumento(Base):
    __tablename__ = "secoes_documento"
    __table_args__ = (UniqueConstraint("documento_id", "chave"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id"))
    chave: Mapped[str] = mapped_column(String(40))
    titulo: Mapped[str] = mapped_column(String(120))
    ordem: Mapped[int] = mapped_column(Integer)
    obrigatoria: Mapped[bool] = mapped_column(Boolean, default=True)
    conteudo: Mapped[str] = mapped_column(Text, default="")
    editado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documento: Mapped[DocumentoPsicologico] = relationship(back_populates="secoes")


class CodigoQualitativo(Base):
    """Código/categoria do livro de códigos da análise qualitativa (global, reutilizável)."""

    __tablename__ = "codigos_qualitativos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class Codificacao(Base):
    """Trecho literal de um registro (entrevista/observação) associado a um código."""

    __tablename__ = "codificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    registro_id: Mapped[int] = mapped_column(ForeignKey("registros_avaliacao.id"))
    codigo_id: Mapped[int] = mapped_column(ForeignKey("codigos_qualitativos.id"))
    trecho: Mapped[str] = mapped_column(Text)
    comentario: Mapped[str] = mapped_column(Text, default="")
    origem: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ia_aceita
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)

    registro: Mapped[RegistroAvaliacao] = relationship()
    codigo: Mapped[CodigoQualitativo] = relationship()


class SegredoCifrado(Base):
    """Segredos digitados no próprio app (ex.: chave da API do Claude), cifrados com chave derivada de
    APP_PASSWORD. Nunca entram no backup, na auditoria nem na tela (só a forma mascarada)."""

    __tablename__ = "segredos_cifrados"

    nome: Mapped[str] = mapped_column(String(60), primary_key=True)
    cifrado: Mapped[str] = mapped_column(Text)
    sal: Mapped[str] = mapped_column(String(64))
    final: Mapped[str] = mapped_column(String(8), default="")  # últimos caracteres, para exibir mascarado
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class ConjuntoDados(Base):
    """Base de dados de pesquisa ANONIMIZADA importada (CSV/XLSX), guardada como CSV normalizado."""

    __tablename__ = "conjuntos_dados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    arquivo_original: Mapped[str] = mapped_column(String(200), default="")
    conteudo_csv: Mapped[str] = mapped_column(Text, deferred=True)
    n_linhas: Mapped[int] = mapped_column(Integer)
    n_colunas: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)


class TrechoModelo(Base):
    """Biblioteca de modelos e frases reutilizáveis para os documentos (textos da própria profissional)."""

    __tablename__ = "trechos_modelo"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120), unique=True)
    categoria: Mapped[str] = mapped_column(String(60))
    secao: Mapped[str] = mapped_column(String(40), default="qualquer")
    texto: Mapped[str] = mapped_column(Text)
    exemplo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    usos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
