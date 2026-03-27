"""
Funções auxiliares para o Assistente Financeiro Pessoal.

Inclui utilitários para:
  - Formatação de moeda brasileira
  - Conversão de valores e datas no padrão BR
  - Detecção de parcelas
  - Normalização de descrições para classificação
  - Detecção de tipo de transação (débito/crédito)
"""

import re
from datetime import datetime, date
from typing import Optional, Tuple, Dict

from app.utils.regex_patterns import MESES_BR


# ================================================
# Formatação de moeda
# ================================================

def formatar_moeda(valor: float) -> str:
    """
    Formata um valor numérico como moeda brasileira.

    Exemplo:
        1234.56  ->  "R$ 1.234,56"
        -150.00  -> "-R$ 150,00"

    Args:
        valor: Valor numérico a formatar

    Returns:
        String formatada em reais
    """
    sinal = "-" if valor < 0 else ""
    v = abs(valor)
    # Formata com separadores e converte para padrão BR
    formatado = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {formatado}"


# ================================================
# Conversão de valores brasileiros
# ================================================

def converter_valor_br(texto: str) -> Optional[float]:
    """
    Converte um valor monetário no formato brasileiro para float.

    Aceita:
        "R$ 1.234,56"  ->  1234.56
        "-1.234,56"    -> -1234.56
        "1234,56"      ->  1234.56

    Args:
        texto: String com o valor monetário

    Returns:
        Valor float ou None em caso de falha
    """
    if not texto:
        return None

    texto = texto.strip().replace("R$", "").replace("r$", "").strip()

    # Detecta sinal negativo (pode estar antes ou depois)
    negativo = texto.startswith("-") or texto.endswith("-")
    texto = texto.replace("-", "").replace("–", "").strip()

    try:
        if "," in texto and "." in texto:
            # Formato "1.234,56" -> "1234.56"
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            # Formato "1234,56" -> "1234.56"
            texto = texto.replace(",", ".")
        # Se só tem ponto, trata como decimal americano ou inteiro

        valor = float(texto)
        return -valor if negativo else valor

    except (ValueError, AttributeError):
        return None


# ================================================
# Parsing de datas brasileiras
# ================================================

def parsear_data_br(texto: str, ano_ref: Optional[int] = None) -> Optional[date]:
    """
    Converte uma string de data no padrão brasileiro para objeto date.

    Aceita:
        "15/01/2024"           -> date(2024, 1, 15)
        "15/01"                -> date(ano_ref, 1, 15)
        "15 de janeiro de 2024"-> date(2024, 1, 15)

    Args:
        texto:   String com a data
        ano_ref: Ano a usar quando a data não tem ano (padrão: ano atual)

    Returns:
        Objeto date ou None
    """
    if not texto:
        return None

    texto  = texto.strip()
    ano    = ano_ref or datetime.now().year

    # Formato dd/mm/yyyy ou dd-mm-yyyy
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$', texto)
    if m:
        dia, mes, ano_str = m.groups()
        a = int(ano_str)
        if a < 100:
            a += 2000
        try:
            return date(a, int(mes), int(dia))
        except ValueError:
            pass

    # Formato dd/mm (sem ano)
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})$', texto)
    if m:
        dia, mes = m.groups()
        try:
            return date(ano, int(mes), int(dia))
        except ValueError:
            pass

    # Formato por extenso: "15 de janeiro de 2024"
    m = re.search(
        r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        texto,
        re.IGNORECASE
    )
    if m:
        dia_s, mes_s, ano_s = m.groups()
        mes_n = MESES_BR.get(mes_s.lower())
        if mes_n:
            try:
                return date(int(ano_s), mes_n, int(dia_s))
            except ValueError:
                pass

    # Tentativas com formatos padrão Python
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"]:
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue

    # Formato Nubank/cartão: "18 FEV", "01 MAR", "25 DEZ"
    m = re.match(r'^(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,4})$', texto)
    if m:
        dia_s, mes_s = m.groups()
        mes_n = MESES_BR.get(mes_s.lower())
        if mes_n:
            try:
                return date(ano, mes_n, int(dia_s))
            except ValueError:
                pass

    return None


# ================================================
# Detecção de parcelas
# ================================================

