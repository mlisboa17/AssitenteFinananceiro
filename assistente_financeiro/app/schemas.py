"""
Schemas Pydantic para validação e serialização de dados da API.
Define os formatos de entrada e saída para cada endpoint REST.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# ================================================
# Schemas de Categoria
# ================================================

class CategoriaBase(BaseModel):
    nome:      str        = Field(..., max_length=100, description="Nome da categoria")
    cor:       str        = Field("#3498db", description="Cor hexadecimal (#RRGGBB)")
    icone:     str        = Field("💰",      description="Emoji de ícone")
    descricao: Optional[str] = None

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaUpdate(BaseModel):
    nome:      Optional[str] = None
    cor:       Optional[str] = None
    icone:     Optional[str] = None
    descricao: Optional[str] = None
    ativa:     Optional[bool] = None

class CategoriaRead(CategoriaBase):
    id:        int
    ativa:     bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ================================================
# Schemas de Conta Bancária
# ================================================

class ContaBancariaBase(BaseModel):
    nome:    str = Field(..., max_length=100)
    banco:   str = Field(..., max_length=100)
    agencia: Optional[str] = None
    conta:   Optional[str] = None
    saldo:   float = 0.0

class ContaBancariaCreate(ContaBancariaBase):
    pass

class ContaBancariaUpdate(BaseModel):
    nome:    Optional[str]   = None
    banco:   Optional[str]   = None
    agencia: Optional[str]   = None
    conta:   Optional[str]   = None
    saldo:   Optional[float] = None
    ativa:   Optional[bool]  = None

class ContaBancariaRead(ContaBancariaBase):
    id:        int
    ativa:     bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ================================================
# Schemas de Cartão de Crédito
# ================================================

class CartaoCreditoBase(BaseModel):
    nome:              str   = Field(..., max_length=100)
    bandeira:          str   = Field(..., max_length=50)
    limite:            float = 0.0
    limite_disponivel: float = 0.0
    dia_fechamento:    int   = Field(1,  ge=1, le=31)
    dia_vencimento:    int   = Field(10, ge=1, le=31)

class CartaoCreditoCreate(CartaoCreditoBase):
    pass

class CartaoCreditoUpdate(BaseModel):
    nome:              Optional[str]   = None
    bandeira:          Optional[str]   = None
    limite:            Optional[float] = None
    limite_disponivel: Optional[float] = None
    dia_fechamento:    Optional[int]   = None
    dia_vencimento:    Optional[int]   = None
    ativo:             Optional[bool]  = None

class CartaoCreditoRead(CartaoCreditoBase):
    id:        int
    ativo:     bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ================================================
# Schemas de Transação
# ================================================

class TransacaoBase(BaseModel):
    data:           date
    descricao:      str   = Field(..., max_length=255)
    valor:          float = Field(..., description="Valor absoluto (sempre positivo)")
    tipo:           str   = Field(..., pattern="^(debito|credito)$")
    observacao:     Optional[str]  = None
    forma_pagamento: Optional[str] = Field(
        None,
        pattern="^(dinheiro|cartao_credito|pix_transferencia|boleto_conta)$",
    )
    parcela_atual:  Optional[int]  = None
    parcelas_total: Optional[int]  = None
    fonte:          Optional[str]  = None
    categoria_id:   Optional[int]  = None
    conta_id:       Optional[int]  = None
    cartao_id:      Optional[int]  = None

class TransacaoCreate(TransacaoBase):
    pass

class TransacaoUpdate(BaseModel):
    data:           Optional[date]  = None
    descricao:      Optional[str]   = None
    valor:          Optional[float] = None
    tipo:           Optional[str]   = None
    observacao:     Optional[str]   = None
    forma_pagamento: Optional[str]  = Field(
        None,
        pattern="^(dinheiro|cartao_credito|pix_transferencia|boleto_conta)$",
    )
    parcela_atual:  Optional[int]   = None
    parcelas_total: Optional[int]   = None
    categoria_id:   Optional[int]   = None
    conta_id:       Optional[int]   = None
    cartao_id:      Optional[int]   = None

class TransacaoRead(TransacaoBase):
    id:            int
    arquivo_origem: Optional[str]  = None
    extrato_id:    Optional[int]   = None
    categoria:     Optional[CategoriaRead] = None
    criado_em:     datetime

    model_config = {"from_attributes": True}


class EventoFinanceiroBase(BaseModel):
    titulo: str = Field(..., max_length=150)
    descricao: Optional[str] = None
    valor: float = Field(..., ge=0)
    data_vencimento: date
    tipo: str = Field(..., pattern="^(conta|receita|reserva|parcela|fatura_cartao|outro)$")
    status: str = Field("pendente", pattern="^(pendente|pago|recebido|atrasado|cancelado)$")
    recorrente: bool = False
    dia_recorrencia: Optional[int] = Field(None, ge=1, le=31)
    codigo_barras: Optional[str] = None
    categoria_id: Optional[int] = None
    conta_id: Optional[int] = None
    cartao_id: Optional[int] = None


class EventoFinanceiroCreate(EventoFinanceiroBase):
    pass


class EventoFinanceiroUpdate(BaseModel):
    titulo: Optional[str] = Field(None, max_length=150)
    descricao: Optional[str] = None
    valor: Optional[float] = Field(None, ge=0)
    data_vencimento: Optional[date] = None
    tipo: Optional[str] = Field(None, pattern="^(conta|receita|reserva|parcela|fatura_cartao|outro)$")
    status: Optional[str] = Field(None, pattern="^(pendente|pago|recebido|atrasado|cancelado)$")
    recorrente: Optional[bool] = None
    dia_recorrencia: Optional[int] = Field(None, ge=1, le=31)
    codigo_barras: Optional[str] = None
    categoria_id: Optional[int] = None
    conta_id: Optional[int] = None
    cartao_id: Optional[int] = None


class EventoFinanceiroRead(EventoFinanceiroBase):
    id: int
    pago_em: Optional[datetime] = None
    transacao_id: Optional[int] = None
    criado_em: datetime

    model_config = {"from_attributes": True}


class EventoFinanceiroPagamento(BaseModel):
    data_pagamento: Optional[date] = None
    conta_id: Optional[int] = None
    cartao_id: Optional[int] = None
    forma_pagamento: Optional[str] = Field(
        None,
        pattern="^(dinheiro|cartao_credito|pix_transferencia|boleto_conta)$",
    )
    descricao_transacao: Optional[str] = Field(None, max_length=255)


# ================================================
# Schemas de Extrato
# ================================================

class ExtratoRead(BaseModel):
    id:               int
    arquivo_nome:     str
    tipo:             str
    banco:            Optional[str]  = None
    periodo_inicio:   Optional[date] = None
    periodo_fim:      Optional[date] = None
    total_transacoes: int
    importado_em:     datetime

    model_config = {"from_attributes": True}


# ================================================
# Schemas de Meta
# ================================================

class MetaBase(BaseModel):
    nome:        str   = Field(..., max_length=100)
    descricao:   Optional[str]  = None
    valor_alvo:  float = Field(..., gt=0)
    valor_atual: float = 0.0
    data_inicio: Optional[date] = None
    data_fim:    Optional[date] = None
    categoria_id: Optional[int] = None

class MetaCreate(MetaBase):
    pass

class MetaUpdate(BaseModel):
    nome:        Optional[str]   = None
    descricao:   Optional[str]   = None
    valor_alvo:  Optional[float] = None
    valor_atual: Optional[float] = None
    data_fim:    Optional[date]  = None
    ativa:       Optional[bool]  = None
    concluida:   Optional[bool]  = None

class MetaRead(MetaBase):
    id:                  int
    ativa:               bool
    concluida:           bool
    percentual_concluido: float
    criado_em:           datetime

    model_config = {"from_attributes": True}


# ================================================
# Schemas de Orçamento
# ================================================

class OrcamentoBase(BaseModel):
    categoria_id:      int
    valor_limite:      float = Field(..., gt=0)
    mes:               int   = Field(..., ge=1, le=12)
    ano:               int   = Field(..., ge=2000)
    alerta_percentual: float = Field(80.0, ge=0, le=100)

class OrcamentoCreate(OrcamentoBase):
    pass

class OrcamentoUpdate(BaseModel):
    valor_limite:      Optional[float] = None
    alerta_percentual: Optional[float] = None

class OrcamentoRead(OrcamentoBase):
    id:       int
    categoria: Optional[CategoriaRead] = None

    model_config = {"from_attributes": True}


# ================================================
# Schemas auxiliares (respostas de endpoints específicos)
# ================================================

class ResumoDashboard(BaseModel):
    """Dados consolidados para o painel principal."""
    total_receitas:    float
    total_despesas:    float
    saldo_mensal:      float
    total_transacoes:  int
    mes_referencia:    str
    categorias_gastos: List[dict]   # [{"categoria": str, "valor": float, "percentual": float}]
    evolucao_mensal:   List[dict]   # [{"mes": str, "receitas": float, "despesas": float}]

class InsightFinanceiro(BaseModel):
    """Insight gerado pelo sistema."""
    tipo:      str      # "alerta", "oportunidade", "info"
    titulo:    str
    descricao: str
    valor:     Optional[float] = None
    categoria: Optional[str]  = None

class PerguntaAssistente(BaseModel):
    """Input do assistente conversacional."""
    pergunta:    str

class RespostaAssistente(BaseModel):
    """Resposta do assistente conversacional."""
    pergunta:    str
    resposta:    str
    dados:       Optional[dict] = None

class DespesaManual(BaseModel):
    """Schema para registro rápido de despesa (Telegram/Voz)."""
    valor:       float  = Field(..., gt=0)
    descricao:   str    = Field(..., max_length=255)
    categoria:   Optional[str] = None
    data:        Optional[date] = None
    fonte:       Optional[str] = Field(default="manual", max_length=30)

    @field_validator("data", mode="before")
    @classmethod
    def default_data_hoje(cls, v):
        return v or date.today()


class TelegramTeste(BaseModel):
    """Payload para envio de mensagem de teste no Telegram."""
    mensagem: Optional[str] = Field(
        default="✅ Teste do Vorcaro: integração com Telegram ativa.",
        max_length=2000,
    )
    chat_id: Optional[str] = Field(default=None, max_length=64)


# ================================================
# Schemas de Importação de Documentos
# ================================================

class DocumentoDetectado(BaseModel):
    """Resultado da análise automática de um documento importado."""
    arquivo_nome:    str
    extensao:        str
    tipo_detectado:  str   # chave interna: nota_fiscal, boleto, extrato_bancario, etc.
    nome_tipo:       str   # nome legível
    emoji_tipo:      str
    confianca:       str   # "alta" | "media" | "baixa"
    texto_preview:   str   # primeiros 600 caracteres do texto extraído


class DocumentoConfirmar(BaseModel):
    """Payload enviado após o usuário confirmar o tipo do documento."""
    arquivo_path:     str   = Field(..., description="Caminho do arquivo já salvo no servidor")
    tipo_documento:   str   = Field(
        ...,
        pattern="^(nota_fiscal|comprovante_compra|boleto|extrato_bancario|extrato_cartao)$"
    )
    conta_id:         Optional[int] = None
    cartao_id:        Optional[int] = None
    descricao_manual: Optional[str] = Field(None, max_length=255)

