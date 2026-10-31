"""Modelo de dados do SIAP-IA (Etapas 1 e 2: catálogo, SATEPSI e auditoria)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


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

    versao: Mapped[VersaoInstrumento] = relationship(back_populates="verificacoes")


class RegistroAuditoria(Base):
    """Trilha de auditoria (somente inclusão)."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    acao: Mapped[str] = mapped_column(String(60))
    entidade: Mapped[str] = mapped_column(String(60))
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[str] = mapped_column(Text, default="{}")