def detectar_parcela(descricao: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Detecta informações de parcela em uma descrição de transação.

    Exemplos detectados:
        "Loja XYZ 3/10"         -> (3, 10)
        "Parcela 2 de 6"        -> (2, 6)
        "Parc. 01/12 Supermkt"  -> (1, 12)

    Args:
        descricao: Texto da transação

    Returns:
        Tupla (parcela_atual, parcelas_total) ou (None, None)
    """
    if not descricao:
        return None, None

    # Padrão "Parcela 3 de 10"
    m = re.search(r'parcela\s+(\d{1,2})\s+de\s+(\d{1,2})', descricao, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Padrão abreviado "Parc.3/10" ou "Pcl3/10"
    m = re.search(
        r'(?:parc|par|pcel|pcl)\.?\s*(\d{1,2})[/](\d{1,2})',
        descricao,
        re.IGNORECASE
    )
    if m:
        return int(m.group(1)), int(m.group(2))

    # Padrão "3/10" isolado (atual <= total e total > 1)
    for m in re.finditer(r'(?<!\d)0?(\d{1,2})[/](\d{1,2})(?!\d)', descricao):
        p_atual = int(m.group(1))
        p_total = int(m.group(2))
        if p_atual <= p_total and p_total > 1:
            return p_atual, p_total

    return None, None


# ================================================
# Normalização de descrição para classificação
# ================================================

def normalizar_descricao(descricao: str) -> str:
    """
    Normaliza a descrição de uma transação para uso na classificação.
    Remove ruídos: parcelas, datas, valores, IDs numéricos, etc.

    Args:
        descricao: Texto original da transação

    Returns:
        Texto normalizado em minúsculas
    """
    if not descricao:
        return ""

    texto = descricao.lower()

    # Remove informações de parcela
    texto = re.sub(r'\b\d{1,2}/\d{1,2}\b', '', texto)
    texto = re.sub(r'parcela\s+\d+\s+de\s+\d+', '', texto, flags=re.IGNORECASE)

    # Remove datas
    texto = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', texto)

    # Remove valores monetários
    texto = re.sub(r'r?\$\s*[\d.,]+', '', texto, flags=re.IGNORECASE)

    # Remove IDs numéricos longos (>= 6 dígitos)
    texto = re.sub(r'\b\d{6,}\b', '', texto)

    # Remove asteriscos, separadores duplos
    texto = re.sub(r'[*]{2,}', '', texto)

    # Colapsa múltiplos espaços
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto


# ================================================
# Detecção de tipo (débito / crédito)
# ================================================

PALAVRAS_CREDITO = {
    'salário', 'salario', 'transferência recebida', 'pix recebido',
    'ted recebida', 'doc recebido', 'depósito', 'deposito',
    'reembolso', 'devolução', 'devolucao', 'rendimento', 'dividendo',
    'cashback', 'crédito em conta', 'credito em conta', 'entrada',
    'restituição', 'restituicao', 'ressarcimento', 'pagamento recebido'
}

PALAVRAS_DEBITO = {
    'compra', 'débito', 'debito', 'saque', 'pagamento efetuado',
    'pix enviado', 'ted enviado', 'doc enviado', 'tarifa',
    'taxa', 'anuidade', 'boleto', 'parcela'
}


def detectar_tipo_transacao(descricao: str, valor: float) -> str:
    """
    Infere se uma transação é débito (saída) ou crédito (entrada).

    Critérios, em ordem de prioridade:
      1. Valor negativo -> débito
      2. Palavras-chave no texto -> débito ou crédito
      3. Padrão -> débito

    Args:
        descricao: Descrição da transação
        valor:     Valor da transação

    Returns:
        "debito" ou "credito"
    """
    if valor < 0:
        return "debito"

    desc_lower = descricao.lower()

    for palavra in PALAVRAS_CREDITO:
        if palavra in desc_lower:
            return "credito"

    for palavra in PALAVRAS_DEBITO:
        if palavra in desc_lower:
            return "debito"

    # Padrão conservador: débito
    return "debito"


# ================================================
# Utilitários gerais
# ================================================

def truncar_texto(texto: str, max_len: int = 50) -> str:
    """Trunca texto ao tamanho máximo, adicionando '...' se necessário."""
    if len(texto) <= max_len:
        return texto
    return texto[:max_len - 3] + "..."


def obter_mes_ano(d: date) -> Tuple[int, int]:
    """Retorna (mes, ano) de uma data."""
    return d.month, d.year


def calcular_percentual(parte: float, total: float) -> float:
    """Calcula percentual com proteção contra divisão por zero."""
    return (parte / total) * 100 if total else 0.0


def nome_mes(mes: int) -> str:
    """Retorna o nome do mês em português."""
    nomes = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    return nomes[mes] if 1 <= mes <= 12 else str(mes)


def periodo_label(mes: int, ano: int) -> str:
    """Retorna label formatado: 'Janeiro/2024'."""
    return f"{nome_mes(mes)}/{ano}"
