"""
Serviço de parsing (análise e extração) de extratos financeiros.

Responsável por transformar texto bruto (de OCR ou arquivo) em
uma lista estruturada de transações prontas para salvar no banco.

Suporta padrões de:
  - Bancos brasileiros: Itaú, Bradesco, Santander, BB, Caixa, Nubank, Inter
  - Cartões de crédito: Visa, Mastercard, Elo, Amex
  - Formato genérico (fallback)
"""

import re
import logging
from datetime import date
from typing import List, Dict, Optional, Any

from app.utils.helpers import (
    converter_valor_br,
    parsear_data_br,
    detectar_parcela,
    detectar_tipo_transacao,
    normalizar_descricao
)
from app.utils.regex_patterns import (
    ITAU_TRANSACAO, BRADESCO_TRANSACAO, BRADESCO_FATURA_TRANSACAO,
    SANTANDER_TRANSACAO,
    BB_TRANSACAO, CAIXA_TRANSACAO, NUBANK_TRANSACAO, INTER_TRANSACAO,
    C6_FATURA_TRANSACAO,
    MP_FATURA_TRANSACAO, MP_FATURA_VENCIMENTO,
    CARTAO_LINHA, CARTAO_LINHA_DATA_COMPLETA, CARTAO_LINHA_MES_TEXTO,
    VALOR_NUMERICO_BR, DATA_BR_COMPLETA, DATA_BR_CURTA,
    BANCO_KEYWORDS, MESES_BR
)

logger = logging.getLogger(__name__)

# Tipo auxiliar para uma transação bruta (antes de salvar no BD)
TransacaoBruta = Dict[str, Any]


