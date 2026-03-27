"""
Padrões de expressões regulares para extratos bancários brasileiros.

Inclui padrões para:
  - Datas em formatos brasileiros
  - Valores monetários em formato BR
  - Identificação de parcelas
  - Padrões específicos de bancos brasileiros
  - Padrões de cartões de crédito
"""

import re

# ================================================
# Padrões de DATA
# ================================================

# Data completa: dd/mm/yyyy ou dd-mm-yyyy
DATA_BR_COMPLETA = re.compile(
    r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b'
)

# Data curta: dd/mm (sem ano)
DATA_BR_CURTA = re.compile(
    r'\b(\d{1,2})[/\-](\d{1,2})\b'
)

# Data por extenso: "15 de janeiro de 2024"
DATA_POR_EXTENSO = re.compile(
    r'\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|'
    r'julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b',
    re.IGNORECASE
)

# ================================================
# Padrões de VALOR MONETÁRIO
# ================================================

# Valor com símbolo R$: "R$ 1.234,56" ou "R$1234,56"
VALOR_COM_RS = re.compile(
    r'R\$\s*([+-]?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)'
)

# Valor numérico brasileiro: "1.234,56" ou "-1.234,56"
VALOR_NUMERICO_BR = re.compile(
    r'([+-]?\d{1,3}(?:\.\d{3})*,\d{2})'
)

# Valor simples (inteiro ou decimal): "1234" ou "1234.56"
VALOR_SIMPLES = re.compile(
    r'\b(\d+(?:[.,]\d{1,2})?)\b'
)

# ================================================
# Padrões de PARCELAS
# ================================================

# Parcela numérica: "3/10" ou "03/10"
PARCELA_NUMERICA = re.compile(
    r'(?<!\d)0?(\d{1,2})[/](\d{1,2})(?!\d)'
)

# Parcela por extenso: "Parcela 3 de 10"
PARCELA_POR_EXTENSO = re.compile(
    r'parcela\s+(\d{1,2})\s+de\s+(\d{1,2})',
    re.IGNORECASE
)

# Parcela abreviada: "Parc 3/10", "Pcl 03/10"
PARCELA_ABREVIADA = re.compile(
    r'(?:parc|par|pcel|pcl)\.?\s*(\d{1,2})[/](\d{1,2})',
    re.IGNORECASE
)

# ================================================
# Padrões de EXTRATOS BANCÁRIOS BRASILEIROS
# ================================================

