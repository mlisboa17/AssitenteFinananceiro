"""
Modelos do banco de dados do Assistente Financeiro Pessoal.
Define a estrutura de todas as tabelas usando SQLAlchemy ORM.

Tabelas:
  - Categoria       : Categorias de gastos (Alimentação, Transporte, etc.)
  - ContaBancaria   : Contas bancárias do usuário
  - CartaoCredito   : Cartões de crédito (Visa, Mastercard, Elo, Amex...)
  - Transacao       : Cada transação financeira registrada
  - Extrato         : Metadados dos arquivos importados
  - Meta            : Metas financeiras do usuário
  - Orcamento       : Limites de gasto mensal por categoria
"""

import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Date, ForeignKey, Text, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


# ================================================
# Enumerações (valores controlados)
# ================================================

class TipoTransacao(str, enum.Enum):
    """Define se a transação é saída (débito) ou entrada (crédito)."""
    DEBITO  = "debito"
    CREDITO = "credito"


class TipoExtrato(str, enum.Enum):
    """Tipo/formato do extrato importado."""
    BANCARIO = "bancario"
    CARTAO   = "cartao"
    CSV      = "csv"
    EXCEL    = "excel"
    OFX      = "ofx"
    MANUAL   = "manual"


# ================================================
# Modelos
# ================================================

class Categoria(Base):
    """
    Categoria de transação financeira.
    Exemplos: Alimentação, Transporte, Saúde, Lazer, etc.
    """
    __tablename__ = "categorias"

    id        = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome      = Column(String(100), unique=True, nullable=False, index=True)
    cor       = Column(String(7),  default="#3498db")   # Cor hexadecimal para gráficos
    icone     = Column(String(10), default="💰")         # Emoji de ícone
    descricao = Column(String(255), nullable=True)
    ativa     = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos reversos
    transacoes = relationship("Transacao", back_populates="categoria")
    orcamentos = relationship("Orcamento", back_populates="categoria")
    metas      = relationship("Meta",      back_populates="categoria")

    def __repr__(self):
        return f"<Categoria(id={self.id}, nome='{self.nome}')>"


class ContaBancaria(Base):
    """
    Conta bancária do usuário.
    Suporta todos os bancos brasileiros.
    """
    __tablename__ = "contas_bancarias"

    id        = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome      = Column(String(100), nullable=False)         # Ex: "Conta Corrente Itaú"
    banco     = Column(String(100), nullable=False)         # Ex: "Itaú"
    agencia   = Column(String(20),  nullable=True)
    conta     = Column(String(20),  nullable=True)
    saldo     = Column(Float,       default=0.0)
    ativa     = Column(Boolean,     default=True)
    criado_em = Column(DateTime,    default=datetime.utcnow)

    transacoes = relationship("Transacao", back_populates="conta")
    extratos   = relationship("Extrato",   back_populates="conta")

    def __repr__(self):
        return f"<ContaBancaria(id={self.id}, banco='{self.banco}', conta='{self.conta}')>"


class CartaoCredito(Base):
    """
    Cartão de crédito do usuário.
    Suporta Visa, Mastercard, Elo, American Express, Hipercard.
    """
    __tablename__ = "cartoes_credito"

    id                = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome              = Column(String(100), nullable=False)     # Ex: "Nubank Mastercard"
    bandeira          = Column(String(50),  nullable=False)     # Ex: "Mastercard"
    limite            = Column(Float,       default=0.0)
    limite_disponivel = Column(Float,       default=0.0)
    dia_fechamento    = Column(Integer,     default=1)          # Dia de fechamento
    dia_vencimento    = Column(Integer,     default=10)         # Dia de vencimento
    ativo             = Column(Boolean,     default=True)
    criado_em         = Column(DateTime,    default=datetime.utcnow)

    transacoes = relationship("Transacao",   back_populates="cartao")
    extratos   = relationship("Extrato",     back_populates="cartao")

    def __repr__(self):
        return f"<CartaoCredito(id={self.id}, nome='{self.nome}', bandeira='{self.bandeira}')>"