class ParserService:
    """
    Serviço de parsing de extratos financeiros.

    Detecta automaticamente o banco/cartão e aplica o parser
    adequado. Sempre há um fallback genérico caso o padrão
    específico não funcione.
    """

    def __init__(self):
        # Mapa: (substring_identificadora -> método_parser)
        self._parsers = {
            "itau":             self._parse_itau,
            "itaú":             self._parse_itau,
            "itaucard":         self._parse_cartao_generico,
            "bradesco":         self._parse_bradesco,
            "santander":        self._parse_santander,
            "way santander":    self._parse_cartao_generico,
            "banco do brasil":  self._parse_bb,
            "bb ":              self._parse_bb,
            "ourocard":         self._parse_cartao_generico,
            "caixa":            self._parse_caixa,
            "nubank":           self._parse_nubank,
            "nu pagamentos":    self._parse_nubank,
            "banco inter":      self._parse_inter,
            "bancointer":       self._parse_inter,
            "inter&co":         self._parse_cartao_generico,
            "c6 bank":          self._parse_c6_fatura,
            "c6bank":           self._parse_c6_fatura,
            "c6 carbon":        self._parse_c6_fatura,
            "mercado pago":     self._parse_mp_fatura,
            "mercadopago":      self._parse_mp_fatura,
            "pagbank":          self._parse_cartao_generico,
            "pagseguro":        self._parse_cartao_generico,
            "btg pactual":      self._parse_cartao_generico,
            "btgpactual":       self._parse_cartao_generico,
            "xp investimentos": self._parse_cartao_generico,
            "xp inc":           self._parse_cartao_generico,
        }

    # --------------------------------------------------
    # Interface pública
    # --------------------------------------------------

    def parsear_texto(
        self,
        texto: str,
        banco: Optional[str] = None,
        tipo_extrato: str = "bancario",
        ano_ref: Optional[int] = None
    ) -> List[TransacaoBruta]:
        """
        Analisa texto de extrato e retorna lista de transações.

        Args:
            texto:        Texto bruto do extrato (de OCR ou arquivo)
            banco:        Nome do banco (opcional; detectado se None)
            tipo_extrato: "bancario" ou "cartao"
            ano_ref:      Ano de referência para datas sem ano

        Returns:
            Lista de dicionários com os dados de cada transação
        """
        if not texto or not texto.strip():
            return []

        texto = self._limpar_texto(texto)

        # Detecta banco se não informado
        banco_detectado = banco or self._detectar_banco(texto)
        logger.info(f"Banco detectado: {banco_detectado or 'Genérico'}")

        # Seleciona parser específico ou usa genérico
        transacoes = []
        if banco_detectado:
            banco_lower = banco_detectado.lower()
            for chave, parser in self._parsers.items():
                if chave in banco_lower:
                    transacoes = parser(texto, ano_ref)
                    break

        # Fallback genérico se não encontrou transações
        if not transacoes:
            if tipo_extrato == "cartao":
                transacoes = self._parse_cartao_generico(texto, ano_ref)
            else:
                transacoes = self._parse_generico(texto, ano_ref)

        # Preenche campos derivados
        for t in transacoes:
            t.setdefault("fonte", banco_detectado or "Desconhecido")
            self._enriquecer_transacao(t)

        logger.info(f"Total de transações extraídas: {len(transacoes)}")
        return transacoes

    # --------------------------------------------------
    # Parsers específicos por banco
    # --------------------------------------------------

    def _parse_itau(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato Itaú."""
        transacoes = []
        for m in ITAU_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2), m.group(3)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })
        return transacoes

    def _parse_bradesco(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato/fatura Bradesco.

        Tenta primeiro o formato de extrato bancário (dd/mm/yyyy).
        Se não encontrar transações, usa o parser de fatura de cartão (dd/mm).
        """
        # Formato extrato bancário (dd/mm/yyyy)
        transacoes = []
        for m in BRADESCO_TRANSACAO.finditer(texto):
            data_s = m.group(1)
            desc   = m.group(3).strip()
            valor_s = m.group(4)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc,
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })

        # Nenhuma transação no formato extrato → tenta formato fatura de cartão
        if not transacoes:
            transacoes = self._parse_bradesco_fatura(texto, ano_ref)
        if not transacoes:
            transacoes = self._parse_bradesco_fatura_colunar(texto, ano_ref)

        return transacoes

    def _parse_bradesco_fatura(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser dedicado para fatura de cartão Bradesco.

        Suporta tanto faturas fechadas simples quanto faturas em aberto com
        colunas intermediárias de moeda, como:
        "10/03 COMPRA USD 0,00 R$ 0,00 R$ 129,90".

        Nesses casos, o valor considerado é o ÚLTIMO valor monetário da linha.
        """
        IGNORAR = {
            "total para", "total da fatura", "saldo anterior",
            "créditos/pagamentos", "compras/débitos", "(=)total",
        }
        PALAVRAS_CREDITO = {"pagto", "pag boleto", "crédito", "credito", "pagamento"}

        transacoes = []
        for linha in texto.splitlines():
            linha = re.sub(r"\s+", " ", linha).strip()
            if not linha:
                continue

            m_data = re.match(r'^(\d{2}/\d{2})\s+(.+)$', linha)
            if not m_data:
                continue

            data_s, restante = m_data.groups()
            valores = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', restante)
            if not valores:
                continue

            valor_s = valores[-1]
            idx_ultimo_valor = restante.rfind(valor_s)
            if idx_ultimo_valor < 0:
                continue

            desc = restante[:idx_ultimo_valor].strip(" -|")
            desc = re.sub(
                r'\s+(?:US\$|USD|R\$)\s*-?\d{1,3}(?:\.\d{3})*,\d{2}',
                '',
                desc,
                flags=re.IGNORECASE,
            )
            desc = re.sub(r'\s+(?:US\$|USD|R\$)\s*$', '', desc, flags=re.IGNORECASE).strip(" -|")
            desc_lower = desc.lower()

            if any(ig in desc_lower for ig in IGNORAR):
                continue
            if not re.search(r'[a-zA-ZÀ-ú]', desc):
                continue

            valor = converter_valor_br(valor_s)
            data = parsear_data_br(data_s, ano_ref)
            if valor is None or not data:
                continue

            tipo = "credito" if valor < 0 or any(p in desc_lower for p in PALAVRAS_CREDITO) else "debito"

            transacoes.append({
                "data": data,
                "descricao": normalizar_descricao(desc),
                "valor": abs(valor),
                "tipo": tipo,
            })

        return transacoes

    def _parse_bradesco_fatura_colunar(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Reconstrói faturas Bradesco em aberto extraídas por OCR em colunas separadas."""
        linhas = [re.sub(r"\s+", " ", linha).strip() for linha in texto.splitlines()]
        linhas = [linha for linha in linhas if linha]

        transacoes = []
        i = 0
        while i < len(linhas):
            linha_atual = linhas[i].lower()
            if "hist" not in linha_atual and linha_atual not in {"| data", "data"}:
                i += 1
                continue

            idx_data = None
            for j in range(max(i - 12, 0), i + 1):
                if linhas[j].lower() in {"| data", "data"}:
                    idx_data = j
                    break

            if idx_data is None:
                i += 1
                continue

            datas = []
            j = idx_data + 1
            while j < len(linhas) and re.fullmatch(r'\d{2}/\d{2}', linhas[j]):
                datas.append(linhas[j])
                j += 1

            descricoes = []
            k = i + 1
            while k < len(linhas):
                linha_desc = linhas[k]
                linha_desc_lower = linha_desc.lower()
                if linha_desc_lower.startswith("total para:"):
                    break
                if self._ignorar_linha_bradesco_colunar(linha_desc):
                    k += 1
                    continue
                descricoes.append(linha_desc)
                k += 1

            if not datas or not descricoes:
                i = k + 1
                continue

            prox_secao = len(linhas)

            valores = []
            for linha_valor in linhas[k + 1:prox_secao]:
                if not re.fullmatch(r'-?R\$\s*-?\d{1,3}(?:\.\d{3})*,\d{2}', linha_valor, re.IGNORECASE):
                    continue
                valor = converter_valor_br(linha_valor)
                if valor is None or abs(valor) < 0.00001:
                    continue
                valores.append(linha_valor)

            quantidade = min(len(datas), len(descricoes), len(valores))
            for data_s, desc, valor_s in zip(datas[:quantidade], descricoes[:quantidade], valores[:quantidade]):
                desc_lower = desc.lower()
                if any(ig in desc_lower for ig in ("saldo anterior", "total para", "créditos/pagamentos", "compras/débitos")):
                    continue

                valor = converter_valor_br(valor_s)
                data = parsear_data_br(data_s, ano_ref)
                if valor is None or not data:
                    continue

                tipo = "credito" if valor < 0 or any(p in desc_lower for p in ("pagto", "pag boleto", "crédito", "credito", "pagamento")) else "debito"
                transacoes.append({
                    "data": data,
                    "descricao": normalizar_descricao(desc),
                    "valor": abs(valor),
                    "tipo": tipo,
                })

            i = prox_secao

        return transacoes

    @staticmethod
    def _ignorar_linha_bradesco_colunar(linha: str) -> bool:
        linha_lower = linha.lower()
        if linha_lower.startswith("total para:"):
            return True
        if linha_lower in {
            "| histórico", "| historico", "histórico", "historico",
            "moeda de", "origem", "uss", "| cotação us$", "| cotacao us$",
            "| as", "| a",
        }:
            return True
        if linha_lower.startswith("bradesco data:"):
            return True
        if linha_lower.startswith("situação do extrato:") or linha_lower.startswith("situacao do extrato:"):
            return True
        if linha_lower.startswith("aplicativo bradesco"):
            return True
        if re.fullmatch(r'xxxx(?:\.xxxx){2,3}\.\d{4}', linha_lower):
            return True
        if re.fullmatch(r'(?:us\$|usd|r\$)\s*-?\d{1,3}(?:\.\d{3})*,\d{2}', linha, re.IGNORECASE):
            return True
        return not re.search(r'[a-zA-ZÀ-ú]', linha)

    def _parse_santander(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato/fatura Santander."""
        transacoes = []
        for m in SANTANDER_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2), m.group(3)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })
        if not transacoes:
            transacoes = self._parse_cartao_generico(texto, ano_ref)
        return transacoes

    def _parse_bb(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato/fatura Banco do Brasil."""
        transacoes = []
        for m in BB_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2), m.group(3)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })
        if not transacoes:
            transacoes = self._parse_cartao_generico(texto, ano_ref)
        return transacoes

    def _parse_caixa(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato/fatura Caixa Econômica Federal."""
        transacoes = []
        for m in CAIXA_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2), m.group(3)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })
        if not transacoes:
            transacoes = self._parse_cartao_generico(texto, ano_ref)
        return transacoes

    def _parse_nubank(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de fatura Nubank.

        Formato real (2024+):
            18 FEV •••• 7596 iFood R$ 61,00
            18 FEV •••• 8099 Hotel Xpto - Parcela 1/2 R$ 1.234,56
            23 FEV Pagamento em 23 FEV −R$ 1.706,22   <- ignorado
        """
        transacoes = []
        IGNORAR = ("pagamento", "total a pagar", "fatura anterior", "saldo em")
        for m in NUBANK_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2).strip(), m.group(3)
            # Ignora linhas de pagamento e resumo
            if any(desc.lower().startswith(p) for p in IGNORAR):
                continue
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc,
                    "valor": abs(valor),
                    "tipo": "debito",
                })
        return transacoes

    def _parse_inter(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser de extrato/fatura Banco Inter."""
        transacoes = []
        for m in INTER_TRANSACAO.finditer(texto):
            data_s, desc, valor_s = m.group(1), m.group(2), m.group(3)
            valor = converter_valor_br(valor_s)
            data  = parsear_data_br(data_s, ano_ref)
            if valor is not None and data:
                transacoes.append({
                    "data": data,
                    "descricao": desc.strip(),
                    "valor": abs(valor),
                    "tipo": detectar_tipo_transacao(desc, valor),
                })
        if not transacoes:
            transacoes = self._parse_cartao_generico(texto, ano_ref)
        return transacoes

    def _parse_c6_fatura(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser dedicado para fatura de cartão C6 Bank.

        Formato: DD mmm DESCRIÇÃO VALOR
        Ex: "30 jan UBER UBER *TRIP HELP.U 13,99"
            "04 nov OTORRINOFACE - Parcela 4/5 3.200,00"
            "03 fev Pag Fatura Boleto 7.524,49"  <- crédito (pagamento)

        Ajuste inteligente de ano: transações com mês muito posterior ao
        vencimento (ex: nov em fatura de março) são atribuídas ao ano anterior.
        """
        IGNORAR = {
            "subtotal deste cart", "valores em reais", "total a pagar",
            "resumo da fatura", "formas de pagamento", "transações do cartão",
            "transacoes do cartao",
        }
        PALAVRAS_CREDITO = {"pag fatura", "pagamento fatura", "crédito", "credito", "estorno"}

        # Detecta mês de vencimento no texto ("Vencimento: 01 de Março")
        vencimento_mes = None
        m_venc = re.search(
            r'vencimento[:\s]+\d{1,2}\s+de\s+(\w+)',
            texto, re.IGNORECASE
        )
        if m_venc:
            vencimento_mes = MESES_BR.get(m_venc.group(1).lower())

        # Determina ano de referência
        ano = ano_ref or date.today().year
        if not ano_ref:
            # Tenta extrair ano da data de fechamento (ex: "20/02/26")
            m_ano = re.search(r'\d{2}/\d{2}/(\d{2,4})', texto)
            if m_ano:
                a = int(m_ano.group(1))
                ano = a + 2000 if a < 100 else a

        referencia_mes = vencimento_mes
        referencia_ano = ano
        m_fechamento = re.search(
            r'fechamento[:\s]+\d{1,2}/(\d{1,2})/(\d{2,4})',
            texto,
            re.IGNORECASE,
        )
        if m_fechamento:
            referencia_mes = int(m_fechamento.group(1))
            ano_fechamento = int(m_fechamento.group(2))
            referencia_ano = ano_fechamento + 2000 if ano_fechamento < 100 else ano_fechamento
        elif vencimento_mes:
            referencia_mes = 12 if vencimento_mes == 1 else vencimento_mes - 1
            referencia_ano = ano - 1 if vencimento_mes == 1 else ano

        transacoes = []
        for m in C6_FATURA_TRANSACAO.finditer(texto):
            dia_s   = m.group(1)
            mes_s   = m.group(2).lower()
            desc    = m.group(3).strip()
            valor_s = m.group(4)

            # Pula linhas de cabeçalho/resumo
            desc_lower = desc.lower()
            if any(ig in desc_lower for ig in IGNORAR):
                continue
            if not re.search(r'[a-zA-ZÀ-ú]', desc):
                continue

            mes_n = MESES_BR.get(mes_s)
            if not mes_n:
                continue

            # Usa o ciclo da fatura como referência. Meses posteriores ao
            # fechamento/vencimento pertencem ao ano anterior.
            ano_transacao = referencia_ano
            if referencia_mes and mes_n > referencia_mes:
                ano_transacao -= 1

            try:
                data = date(ano_transacao, mes_n, int(dia_s))
            except ValueError:
                continue

            valor = converter_valor_br(valor_s)
            if valor is None:
                continue

            if any(p in desc_lower for p in PALAVRAS_CREDITO):
                tipo = "credito"
            else:
                tipo = "debito"

            parcela_atual, parcelas_total = detectar_parcela(desc)

            transacao = {
                "data":      data,
                "descricao": normalizar_descricao(desc),
                "valor":     abs(valor),
                "tipo":      tipo,
            }
            if parcela_atual:
                transacao["parcela_atual"] = parcela_atual
                transacao["parcelas_total"] = parcelas_total

            transacoes.append(transacao)

        return transacoes

    def _parse_mp_fatura(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser dedicado para fatura de cartão Mercado Pago.

        Formato por linha: "DD/MM DESCRIÇÃO R$ VALOR"
        Seções:
          - "Movimentações na fatura": pagamentos/créditos (tipo=credito)
          - "Cartão Visa/Mastercard [...]": compras (tipo=debito)

        Ajuste de ano: se mês da transação > mês do vencimento → ano anterior.
        """
        IGNORAR = {
            "data movimentações", "data movimentacoes",
            "informações complementares", "resumo da fatura",
            "consumos de", "parcelamento de fatura", "emitido em",
            "detalhes de consumo",
        }
        KEYWORDS_CREDITO = {
            "pagamento", "crédito concedido", "credito concedido",
            "estorno", "reembolso", "devolução", "devolucao",
        }

        # Extrai data de vencimento para calcular o ano de cada transação
        m_venc = MP_FATURA_VENCIMENTO.search(texto)
        if m_venc:
            partes = m_venc.group(1).split('/')
            venc_mes, venc_ano = int(partes[1]), int(partes[2])
        else:
            venc_mes = date.today().month
            venc_ano = ano_ref or date.today().year

        secao = None   # "pagamento" = créditos / "cartao" = débitos
        transacoes = []

        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue

            linha_lower = linha.lower()

            # Detecta seção de pagamentos/créditos
            if "movimentações na fatura" in linha_lower or "movimentacoes na fatura" in linha_lower:
                secao = "pagamento"
                continue

            # Detecta seção de cartão (compras)
            if re.match(r'cart[aã]o\s+(visa|mastercard|elo)', linha_lower):
                secao = "cartao"
                continue

            # Pula cabeçalhos, rodapés e linhas de câmbio
            if any(ig in linha_lower for ig in IGNORAR):
                continue
            if re.match(r'^[A-Z]{3}\s+\d+\s*=', linha):  # ex: "USD 1 = R$ 5.29"
                continue

            # Tenta casar linha de transação
            m = MP_FATURA_TRANSACAO.match(linha)
            if not m or secao is None:
                continue

            data_s  = m.group(1)   # "DD/MM"
            desc    = m.group(2).strip()
            valor_s = m.group(3)

            dia_s, mes_s = data_s.split('/')
            mes_trans = int(mes_s)
            ano_trans = venc_ano if mes_trans <= venc_mes else venc_ano - 1

            try:
                data = date(ano_trans, mes_trans, int(dia_s))
            except ValueError:
                continue

            valor = converter_valor_br(valor_s)
            if valor is None:
                continue

            desc_lower = desc.lower()
            if secao == "pagamento" or any(kw in desc_lower for kw in KEYWORDS_CREDITO):
                tipo = "credito"
            else:
                tipo = "debito"

            transacoes.append({
                "data":      data,
                "descricao": normalizar_descricao(desc),
                "valor":     abs(valor),
                "tipo":      tipo,
            })

        return transacoes

    def _parse_cartao_generico(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """Parser genérico para faturas de cartão de crédito.

        Cobre formatos comuns entre emissores como Itaú, Santander, BB,
        Caixa, XP/BTG, PagBank e layouts sem detecção explícita do banco.
        """
        ignorar = (
            "total", "subtotal", "saldo anterior", "saldo atual", "limite",
            "anuidade", "encargos", "juros", "iof", "pagamento mínimo",
            "pagamento minimo", "melhor dia de compra", "fechamento",
            "vencimento", "resumo da fatura", "fatura fechada", "fatura aberta",
            "lançamentos futuros", "lancamentos futuros", "parcelamento de fatura",
        )
        palavras_credito = (
            "pagamento", "pag fatura", "pagto", "credito", "crédito",
            "estorno", "reembolso", "devolucao", "devolução",
        )

        referencia_mes, referencia_ano = self._extrair_referencia_fatura(texto, ano_ref)
        transacoes = []
        vistos = set()

        for m in CARTAO_LINHA.finditer(texto):
            data = parsear_data_br(m.group(1), referencia_ano)
            if data and referencia_mes and data.month > referencia_mes:
                data = date(referencia_ano - 1, data.month, data.day)
            self._adicionar_transacao_cartao(
                transacoes, vistos, data, m.group(2), m.group(3), ignorar, palavras_credito
            )

        for m in CARTAO_LINHA_DATA_COMPLETA.finditer(texto):
            data = parsear_data_br(m.group(1), referencia_ano)
            self._adicionar_transacao_cartao(
                transacoes, vistos, data, m.group(2), m.group(3), ignorar, palavras_credito
            )

        for m in CARTAO_LINHA_MES_TEXTO.finditer(texto):
            mes = MESES_BR.get(m.group(2).lower())
            if not mes:
                continue
            ano_data = referencia_ano
            if referencia_mes and mes > referencia_mes:
                ano_data -= 1
            try:
                data = date(ano_data, mes, int(m.group(1)))
            except ValueError:
                continue
            self._adicionar_transacao_cartao(
                transacoes, vistos, data, m.group(3), m.group(4), ignorar, palavras_credito
            )

        self._parse_cartao_linhas_quebradas(
            texto,
            referencia_mes,
            referencia_ano,
            ignorar,
            palavras_credito,
            transacoes,
            vistos,
        )

        transacoes.sort(key=lambda item: (item["data"], item["descricao"], item["valor"]))
        return transacoes

    def _parse_generico(self, texto: str, ano_ref: Optional[int]) -> List[TransacaoBruta]:
        """
        Parser genérico de fallback.
        Processa linha a linha buscando data + descrição + valor.
        """
        transacoes = []
        linhas = texto.splitlines()

        for linha in linhas:
            linha = linha.strip()
            if len(linha) < 10:
                continue

            # Busca data na linha
            data = None
            for padrao in [DATA_BR_COMPLETA, DATA_BR_CURTA]:
                m = padrao.search(linha)
                if m:
                    data = parsear_data_br(m.group(0), ano_ref)
                    if data:
                        break

            if not data:
                continue

            # Busca valor na linha
            valores = VALOR_NUMERICO_BR.findall(linha)
            if not valores:
                continue

            valor_s  = valores[-1]   # Pega o último valor (geralmente o montante)
            valor    = converter_valor_br(valor_s)
            if valor is None:
                continue

            # Extrai descrição (texto entre data e valor)
            desc = linha
            desc = re.sub(r'\d{1,2}[/\-]\d{1,2}([/\-]\d{2,4})?', '', desc)
            desc = re.sub(re.escape(valor_s), '', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()

            if not desc or len(desc) < 3:
                continue

            transacoes.append({
                "data": data,
                "descricao": desc,
                "valor": abs(valor),
                "tipo": detectar_tipo_transacao(desc, valor),
            })

        return transacoes

    # --------------------------------------------------
    # Helpers internos
    # --------------------------------------------------

    def _detectar_banco(self, texto: str) -> Optional[str]:
        """Detecta o banco pelo conteúdo do texto."""
        texto_lower = texto.lower()
        for banco, keywords in BANCO_KEYWORDS.items():
            for kw in keywords:
                if kw in texto_lower:
                    return banco
        return None

    def _limpar_texto(self, texto: str) -> str:
        """Remove caracteres desnecessários do texto bruto."""
        # Remove hifens excessivos (separadores de tabela)
        texto = re.sub(r'-{3,}', '', texto)
        # Remove múltiplos espaços/tabulações -> espaço único
        texto = re.sub(r'[ \t]+', ' ', texto)
        # Normaliza quebras de linha
        texto = re.sub(r'\r\n', '\n', texto)
        texto = re.sub(r'\r', '\n', texto)
        linhas = [linha.strip() for linha in texto.split('\n')]
        return '\n'.join(linhas)

    def _extrair_referencia_fatura(
        self,
        texto: str,
        ano_ref: Optional[int],
    ) -> tuple[Optional[int], int]:
        """Extrai mês/ano de referência da fatura para resolver datas sem ano."""
        if ano_ref:
            return None, ano_ref

        match_vencimento = re.search(
            r'(?:vence\s+em|vencimento\s*:?)\s*(\d{2})/(\d{2})/(\d{2,4})',
            texto,
            re.IGNORECASE,
        )
        if match_vencimento:
            ano = int(match_vencimento.group(3))
            if ano < 100:
                ano += 2000
            return int(match_vencimento.group(2)), ano

        match_data = DATA_BR_COMPLETA.search(texto)
        if match_data:
            dia_s, mes_s, ano_s = match_data.groups()
            ano = int(ano_s)
            if ano < 100:
                ano += 2000
            return int(mes_s), ano

        return None, date.today().year

    def _adicionar_transacao_cartao(
        self,
        transacoes: List[TransacaoBruta],
        vistos: set[tuple[date, str, float, str]],
        data: Optional[date],
        descricao: str,
        valor_s: str,
        ignorar: tuple[str, ...],
        palavras_credito: tuple[str, ...],
    ) -> None:
        if not data:
            return

        desc = descricao.strip()
        desc = re.sub(r'\s+(?:r\$|us\$|usd)\s*$', '', desc, flags=re.IGNORECASE)
        desc_lower = desc.lower()
        if len(desc) < 3 or any(chave in desc_lower for chave in ignorar):
            return
        if not re.search(r'[a-zA-ZÀ-ú]', desc):
            return

        valor = converter_valor_br(valor_s)
        if valor is None:
            return

        tipo = "credito" if any(palavra in desc_lower for palavra in palavras_credito) or valor < 0 else "debito"
        transacao = {
            "data": data,
            "descricao": normalizar_descricao(desc),
            "valor": abs(valor),
            "tipo": tipo,
        }
        chave = (transacao["data"], transacao["descricao"], transacao["valor"], transacao["tipo"])
        if chave in vistos:
            return
        vistos.add(chave)
        transacoes.append(transacao)

    def _parse_cartao_linhas_quebradas(
        self,
        texto: str,
        referencia_mes: Optional[int],
        referencia_ano: int,
        ignorar: tuple[str, ...],
        palavras_credito: tuple[str, ...],
        transacoes: List[TransacaoBruta],
        vistos: set[tuple[date, str, float, str]],
    ) -> None:
        """Reconstrói transações de cartão quando o OCR quebra descrição e valor em linhas separadas."""
        linhas = [re.sub(r'\s+', ' ', linha).strip() for linha in texto.splitlines()]
        linhas = [linha for linha in linhas if linha]
        padrao_data = re.compile(r'^\d{2}/\d{2}(?:/\d{2,4})?\b')

        i = 0
        while i < len(linhas):
            linha = linhas[i]
            if not padrao_data.match(linha):
                i += 1
                continue

            combinado = linha
            consumidas = 1
            for proxima in linhas[i + 1:i + 4]:
                if padrao_data.match(proxima):
                    break
                combinado = f"{combinado} {proxima}"
                consumidas += 1

                match = CARTAO_LINHA_DATA_COMPLETA.match(combinado)
                if match:
                    data = parsear_data_br(match.group(1), referencia_ano)
                    self._adicionar_transacao_cartao(
                        transacoes,
                        vistos,
                        data,
                        match.group(2),
                        match.group(3),
                        ignorar,
                        palavras_credito,
                    )
                    break

                match = CARTAO_LINHA.match(combinado)
                if match:
                    data = parsear_data_br(match.group(1), referencia_ano)
                    if data and referencia_mes and data.month > referencia_mes:
                        data = date(referencia_ano - 1, data.month, data.day)
                    self._adicionar_transacao_cartao(
                        transacoes,
                        vistos,
                        data,
                        match.group(2),
                        match.group(3),
                        ignorar,
                        palavras_credito,
                    )
                    break

            i += consumidas

    def _enriquecer_transacao(self, transacao: TransacaoBruta) -> None:
        """
        Enriquece uma transação com informações derivadas:
          - Identificação de parcelas
          - Normalização da descrição
        """
        desc = transacao.get("descricao", "")
        p_atual, p_total = detectar_parcela(desc)
        if p_atual:
            transacao["parcela_atual"]  = p_atual
            transacao["parcelas_total"] = p_total
        else:
            transacao.setdefault("parcela_atual",  None)
            transacao.setdefault("parcelas_total", None)