# Itaú - formato: "15/01  Compra Supermercado  -150,00"
ITAU_TRANSACAO = re.compile(
    r'(\d{2}/\d{2})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Bradesco - formato extrato: "15/01/2024  12345  Pagamento  -150,00"
BRADESCO_TRANSACAO = re.compile(
    r'(\d{2}/\d{2}/\d{4})\s+(\d+)?\s*(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Bradesco Fatura de Cartão - formato: "DD/MM HISTÓRICO VALOR[-]"
# O '-' ao final indica crédito (pagamento). Usa match não-guloso para capturar
# o PRIMEIRO valor na linha, evitando colunas da tabela de limites/taxas.
# O lookahead negativo (?!\s*%) exclui linhas de tabelas de taxas (ex: "4,99%").
BRADESCO_FATURA_TRANSACAO = re.compile(
    r'^\s*(\d{2}/\d{2})\s+(.*?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(-?)(?!\s*%)',
    re.MULTILINE
)

# Santander - formato: "15/01  Compra  -150,00  1.234,56"
SANTANDER_TRANSACAO = re.compile(
    r'(\d{2}/\d{2})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})',
    re.MULTILINE
)

# Banco do Brasil - formato: "15/01/2024  Compra  -150,00"
BB_TRANSACAO = re.compile(
    r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Caixa Econômica Federal
CAIXA_TRANSACAO = re.compile(
    r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Nubank - formato de fatura (ex: "18 FEV •••• 7596 iFood R$ 1.234,56")
# Também cobre linhas sem mascara de cartão: "18 FEV Descricao R$ 50,00"
NUBANK_TRANSACAO = re.compile(
    r'^(\d{2}\s+\w{3})\s+(?:[^\w\s]+\s+\d{3,4}\s+)?(.+?)\s+R\$\s*([\d\.]+,\d{2})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Inter - extrato digital
INTER_TRANSACAO = re.compile(
    r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# C6 Bank Fatura de Cartão - formato: "DD mmm DESCRIÇÃO VALOR"
# Ex: "30 jan UBER UBER *TRIP HELP.U 13,99"
#     "04 nov OTORRINOFACE - Parcela 4/5 3.200,00"
# Usa match não-guloso da descrição para pegar o ÚLTIMO valor da linha.
C6_FATURA_TRANSACAO = re.compile(
    r'^\s*(\d{1,2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s+'
    r'(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# ================================================
# Padrões de CARTÃO DE CRÉDITO
# ================================================

# Padrão genérico de fatura de cartão
CARTAO_LINHA = re.compile(
    r'(\d{2}/\d{2})\s+(.+?)\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Fatura com data completa: "DD/MM/AAAA DESCRIÇÃO VALOR"
CARTAO_LINHA_DATA_COMPLETA = re.compile(
    r'^\s*(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(?:R\$\s*)?([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Fatura com mês abreviado: "DD MMM DESCRIÇÃO VALOR" ou "DD MMM DESCRIÇÃO R$ VALOR"
CARTAO_LINHA_MES_TEXTO = re.compile(
    r'^\s*(\d{1,2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s+'
    r'(?:[^\w\n]+\s+\d{3,4}\s+)?(.+?)\s+(?:R\$\s*)?([+-]?\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Mercado Pago - fatura de cartão de crédito
# Linha de transação: "DD/MM DESCRIÇÃO R$ VALOR"
# Ex: "11/11 ENGEFRIO INDUSTRIAL LT Parcela 4 de 4 R$ 2.591,25"
#     "06/03 Compra internacional em GITHUB, INC. R$ 213,54"
MP_FATURA_TRANSACAO = re.compile(
    r'^\s*(\d{2}/\d{2})\s+(.+?)\s+R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
    re.MULTILINE
)

# Data de vencimento na fatura do Mercado Pago
# Formatos: "Vence em 16/03/2026" ou "Vencimento: 16/03/2026"
MP_FATURA_VENCIMENTO = re.compile(
    r'(?:Vence em|Vencimento\s*:)\s*(\d{2}/\d{2}/\d{4})',
    re.IGNORECASE
)

# Compra parcelada no cartão: "Nome Loja 03/12  R$150,00"
CARTAO_PARCELADO = re.compile(
    r'(.+?)\s+(\d{2})/(\d{2})\s+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})',
    re.IGNORECASE
)

# ================================================
# Padrões de IDENTIFICAÇÃO DE DADOS SENSÍVEIS
# ================================================

# CPF: "123.456.789-00" ou "12345678900"
CPF = re.compile(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}')

# CNPJ: "12.345.678/0001-00"
CNPJ = re.compile(r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}')

# Número de conta/agência
AGENCIA_CONTA = re.compile(
    r'ag[eê]ncia\s*[:.]?\s*(\d+)[-/]?\s*conta\s*[:.]?\s*(\d+[-x\d]*)',
    re.IGNORECASE
)

# ================================================
# Mapeamento de meses em português (nome -> número)
# ================================================

MESES_BR = {
    # Nomes completos
    'janeiro': 1,   'fevereiro': 2,  'março': 3,     'abril': 4,
    'maio': 5,      'junho': 6,      'julho': 7,      'agosto': 8,
    'setembro': 9,  'outubro': 10,   'novembro': 11,  'dezembro': 12,
    # Abreviações
    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4,
    'mai': 5, 'jun': 6, 'jul': 7, 'ago': 8,
    'set': 9, 'out': 10, 'nov': 11, 'dez': 12
}

# ================================================
# Padrões para detecção de banco pelo conteúdo
# ================================================

BANCO_KEYWORDS = {
    "Itaú":              ["itau", "itaú", "banco itau", "itaucard", "itaú card", "cartão itaú", "cartao itau"],
    "Bradesco":          ["bradesco"],
    "Santander":         ["santander", "santander sx", "santander free", "way santander"],
    "Banco do Brasil":   ["banco do brasil", "bb ", "ourocard"],
    "Caixa":             ["caixa economica", "caixa econômica", "cef", "cartões caixa", "cartoes caixa"],
    "Nubank":            ["nubank", "nu pagamentos"],
    "Inter":             ["banco inter", "bancointer", "inter&co", "inter mastercard", "inter visa"],
    "C6 Bank":           ["c6 bank", "c6bank", "c6 carbon", "carbon mastercard"],
    "BTG Pactual":       ["btg pactual", "btgpactual"],
    "XP":                ["xp investimentos", "xp inc", "xp visa infinite", "xp mastercard"],
    "Mercado Pago":      ["mercado pago", "mercadopago"],
    "PagBank":           ["pagbank", "pag seguro", "pagseguro"],
}