class Transacao(Base):
    """
    Transação financeira individual.
    Pode ser de débito (gasto) ou crédito (receita/entrada).
    Suporta detecção de parcelas (ex: 3/10).
    """
    __tablename__ = "transacoes"

    id             = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data           = Column(Date,    nullable=False, index=True)
    descricao      = Column(String(255), nullable=False)
    valor          = Column(Float,       nullable=False)
    tipo           = Column(SAEnum(TipoTransacao), nullable=False)
    observacao     = Column(Text,    nullable=True)

    # Suporte a compras parceladas (ex: "3/10" = parcela 3 de 10)
    parcela_atual  = Column(Integer, nullable=True)
    parcelas_total = Column(Integer, nullable=True)

    # Metadados de origem
    fonte          = Column(String(100), nullable=True)   # Ex: "Itaú", "Nubank"
    arquivo_origem = Column(String(255), nullable=True)   # Nome do arquivo importado

    # Chaves estrangeiras
    categoria_id   = Column(Integer, ForeignKey("categorias.id"),       nullable=True)
    conta_id       = Column(Integer, ForeignKey("contas_bancarias.id"), nullable=True)
    cartao_id      = Column(Integer, ForeignKey("cartoes_credito.id"),  nullable=True)
    extrato_id     = Column(Integer, ForeignKey("extratos.id"),         nullable=True)

    # Timestamps automáticos
    criado_em      = Column(DateTime, default=datetime.utcnow)
    atualizado_em  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos ORM
    categoria = relationship("Categoria",     back_populates="transacoes")
    conta     = relationship("ContaBancaria", back_populates="transacoes")
    cartao    = relationship("CartaoCredito", back_populates="transacoes")
    extrato   = relationship("Extrato",       back_populates="transacoes")

    def __repr__(self):
        return f"<Transacao(id={self.id}, data='{self.data}', descricao='{self.descricao}', valor={self.valor})>"


class Extrato(Base):
    """
    Registro de extrato importado (PDF, CSV, Excel, OFX).
    Armazena metadados sobre cada importação realizada.
    """
    __tablename__ = "extratos"

    id                = Column(Integer, primary_key=True, index=True, autoincrement=True)
    arquivo_nome      = Column(String(255), nullable=False)
    arquivo_path      = Column(String(512), nullable=True)
    tipo              = Column(SAEnum(TipoExtrato), nullable=False)
    banco             = Column(String(100), nullable=True)
    periodo_inicio    = Column(Date,    nullable=True)
    periodo_fim       = Column(Date,    nullable=True)
    total_transacoes  = Column(Integer, default=0)
    importado_em      = Column(DateTime, default=datetime.utcnow)

    # Chaves estrangeiras (opcionais)
    conta_id          = Column(Integer, ForeignKey("contas_bancarias.id"), nullable=True)
    cartao_id         = Column(Integer, ForeignKey("cartoes_credito.id"),  nullable=True)

    conta      = relationship("ContaBancaria", back_populates="extratos")
    cartao     = relationship("CartaoCredito", back_populates="extratos")
    transacoes = relationship("Transacao",     back_populates="extrato")

    def __repr__(self):
        return f"<Extrato(id={self.id}, arquivo='{self.arquivo_nome}', tipo='{self.tipo}')>"


class AprendizadoTipoDocumento(Base):
    """
    Guarda feedback de tipo de documento confirmado pelo usuário.
    A assinatura textual permite reutilizar a correção em documentos parecidos.
    """
    __tablename__ = "aprendizado_tipos_documento"
    __table_args__ = (
        UniqueConstraint("assinatura", "tipo_documento", name="uq_aprendizado_assinatura_tipo"),
    )

    id            = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assinatura    = Column(String(64), nullable=False, index=True)
    tipo_documento = Column(String(64), nullable=False, index=True)
    ocorrencias   = Column(Integer, nullable=False, default=1)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            "<AprendizadoTipoDocumento(assinatura='"
            f"{self.assinatura}', tipo='{self.tipo_documento}', ocorrencias={self.ocorrencias})>"
        )


class Meta(Base):
    """
    Meta financeira do usuário.
    Permite acompanhar o progresso em direção a um objetivo.
    Ex: Poupar R$ 5.000 para viagem, quitar dívida, etc.
    """
    __tablename__ = "metas"

    id           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome         = Column(String(100), nullable=False)
    descricao    = Column(Text,    nullable=True)
    valor_alvo   = Column(Float,   nullable=False)
    valor_atual  = Column(Float,   default=0.0)
    data_inicio  = Column(Date,    default=date.today)
    data_fim     = Column(Date,    nullable=True)
    ativa        = Column(Boolean, default=True)
    concluida    = Column(Boolean, default=False)
    criado_em    = Column(DateTime, default=datetime.utcnow)

    # Categoria associada (opcional)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria    = relationship("Categoria", back_populates="metas")

    @property
    def percentual_concluido(self) -> float:
        """Calcula e retorna o percentual de conclusão da meta."""
        if self.valor_alvo > 0:
            return min((self.valor_atual / self.valor_alvo) * 100, 100.0)
        return 0.0

    def __repr__(self):
        return f"<Meta(id={self.id}, nome='{self.nome}', progresso={self.percentual_concluido:.1f}%)>"


class Orcamento(Base):
    """
    Orçamento mensal por categoria.
    Define limite de gastos e dispara alerta ao aproximar do limite.
    """
    __tablename__ = "orcamentos"

    id                = Column(Integer, primary_key=True, index=True, autoincrement=True)
    valor_limite      = Column(Float,   nullable=False)
    mes               = Column(Integer, nullable=False)         # 1 = Janeiro, 12 = Dezembro
    ano               = Column(Integer, nullable=False)
    alerta_percentual = Column(Float,   default=80.0)           # Alerta ao atingir X%

    # Chave estrangeira obrigatória
    categoria_id      = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    categoria         = relationship("Categoria", back_populates="orcamentos")

    def __repr__(self):
        return f"<Orcamento(categoria={self.categoria_id}, {self.mes}/{self.ano}, limite=R${self.valor_limite})>"


# ================================================
# Agenda Financeira
# ================================================

class StatusEvento(str, enum.Enum):
    PENDENTE  = "pendente"
    PAGO      = "pago"
    RECEBIDO  = "recebido"
    ATRASADO  = "atrasado"
    CANCELADO = "cancelado"


class TipoEvento(str, enum.Enum):
    CONTA      = "conta"       # Conta a pagar (luz, aluguel…)
    RECEITA    = "receita"     # Receita esperada (salário, freelance…)
    RESERVA    = "reserva"     # Transferência / reserva
    PARCELA    = "parcela"     # Parcela de cartão/empréstimo
    OUTRO      = "outro"


class EventoFinanceiro(Base):
    """
    Evento financeiro agendado: conta a pagar, receita esperada, parcela, etc.
    Suporta recorrência mensal automática.
    """
    __tablename__ = "eventos_financeiros"

    id               = Column(Integer,  primary_key=True, index=True, autoincrement=True)
    titulo           = Column(String(150), nullable=False)
    descricao        = Column(Text,     nullable=True)
    valor            = Column(Float,    nullable=False, default=0.0)
    data_vencimento  = Column(Date,     nullable=False, index=True)
    tipo             = Column(SAEnum(TipoEvento),   nullable=False, default=TipoEvento.CONTA)
    status           = Column(SAEnum(StatusEvento), nullable=False, default=StatusEvento.PENDENTE)
    recorrente       = Column(Boolean,  default=False)   # Repetir todo mês
    dia_recorrencia  = Column(Integer,  nullable=True)   # Dia do mês para recorrência
    codigo_barras    = Column(String(100), nullable=True) # Linha digitável / código de barras
    pago_em          = Column(DateTime, nullable=True)
    criado_em        = Column(DateTime, default=datetime.utcnow)

    categoria_id     = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria        = relationship("Categoria")

    def __repr__(self):
        return f"<EventoFinanceiro(id={self.id}, titulo='{self.titulo}', venc='{self.data_vencimento}', status='{self.status}')>"


# ================================================
# Agenda de Compromissos
# ================================================

class Compromisso(Base):
    """
    Compromisso pessoal ou profissional do usuário.
    """
    __tablename__ = "compromissos"

    id               = Column(Integer,  primary_key=True, index=True, autoincrement=True)
    titulo           = Column(String(150), nullable=False)
    descricao        = Column(Text,     nullable=True)
    local            = Column(String(200), nullable=True)
    data             = Column(Date,     nullable=False, index=True)
    hora_inicio      = Column(String(5), nullable=True)   # "HH:MM"
    hora_fim         = Column(String(5), nullable=True)
    cor              = Column(String(7), default="#3498db")
    lembrete_min     = Column(Integer,  nullable=True)    # Lembrete X min antes
    concluido        = Column(Boolean,  default=False)
    criado_em        = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Compromisso(id={self.id}, titulo='{self.titulo}', data='{self.data}')>"


# ================================================
# Planner de Tarefas
# ================================================

class PrioridadeTarefa(str, enum.Enum):
    ALTA   = "alta"
    MEDIA  = "media"
    BAIXA  = "baixa"


class StatusTarefa(str, enum.Enum):
    A_FAZER     = "a_fazer"
    EM_PROGRESSO = "em_progresso"
    CONCLUIDO   = "concluido"


class AreaTarefa(str, enum.Enum):
    FINANCEIRO = "financeiro"
    PESSOAL    = "pessoal"
    TRABALHO   = "trabalho"
    SAUDE      = "saude"
    OUTRO      = "outro"


class TarefaPlanner(Base):
    """
    Tarefa do Planner: pode estar vinculada a um dia da semana/mês.
    """
    __tablename__ = "tarefas_planner"

    id           = Column(Integer,  primary_key=True, index=True, autoincrement=True)
    titulo       = Column(String(150), nullable=False)
    descricao    = Column(Text,     nullable=True)
    data         = Column(Date,     nullable=True, index=True)
    prioridade   = Column(SAEnum(PrioridadeTarefa), nullable=False, default=PrioridadeTarefa.MEDIA)
    status       = Column(SAEnum(StatusTarefa),     nullable=False, default=StatusTarefa.A_FAZER)
    area         = Column(SAEnum(AreaTarefa),        nullable=False, default=AreaTarefa.PESSOAL)
    concluido_em = Column(DateTime, nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TarefaPlanner(id={self.id}, titulo='{self.titulo}', status='{self.status}')>"
