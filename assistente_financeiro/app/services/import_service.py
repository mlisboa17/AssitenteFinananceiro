"""
Serviço de importação de extratos financeiros.

Suporta os formatos:
  - PDF  : via OCR (pytesseract) ou extração digital
  - CSV  : via pandas
  - Excel: via pandas + openpyxl
  - OFX  : via ofxparse (padrão Open Financial Exchange)
  - Imagens: JPG, PNG, BMP, TIFF, WEBP (via OCR)
  - DOCX : via python-docx
  - TXT  : leitura direta

O serviço orquestra OCR → Parser → Classifier → persistência no BD.
"""

import os
import re
import logging
import calendar
from datetime import date
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import Transacao, Extrato, Categoria, EventoFinanceiro, CartaoCredito
from app.services.ocr_service        import OCRService
from app.services.parser_service     import ParserService
from app.services.classifier_service import ClassifierService
from app.utils.helpers import parsear_data_br, converter_valor_br, detectar_tipo_transacao, normalizar_descricao

logger = logging.getLogger(__name__)

KEYWORDS_ESTORNO_REFERENCIA = (
    "estorno", "reembolso", "devolucao", "devolução", "chargeback",
    "cancelamento", "compra cancelada", "valor estornado",
)

KEYWORDS_MOVIMENTO_NAO_CONSUMO = (
    "pagamento", "pagto", "pag fatura", "quitacao", "quitação",
    "credito concedido", "crédito concedido", "credito em conta", "crédito em conta",
    "transferencia", "transferência", "pix enviado", "pix recebido",
    "ted", "doc ", "deposito", "depósito", "cashback", "ajuste de limite",
    "limite", "saldo anterior", "saldo atual", "total da fatura", "total para",
    "resumo da fatura", "parcelamento de fatura", "lancamentos futuros",
    "lançamentos futuros", "anuidade", "encargos", "juros", "mora", "multa",
    "tarifa", "taxa",
)

BANCO_CARTAO_LABELS = {
    "nubank": "Nubank",
    "inter": "Inter",
    "c6": "C6 Bank",
    "xp": "XP",
    "itau": "Itaú",
    "bradesco": "Bradesco",
    "santander": "Santander",
    "bb": "Banco do Brasil",
    "caixa": "Caixa",
    "pagbank": "PagBank",
    "generico": "Cartão Importado",
}

if TYPE_CHECKING:
    import pandas as pd


class ImportService:
    """
    Serviço de importação multi-formato de extratos financeiros.

    Fluxo para cada formato:
      1. Leitura do arquivo
      2. Extração de transações (parsing / OCR)
      3. Classificação automática por categoria
      4. Persistência no banco de dados
      5. Retorno com resumo da importação
    """

    def __init__(self, db: Session):
        self.db         = db
        self.ocr        = OCRService()
        self.parser     = ParserService()
        self.classifier = ClassifierService(db)

    # ================================================
    # Importação de PDF
    # ================================================

    def importar_pdf(
        self,
        caminho: str,
        banco: Optional[str] = None,
        tipo_extrato: str = "bancario",
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Importa um extrato em formato PDF.

        Args:
            caminho:      Caminho do arquivo PDF
            banco:        Nome do banco (autodetectado se None)
            tipo_extrato: "bancario" ou "cartao"
            conta_id:     ID da conta bancária (opcional)
            cartao_id:    ID do cartão de crédito (opcional)

        Returns:
            Dicionário com resumo da importação
        """
        logger.info(f"Importando PDF: {caminho}")
        info_cartao = {"cartao_criado": False}

        if tipo_extrato == "cartao" and not cartao_id:
            info_cartao = self._obter_ou_criar_cartao_importado(
                caminho=caminho,
                formato=".pdf",
                senha=senha,
            )
            cartao_id = info_cartao["cartao_id"]

        texto = self.ocr.extrair_texto_pdf(caminho, senha=senha)
        banco = banco or self.ocr.detectar_banco(texto)

        transacoes_brutas = self.parser.parsear_texto(
            texto,
            banco=banco,
            tipo_extrato=tipo_extrato,
        )

        if not transacoes_brutas:
            classificacao = self.classifier.classificar_tipo_documento(texto)
            tipo_documento = classificacao["tipo"]
            if tipo_documento in {
                "comprovante_pagamento_bancario",
                "recibo_despesa",
                "nota_fiscal",
                "boleto",
                "comprovante_compra",
            }:
                logger.info(
                    "PDF '%s' não parece extrato; redirecionando para importação de documento (%s).",
                    os.path.basename(caminho),
                    tipo_documento,
                )
                return self.importar_por_tipo_documento(
                    caminho=caminho,
                    tipo_documento=tipo_documento,
                    conta_id=conta_id,
                    cartao_id=cartao_id,
                    senha=senha,
                )

        resultado = self._salvar_transacoes(
            transacoes_brutas,
            arquivo_nome=os.path.basename(caminho),
            arquivo_path=caminho,
            tipo=tipo_extrato,
            banco=banco,
            conta_id=conta_id,
            cartao_id=cartao_id,
        )
        resultado["cartao_criado"] = info_cartao.get("cartao_criado", False)
        return resultado

    # ================================================
    # Importação de CSV
    # ================================================

    def importar_csv(
        self,
        caminho: str,
        mapeamento: Optional[Dict[str, str]] = None,
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
        separador: str = ",",
        encoding: str = "utf-8",
        tipo_extrato: str = "bancario",
    ) -> Dict[str, Any]:
        """
        Importa um extrato em formato CSV.

        Args:
            caminho:    Caminho do arquivo CSV
            mapeamento: Mapa de colunas {"data": "col_data", "descricao": "col_desc", ...}
                        Se None, usa mapeamento automático por nomes comuns
            conta_id:   ID da conta (opcional)
            cartao_id:  ID do cartão (opcional)
            separador:  Separador de colunas (padrão: ",")
            encoding:   Encoding do arquivo (padrão: "utf-8")

        Returns:
            Resumo da importação
        """
        import pandas as pd

        logger.info(f"Importando CSV: {caminho}")
        info_cartao = {"cartao_criado": False}

        if tipo_extrato == "cartao" and not cartao_id:
            info_cartao = self._obter_ou_criar_cartao_importado(
                caminho=caminho,
                formato=".csv",
                separador=separador,
                encoding=encoding,
            )
            cartao_id = info_cartao["cartao_id"]

        # Tenta encoding UTF-8, depois latin-1 (comum em extratos brasileiros)
        for enc in [encoding, "latin-1", "utf-8-sig"]:
            try:
                df = pd.read_csv(caminho, sep=separador, encoding=enc)
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise ValueError(f"Não foi possível ler o arquivo CSV: {caminho}")

        # Detecta formato específico de cartão de crédito
        if tipo_extrato == "cartao" or cartao_id:
            transacoes_brutas = self._parsear_csv_cartao(df)
        else:
            mapeamento = mapeamento or self._detectar_mapeamento_csv(df.columns.tolist())
            transacoes_brutas = self._df_para_transacoes(df, mapeamento)

        resultado = self._salvar_transacoes(
            transacoes_brutas,
            arquivo_nome=os.path.basename(caminho),
            arquivo_path=caminho,
            tipo="cartao" if tipo_extrato == "cartao" else "csv",
            conta_id=conta_id,
            cartao_id=cartao_id,
        )
        resultado["cartao_criado"] = info_cartao.get("cartao_criado", False)
        return resultado

    # ================================================
    # Importação de Excel
    # ================================================

    def importar_excel(
        self,
        caminho: str,
        mapeamento: Optional[Dict[str, str]] = None,
        aba: Optional[str] = None,
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
        tipo_extrato: str = "bancario",
    ) -> Dict[str, Any]:
        """
        Importa um extrato em formato Excel (.xlsx ou .xls).

        Args:
            caminho:   Caminho do arquivo Excel
            mapeamento: Mapa de colunas (opcional)
            aba:       Nome da aba a ler (None = primeira aba)
            conta_id:  ID da conta (opcional)
            cartao_id: ID do cartão (opcional)

        Returns:
            Resumo da importação
        """
        import pandas as pd

        logger.info(f"Importando Excel: {caminho}")
        info_cartao = {"cartao_criado": False}

        if tipo_extrato == "cartao" and not cartao_id:
            info_cartao = self._obter_ou_criar_cartao_importado(
                caminho=caminho,
                formato=os.path.splitext(caminho)[1].lower(),
            )
            cartao_id = info_cartao["cartao_id"]

        df = pd.read_excel(caminho, sheet_name=aba or 0)

        # Detecta formato específico de cartão de crédito
        if tipo_extrato == "cartao" or cartao_id:
            transacoes_brutas = self._parsear_csv_cartao(df)
        else:
            mapeamento = mapeamento or self._detectar_mapeamento_csv(df.columns.tolist())
            transacoes_brutas = self._df_para_transacoes(df, mapeamento)

        resultado = self._salvar_transacoes(
            transacoes_brutas,
            arquivo_nome=os.path.basename(caminho),
            arquivo_path=caminho,
            tipo="cartao" if tipo_extrato == "cartao" else "excel",
            conta_id=conta_id,
            cartao_id=cartao_id,
        )
        resultado["cartao_criado"] = info_cartao.get("cartao_criado", False)
        return resultado

    # ================================================
    # Importação de OFX
    # ================================================

    def importar_ofx(
        self,
        caminho: str,
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
        tipo_extrato: str = "bancario",
    ) -> Dict[str, Any]:
        """
        Importa um extrato no formato OFX (Open Financial Exchange).
        Padrão usado por muitos bancos para exportação de extratos.

        Args:
            caminho:   Caminho do arquivo OFX
            conta_id:  ID da conta (opcional)
            cartao_id: ID do cartão (opcional)
        """
        from ofxparse import OfxParser

        logger.info(f"Importando OFX: {caminho}")
        info_cartao = {"cartao_criado": False}

        if tipo_extrato == "cartao" and not cartao_id:
            info_cartao = self._obter_ou_criar_cartao_importado(
                caminho=caminho,
                formato=os.path.splitext(caminho)[1].lower(),
            )
            cartao_id = info_cartao["cartao_id"]

        with open(caminho, "rb") as f:
            ofx = OfxParser.parse(f)

        transacoes_brutas = []
        for conta in ofx.accounts:
            banco = getattr(conta, "institution", None)
            banco = getattr(banco, "organization", None) if banco else None

            for stmt in (conta.statement.transactions if hasattr(conta, "statement") else []):
                valor  = float(stmt.amount)
                tipo   = "credito" if valor > 0 else "debito"
                transacoes_brutas.append({
                    "data":      stmt.date.date() if hasattr(stmt.date, "date") else stmt.date,
                    "descricao": stmt.memo or stmt.payee or "Transação OFX",
                    "valor":     abs(valor),
                    "tipo":      tipo,
                    "fonte":     banco or "OFX",
                })

        resultado = self._salvar_transacoes(
            transacoes_brutas,
            arquivo_nome=os.path.basename(caminho),
            arquivo_path=caminho,
            tipo="ofx",
            conta_id=conta_id,
            cartao_id=cartao_id,
        )
        resultado["cartao_criado"] = info_cartao.get("cartao_criado", False)
        return resultado

    # --------------------------------------------------
    # Persistência e helpers internos
    # --------------------------------------------------

    def _salvar_transacoes(
        self,
        transacoes_brutas: List[Dict],
        arquivo_nome: str,
        arquivo_path: str,
        tipo: str,
        banco: Optional[str] = None,
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Classifica e persiste a lista de transações brutas no banco.

        Returns:
            Resumo com total importado, ignorado e ID do extrato
        """
        transacoes_consumo, referencias_visuais, ignoradas_movimento = self._filtrar_transacoes_para_consumo(
            transacoes_brutas,
            tipo_extrato=tipo,
        )

        transacoes_brutas = transacoes_consumo
        if not transacoes_brutas:
            resultado_vazio = {
                "importadas": 0,
                "ignoradas": ignoradas_movimento,
                "extrato_id": None,
                "erro": "Nenhuma transação de consumo real encontrada",
                "referencias_visuais": referencias_visuais,
            }
            return self._anexar_info_cartao_resultado(resultado_vazio, cartao_id=cartao_id)

        datas = [t["data"] for t in transacoes_brutas if t.get("data")]
        periodo_inicio = min(datas) if datas else None
        periodo_fim = max(datas) if datas else None

        def _resumo_duplicado(extrato: Extrato) -> Dict[str, Any]:
            resultado = {
                "importadas": 0,
                "ignoradas": ignoradas_movimento,
                "extrato_id": extrato.id,
                "arquivo": arquivo_nome,
                "duplicado": True,
                "importado_em": extrato.importado_em.strftime("%d/%m/%Y %H:%M") if extrato.importado_em else "—",
                "total_anterior": extrato.total_transacoes or 0,
                "referencias_visuais": referencias_visuais,
            }
            return self._anexar_info_cartao_resultado(resultado, cartao_id=extrato.cartao_id)

        # Duplicidade: caminho idêntico (mesmo arquivo físico)
        extrato_por_path = self.db.query(Extrato).filter(
            Extrato.arquivo_path == arquivo_path
        ).first()
        if extrato_por_path:
            logger.warning(
                "Arquivo '%s' já importado pelo mesmo caminho (Extrato ID=%s). Ignorando.",
                arquivo_nome,
                extrato_por_path.id,
            )
            return _resumo_duplicado(extrato_por_path)

        # Duplicidade por assinatura do extrato (evita bloquear só por nome)
        q_assinatura = self.db.query(Extrato).filter(
            Extrato.arquivo_nome == arquivo_nome,
            Extrato.tipo == tipo,
            Extrato.periodo_inicio == periodo_inicio,
            Extrato.periodo_fim == periodo_fim,
            Extrato.total_transacoes == len(transacoes_brutas),
        )
        if conta_id is None:
            q_assinatura = q_assinatura.filter(Extrato.conta_id.is_(None))
        else:
            q_assinatura = q_assinatura.filter(Extrato.conta_id == conta_id)

        if cartao_id is None:
            q_assinatura = q_assinatura.filter(Extrato.cartao_id.is_(None))
        else:
            q_assinatura = q_assinatura.filter(Extrato.cartao_id == cartao_id)

        if banco is None:
            q_assinatura = q_assinatura.filter(Extrato.banco.is_(None))
        else:
            q_assinatura = q_assinatura.filter(Extrato.banco == banco)

        extrato_assinatura = q_assinatura.first()
        if extrato_assinatura:
            logger.warning(
                "Arquivo '%s' já importado com mesma assinatura (Extrato ID=%s). Ignorando.",
                arquivo_nome,
                extrato_assinatura.id,
            )
            return _resumo_duplicado(extrato_assinatura)

        # Se for fatura de cartão, sobrepõe todas as datas pelo dia de vencimento
        data_vencimento: Optional[date] = None
        if tipo == "cartao" and cartao_id:
            from app.models import CartaoCredito as _CartaoCredito
            cartao_obj = self.db.query(_CartaoCredito).filter(_CartaoCredito.id == cartao_id).first()
            if cartao_obj and cartao_obj.dia_vencimento:
                datas_raw = [t["data"] for t in transacoes_brutas if t.get("data")]
                if datas_raw:
                    ref = max(datas_raw)
                    # Vencimento no mesmo mês se dia ainda não passou, senão no mês seguinte
                    if ref.day < cartao_obj.dia_vencimento:
                        mes_v, ano_v = ref.month, ref.year
                    else:
                        if ref.month == 12:
                            mes_v, ano_v = 1, ref.year + 1
                        else:
                            mes_v, ano_v = ref.month + 1, ref.year
                    ultimo_dia = calendar.monthrange(ano_v, mes_v)[1]
                    dia_v = min(cartao_obj.dia_vencimento, ultimo_dia)
                    data_vencimento = date(ano_v, mes_v, dia_v)
                    logger.info(f"Fatura de cartão: data de vencimento calculada = {data_vencimento}")

        # Cria registro de extrato
        extrato = Extrato(
            arquivo_nome=arquivo_nome,
            arquivo_path=arquivo_path,
            tipo=tipo,
            banco=banco,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            total_transacoes=len(transacoes_brutas),
            conta_id=conta_id,
            cartao_id=cartao_id,
        )
        self.db.add(extrato)
        self.db.flush()

        importadas = 0
        ignoradas  = ignoradas_movimento

        for bruta in transacoes_brutas:
            try:
                if not bruta.get("data") or bruta.get("valor") is None:
                    ignoradas += 1
                    continue

                # Regra de negócio: toda compra da fatura de cartão vira despesa
                # na data de pagamento (vencimento) da fatura.
                data_lancamento = data_vencimento if (tipo == "cartao" and data_vencimento) else bruta["data"]
                tipo_lancamento = "debito" if tipo == "cartao" else bruta.get("tipo", "debito")

                t = Transacao(
                    data           = data_lancamento,
                    descricao      = bruta.get("descricao", "Sem descrição"),
                    valor          = abs(float(bruta["valor"])),
                    tipo           = tipo_lancamento,
                    parcela_atual  = bruta.get("parcela_atual"),
                    parcelas_total = bruta.get("parcelas_total"),
                    fonte          = bruta.get("fonte", banco),
                    arquivo_origem = arquivo_nome,
                    conta_id       = conta_id,
                    cartao_id      = cartao_id,
                    extrato_id     = extrato.id,
                )

                # Classifica automaticamente
                self.classifier.classificar_e_aplicar(t)

                self.db.add(t)
                importadas += 1

            except Exception as e:
                logger.warning(f"Erro ao processar transação: {e} | dados: {bruta}")
                ignoradas += 1

        extrato.total_transacoes = importadas
        self.db.commit()

        logger.info(f"Importação concluída: {importadas} transações | {ignoradas} ignoradas")
        resultado = {
            "importadas":  importadas,
            "ignoradas":   ignoradas,
            "extrato_id":  extrato.id,
            "arquivo":     arquivo_nome,
            "referencias_visuais": referencias_visuais,
        }
        return self._anexar_info_cartao_resultado(resultado, cartao_id=cartao_id)

    # ================================================
    # Importação de fatura de cartão de crédito
    # ================================================

    def importar_fatura_cartao(
        self,
        caminho: str,
        cartao_id: Optional[int] = None,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Importa fatura de cartão de crédito a partir de CSV/Excel/PDF/OFX.
        Auto-detecta o formato do banco (Nubank, Inter, C6, XP, Itaú, etc.).

        Args:
            caminho:   Caminho do arquivo
            cartao_id: ID do cartão no banco (opcional)
            separador: Separador CSV (padrão ",")
            encoding:  Encoding do arquivo (padrão "utf-8")

        Returns:
            Resumo da importação
        """
        ext = os.path.splitext(caminho)[1].lower()

        if ext == ".pdf":
            return self.importar_pdf(
                caminho,
                tipo_extrato="cartao",
                cartao_id=cartao_id,
                senha=senha,
            )

        if ext in (".ofx", ".qfx"):
            return self.importar_ofx(caminho, cartao_id=cartao_id, tipo_extrato="cartao")

        if ext in (".xlsx", ".xls"):
            return self.importar_excel(caminho, cartao_id=cartao_id, tipo_extrato="cartao")

        return self.importar_csv(
            caminho,
            cartao_id=cartao_id,
            separador=separador,
            encoding=encoding,
            tipo_extrato="cartao",
        )

    def previsualizar_fatura_cartao(
        self,
        caminho: str,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Realiza a primeira leitura da fatura sem salvar no banco.
        Retorna transações de consumo para revisão manual na UI.
        """
        transacoes_brutas, banco = self._coletar_transacoes_fatura_cartao(
            caminho=caminho,
            separador=separador,
            encoding=encoding,
            senha=senha,
        )
        consumo, referencias_visuais, ignoradas = self._filtrar_transacoes_para_consumo(
            transacoes_brutas,
            tipo_extrato="cartao",
        )

        transacoes = []
        for item in consumo:
            data_item = item.get("data")
            if hasattr(data_item, "strftime"):
                data_item = data_item.strftime("%Y-%m-%d")
            transacoes.append({
                "data": data_item,
                "descricao": item.get("descricao") or "",
                "valor": float(item.get("valor") or 0.0),
                "tipo": str(item.get("tipo") or "debito").lower(),
                "parcela_atual": item.get("parcela_atual"),
                "parcelas_total": item.get("parcelas_total"),
            })

        return {
            "arquivo": os.path.basename(caminho),
            "banco": banco,
            "transacoes": transacoes,
            "qtd_lidas": len(transacoes_brutas or []),
            "qtd_previa": len(transacoes),
            "qtd_ignoradas": ignoradas,
            "qtd_estornos": len(referencias_visuais),
        }

    def salvar_fatura_cartao_previa(
        self,
        caminho: str,
        transacoes_editadas: List[Dict[str, Any]],
        cartao_id: Optional[int] = None,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Salva no banco a prévia editada pelo usuário após confirmação explícita.
        """
        if not transacoes_editadas:
            raise ValueError("Nenhuma transação informada para salvar.")

        ext = os.path.splitext(caminho)[1].lower()
        info_cartao = {"cartao_criado": False}
        if not cartao_id:
            info_cartao = self._obter_ou_criar_cartao_importado(
                caminho=caminho,
                formato=ext,
                separador=separador,
                encoding=encoding,
                senha=senha,
            )
            cartao_id = info_cartao.get("cartao_id")

        _, banco = self._coletar_transacoes_fatura_cartao(
            caminho=caminho,
            separador=separador,
            encoding=encoding,
            senha=senha,
        )

        normalizadas: List[Dict[str, Any]] = []
        for item in transacoes_editadas:
            data_raw = item.get("data")
            data_obj = data_raw if isinstance(data_raw, date) else parsear_data_br(str(data_raw or ""))
            if not data_obj:
                raise ValueError(f"Data inválida na prévia: {data_raw}")

            valor_raw = item.get("valor")
            if isinstance(valor_raw, str):
                valor_obj = converter_valor_br(valor_raw)
            else:
                try:
                    valor_obj = float(valor_raw)
                except Exception:
                    valor_obj = None

            if valor_obj is None:
                raise ValueError(f"Valor inválido na prévia: {valor_raw}")

            normalizadas.append({
                "data": data_obj,
                "descricao": (item.get("descricao") or "Sem descrição").strip(),
                "valor": abs(float(valor_obj)),
                "tipo": str(item.get("tipo") or "debito").lower(),
                "parcela_atual": item.get("parcela_atual"),
                "parcelas_total": item.get("parcelas_total"),
                "fonte": banco or "Cartão",
            })

        resultado = self._salvar_transacoes(
            normalizadas,
            arquivo_nome=os.path.basename(caminho),
            arquivo_path=caminho,
            tipo="cartao",
            banco=banco,
            cartao_id=cartao_id,
        )
        resultado["cartao_criado"] = info_cartao.get("cartao_criado", False)
        return resultado

    def _coletar_transacoes_fatura_cartao(
        self,
        caminho: str,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Coleta transações de fatura sem persistência, independente do formato."""
        ext = os.path.splitext(caminho)[1].lower()

        if ext == ".pdf":
            texto = self.ocr.extrair_texto_pdf(caminho, senha=senha)
            banco = self.ocr.detectar_banco(texto)
            transacoes = self.parser.parsear_texto(texto, banco=banco, tipo_extrato="cartao")
            return transacoes, banco

        if ext in (".csv", ".xlsx", ".xls"):
            import pandas as pd

            if ext == ".csv":
                df = None
                for enc in [encoding, "latin-1", "utf-8-sig"]:
                    try:
                        df = pd.read_csv(caminho, sep=separador, encoding=enc)
                        break
                    except Exception:
                        continue
                if df is None:
                    raise ValueError(f"Não foi possível ler o arquivo CSV: {caminho}")
            else:
                df = pd.read_excel(caminho, sheet_name=0)

            cols = [str(c).strip().lower() for c in df.columns]
            banco_key = self._detectar_banco_csv_cartao(cols, df)
            banco = BANCO_CARTAO_LABELS.get(banco_key, "Cartão Importado")
            transacoes = self._parsear_csv_cartao(df)
            return transacoes, banco

        if ext in (".ofx", ".qfx"):
            from ofxparse import OfxParser

            with open(caminho, "rb") as f:
                ofx = OfxParser.parse(f)

            transacoes: List[Dict[str, Any]] = []
            banco = None
            for conta in ofx.accounts:
                instituicao = getattr(conta, "institution", None)
                banco_local = getattr(instituicao, "organization", None) if instituicao else None
                if banco_local and not banco:
                    banco = banco_local

                for stmt in (conta.statement.transactions if hasattr(conta, "statement") else []):
                    valor = float(stmt.amount)
                    tipo = "credito" if valor > 0 else "debito"
                    transacoes.append({
                        "data": stmt.date.date() if hasattr(stmt.date, "date") else stmt.date,
                        "descricao": stmt.memo or stmt.payee or "Transação OFX",
                        "valor": abs(valor),
                        "tipo": tipo,
                        "fonte": banco_local or "OFX",
                    })

            return transacoes, banco

        raise ValueError(f"Formato '{ext}' não suportado para fatura de cartão.")

    def _obter_ou_criar_cartao_importado(
        self,
        caminho: str,
        formato: str,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        metadados = self._inferir_metadados_cartao_importado(
            caminho=caminho,
            formato=formato,
            separador=separador,
            encoding=encoding,
            senha=senha,
        )

        nome_base = metadados["nome_base"]
        bandeira = metadados["bandeira"]
        identificador = metadados["identificador"]
        dia_fechamento = metadados["dia_fechamento"]
        dia_vencimento = metadados["dia_vencimento"]

        cartoes = self.db.query(CartaoCredito).all()
        nome = self._montar_nome_cartao_importado(
            nome_base=nome_base,
            bandeira=bandeira,
            dia_fechamento=dia_fechamento,
            dia_vencimento=dia_vencimento,
            identificador=identificador,
            cartoes_existentes=cartoes,
        )
        nome_norm = nome.casefold()
        nome_base_norm = nome_base.casefold()
        bandeira_norm = bandeira.casefold()

        for cartao in cartoes:
            if cartao.nome.strip().casefold() == nome_norm and cartao.bandeira.strip().casefold() == bandeira_norm:
                self._atualizar_cartao_importado(
                    cartao,
                    bandeira=bandeira,
                    dia_fechamento=dia_fechamento,
                    dia_vencimento=dia_vencimento,
                )
                return self._anexar_info_cartao_resultado({"cartao_criado": False}, cartao.id)

        for cartao in cartoes:
            nome_existente = cartao.nome.strip().casefold()
            if nome_existente == nome_base_norm or nome_existente.startswith(f"{nome_base_norm} "):
                if cartao.bandeira.strip().casefold() != bandeira_norm:
                    continue
                if dia_vencimento and cartao.dia_vencimento and cartao.dia_vencimento != dia_vencimento:
                    continue
                if dia_fechamento and cartao.dia_fechamento and cartao.dia_fechamento != dia_fechamento:
                    continue
                self._atualizar_cartao_importado(
                    cartao,
                    bandeira=bandeira,
                    dia_fechamento=dia_fechamento,
                    dia_vencimento=dia_vencimento,
                )
                return self._anexar_info_cartao_resultado({"cartao_criado": False}, cartao.id)

        cartao = CartaoCredito(
            nome=nome,
            bandeira=bandeira,
            limite=0.0,
            limite_disponivel=0.0,
            dia_fechamento=dia_fechamento or 1,
            dia_vencimento=dia_vencimento or 10,
            ativo=True,
        )
        self.db.add(cartao)
        self.db.flush()

        logger.info("Cartão criado automaticamente: %s (%s)", cartao.nome, cartao.bandeira)
        return self._anexar_info_cartao_resultado({"cartao_criado": True}, cartao.id)

    def _atualizar_cartao_importado(
        self,
        cartao: CartaoCredito,
        bandeira: str,
        dia_fechamento: Optional[int],
        dia_vencimento: Optional[int],
    ) -> None:
        alterado = False

        if not cartao.ativo:
            cartao.ativo = True
            alterado = True

        if bandeira and bandeira != "Outros" and (not cartao.bandeira or cartao.bandeira == "Outros"):
            cartao.bandeira = bandeira
            alterado = True

        if dia_fechamento and (not cartao.dia_fechamento or cartao.dia_fechamento == 1):
            cartao.dia_fechamento = dia_fechamento
            alterado = True

        if dia_vencimento and (not cartao.dia_vencimento or cartao.dia_vencimento == 10):
            cartao.dia_vencimento = dia_vencimento
            alterado = True

        if alterado:
            self.db.flush()

    def _anexar_info_cartao_resultado(
        self,
        resultado: Dict[str, Any],
        cartao_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not cartao_id:
            return resultado

        cartao = self.db.get(CartaoCredito, cartao_id)
        resultado["cartao_id"] = cartao_id
        if cartao:
            resultado["cartao_nome"] = cartao.nome
            resultado["cartao_bandeira"] = cartao.bandeira
            resultado["cartao_dia_fechamento"] = cartao.dia_fechamento
            resultado["cartao_dia_vencimento"] = cartao.dia_vencimento
        return resultado

    def _inferir_metadados_cartao_importado(
        self,
        caminho: str,
        formato: str,
        separador: str = ",",
        encoding: str = "utf-8",
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        texto = ""
        banco = None

        if formato == ".pdf":
            texto = self.ocr.extrair_texto_pdf(caminho, senha=senha)
            banco = self.ocr.detectar_banco(texto)
        elif formato in (".csv", ".xlsx", ".xls"):
            import pandas as pd

            if formato == ".csv":
                for enc in [encoding, "latin-1", "utf-8-sig"]:
                    try:
                        df = pd.read_csv(caminho, sep=separador, encoding=enc)
                        break
                    except Exception:
                        df = None
                if df is None:
                    raise ValueError(f"Não foi possível ler o arquivo CSV: {caminho}")
            else:
                df = pd.read_excel(caminho, sheet_name=0)

            cols = [str(c).strip().lower() for c in df.columns]
            banco = BANCO_CARTAO_LABELS.get(self._detectar_banco_csv_cartao(cols, df), "Cartão Importado")
            texto = " ".join(str(c) for c in df.columns)
            try:
                amostra = df.head(5).fillna("").astype(str)
                texto += "\n" + "\n".join(" ".join(linha) for linha in amostra.values.tolist())
            except Exception:
                pass
        elif formato in (".ofx", ".qfx"):
            texto = self.ocr.extrair_texto_txt(caminho)
            banco = self.ocr.detectar_banco(texto)

        banco = banco or self.ocr.detectar_banco(texto or "") or self._nome_cartao_por_arquivo(caminho)
        return {
            "nome_base": banco,
            "bandeira": self._detectar_bandeira_cartao(texto),
            "identificador": self._detectar_identificador_cartao(texto, caminho),
            "dia_fechamento": self._detectar_dia_fechamento_cartao(texto),
            "dia_vencimento": self._detectar_dia_vencimento_cartao(texto),
        }

    def _montar_nome_cartao_importado(
        self,
        nome_base: str,
        bandeira: str,
        dia_fechamento: Optional[int],
        dia_vencimento: Optional[int],
        identificador: Optional[str],
        cartoes_existentes: List[CartaoCredito],
    ) -> str:
        nome_base = (nome_base or "Cartão Importado").strip()
        nomes_existentes = {c.nome.strip().casefold() for c in cartoes_existentes}
        if nome_base.casefold() not in nomes_existentes:
            return nome_base

        partes = []
        if bandeira and bandeira != "Outros" and bandeira.casefold() not in nome_base.casefold():
            partes.append(bandeira)
        if identificador:
            partes.append(f"final {identificador}")
        if dia_fechamento:
            partes.append(f"fecha {dia_fechamento:02d}")
        if dia_vencimento:
            partes.append(f"vence {dia_vencimento:02d}")

        candidato = nome_base if not partes else f"{nome_base} {' '.join(partes)}"
        if candidato.casefold() not in nomes_existentes:
            return candidato

        idx = 2
        while f"{candidato} {idx}".casefold() in nomes_existentes:
            idx += 1
        return f"{candidato} {idx}"

    def _detectar_bandeira_cartao(self, texto: str) -> str:
        texto_lower = (texto or "").lower()
        bandeiras = [
            ("mastercard", "Mastercard"),
            ("master card", "Mastercard"),
            ("visa", "Visa"),
            ("elo", "Elo"),
            ("american express", "Amex"),
            ("amex", "Amex"),
            ("hipercard", "Hipercard"),
        ]
        for termo, nome in bandeiras:
            if termo in texto_lower:
                return nome
        return "Outros"

    def _detectar_identificador_cartao(self, texto: str, caminho: str) -> Optional[str]:
        texto = texto or ""
        padroes = [
            r"(?:final|terminad[oa]\s+em|ultimos?\s+4\s+d[ií]gitos|[uú]ltimos?\s+4\s+d[ií]gitos)\D*(\d{4})",
            r"\*{4}\s*(\d{4})",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return m.group(1)

        stem = os.path.splitext(os.path.basename(caminho))[0]
        m_stem = re.search(r"(\d{4})", stem)
        if m_stem:
            return m_stem.group(1)
        return None

    def _detectar_dia_fechamento_cartao(self, texto: str) -> Optional[int]:
        if not texto:
            return None

        padroes = [
            r"(?:data\s+de\s+fechamento|fechamento(?:\s+da\s+fatura)?|fecha\s+em)\s*[:\-]?\s*(\d{1,2})/(\d{1,2})/(\d{2,4})",
            r"(?:data\s+de\s+fechamento|fechamento(?:\s+da\s+fatura)?)\s*[:\-]?\s*(\d{1,2})\s+de\s+\w+",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    def _detectar_dia_vencimento_cartao(self, texto: str) -> Optional[int]:
        if not texto:
            return None

        padroes = [
            r"(?:vence\s+em|vencimento(?:\s+da\s+fatura)?|data\s+de\s+vencimento)\s*[:\-]?\s*(\d{2})/(\d{2})/(\d{4})",
            r"vencimento\s*[:\-]?\s*(\d{1,2})\s+de\s+\w+",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    def _nome_cartao_por_arquivo(self, caminho: str) -> str:
        nome = os.path.splitext(os.path.basename(caminho))[0]
        nome = re.sub(r"[_\-]+", " ", nome).strip()
        return nome.title() or "Cartão Importado"

    def _parsear_csv_cartao(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Identifica o formato de fatura do cartão e converte para transações brutas.
        Suporta: Nubank, Inter, C6, XP/BTG, Itaú, Bradesco, Santander, genérico.
        """
        cols = [str(c).strip().lower() for c in df.columns]
        banco = self._detectar_banco_csv_cartao(cols, df)
        logger.info(f"Formato de cartão detectado: {banco}")

        if banco == "nubank":
            return self._parse_nubank_csv(df)
        if banco == "inter":
            return self._parse_inter_csv(df)
        if banco == "c6":
            return self._parse_c6_csv(df)
        if banco == "xp":
            return self._parse_xp_csv(df)
        if banco == "itau":
            return self._parse_itau_csv(df)

        # Fallback: mapeamento automático genérico
        mapeamento = self._detectar_mapeamento_csv(df.columns.tolist())
        return self._df_para_transacoes(df, mapeamento)

    # ================================================
    # Análise e importação unificada de documentos
    # ================================================

    # Extensões aceitas pelo fluxo de documento único
    EXTENSOES_DOCUMENTO = {
        ".pdf", ".jpg", ".jpeg", ".png", ".bmp",
        ".tiff", ".tif", ".webp", ".docx", ".doc", ".txt",
    }

    def analisar_documento(self, caminho: str, senha: Optional[str] = None) -> Dict[str, Any]:
        """
        Extrai texto do arquivo e classifica automaticamente o tipo de documento.

        Este método NÃO salva nada no banco. É usado para apresentar ao usuário
        o tipo detectado antes de confirmar a importação.

        Args:
            caminho: Caminho do arquivo (PDF/imagem/DOCX/TXT)

        Returns:
            Dicionário com:
              - arquivo_nome: str
              - extensao:     str
              - tipo_detectado: chave de tipo (ex. "extrato_bancario")
              - nome_tipo:    nome legível do tipo
              - emoji_tipo:   emoji do tipo
              - confianca:    "alta" | "media" | "baixa"
              - texto_preview: primeiros 600 caracteres do texto extraído
              - texto_completo: texto completo para uso posterior
        """
        ext = os.path.splitext(caminho)[1].lower()
        if ext not in self.EXTENSOES_DOCUMENTO:
            raise ValueError(
                f"Formato '{ext}' não suportado. "
                f"Use: {', '.join(sorted(self.EXTENSOES_DOCUMENTO))}"
            )

        logger.info(f"Analisando documento: {caminho}")
        texto = self.ocr.extrair_texto(caminho, senha=senha)

        classificacao = self.classifier.classificar_tipo_documento(texto)
        pre_lancamento = self.montar_previa_documento(
            texto=texto,
            tipo_documento=classificacao["tipo"],
        )

        return {
            "arquivo_nome":   os.path.basename(caminho),
            "extensao":       ext,
            "tipo_detectado": classificacao["tipo"],
            "nome_tipo":      classificacao["nome"],
            "emoji_tipo":     classificacao["emoji"],
            "confianca":      classificacao["confianca"],
            "texto_preview":  texto[:1500].strip(),
            "texto_completo": texto,
            "pre_lancamento": pre_lancamento,
        }

    def registrar_feedback_tipo_documento(
        self,
        texto: str,
        tipo_confirmado: str,
        tipo_detectado: Optional[str] = None,
    ) -> None:
        """Registra aprendizado de tipo de documento a partir da confirmação do usuário."""
        if not texto or not tipo_confirmado or tipo_confirmado == "desconhecido":
            return

        self.classifier.registrar_feedback_tipo_documento(texto, tipo_confirmado)

        if tipo_detectado and tipo_detectado != tipo_confirmado:
            logger.info(
                "Aprendizado aplicado: tipo detectado '%s' corrigido para '%s'.",
                tipo_detectado,
                tipo_confirmado,
            )

    def montar_previa_documento(self, texto: str, tipo_documento: str) -> Dict[str, Any]:
        """Monta um resumo objetivo da leitura para confirmação do usuário."""
        previa: Dict[str, Any] = {
            "tipo_documento": tipo_documento,
            "tipo_movimento": None,
            "valor": None,
            "descricao": None,
            "categoria_sugerida": None,
            "vencimento": None,
            "qtd_transacoes": None,
            "amostra_transacoes": [],
        }

        if tipo_documento in ("extrato_bancario", "extrato_cartao"):
            tipo_extrato = "cartao" if tipo_documento == "extrato_cartao" else "bancario"
            banco = self.ocr.detectar_banco(texto) if tipo_extrato == "bancario" else None
            transacoes_lidas = self.parser.parsear_texto(
                texto,
                banco=banco,
                tipo_extrato=tipo_extrato,
            )
            transacoes, referencias_visuais, ignoradas = self._filtrar_transacoes_para_consumo(
                transacoes_lidas,
                tipo_extrato=tipo_extrato,
            )
            previa["qtd_transacoes"] = len(transacoes)
            previa["qtd_ignoradas"] = ignoradas
            previa["qtd_estornos"] = len(referencias_visuais)
            def _cat_item(desc: str) -> str:
                try:
                    return (self.classifier.sugestoes(desc or "", n=1) or ["Outros"])[0]
                except Exception:
                    return "Outros"

            previa["amostra_transacoes"] = [
                {
                    "data": str(item.get("data") or ""),
                    "descricao": item.get("descricao"),
                    "valor": item.get("valor"),
                    "tipo": item.get("tipo"),
                    "referencia_visual": False,
                    "categoria_sugerida": _cat_item(item.get("descricao") or ""),
                }
                for item in transacoes[:5]
            ]
            previa["amostra_estornos"] = [
                {
                    "data": str(item.get("data") or ""),
                    "descricao": item.get("descricao"),
                    "valor": item.get("valor"),
                    "tipo": item.get("tipo"),
                    "referencia_visual": True,
                }
                for item in referencias_visuais[:3]
            ]
            if transacoes:
                primeira = transacoes[0]
                previa["valor"] = primeira.get("valor")
                previa["descricao"] = primeira.get("descricao")
                previa["tipo_movimento"] = primeira.get("tipo")
                previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                    descricao=previa.get("descricao"),
                    valor=previa.get("valor"),
                    tipo_movimento=previa.get("tipo_movimento"),
                )
            return previa

        valor = self._extrair_valor_documento(texto, tipo_documento=tipo_documento)
        previa["valor"] = valor

        if tipo_documento == "comprovante_pagamento_bancario":
            previa["descricao"] = self._extrair_descricao_comprovante_bancario(texto)
            previa["tipo_movimento"] = self._inferir_tipo_comprovante_bancario(texto)
            previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                descricao=previa.get("descricao"),
                valor=previa.get("valor"),
                tipo_movimento=previa.get("tipo_movimento"),
            )
            return previa

        if tipo_documento == "recibo_despesa":
            previa["descricao"] = (
                self._extrair_descricao_recibo(texto)
                or self._extrair_descricao_documento(texto)
            )
            previa["tipo_movimento"] = "debito"
            previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                descricao=previa.get("descricao"),
                valor=previa.get("valor"),
                tipo_movimento=previa.get("tipo_movimento"),
            )
            return previa

        if tipo_documento == "nota_fiscal":
            previa["descricao"] = self._extrair_descricao_nota_fiscal(texto)
            previa["tipo_movimento"] = "debito"
            previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                descricao=previa.get("descricao"),
                valor=previa.get("valor"),
                tipo_movimento=previa.get("tipo_movimento"),
                texto_contexto=texto,
            )
            return previa

        if tipo_documento == "comprovante_compra":
            previa["descricao"] = self._extrair_estabelecimento_comprovante(texto)
            previa["tipo_movimento"] = "debito"
            previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                descricao=previa.get("descricao"),
                valor=previa.get("valor"),
                tipo_movimento=previa.get("tipo_movimento"),
            )
            return previa

        if tipo_documento == "boleto":
            previa["descricao"] = self._extrair_beneficiario_boleto(texto)
            previa["vencimento"] = self._extrair_vencimento_boleto(texto)
            previa["tipo_movimento"] = "evento_pendente"
            previa["categoria_sugerida"] = self._sugerir_categoria_documento(
                descricao=previa.get("descricao"),
                valor=previa.get("valor"),
                tipo_movimento="debito",
            )
            return previa

        return previa

    def _sugerir_categoria_documento(
        self,
        descricao: Optional[str],
        valor: Optional[float],
        tipo_movimento: Optional[str],
        texto_contexto: Optional[str] = None,
    ) -> Optional[str]:
        """Sugere categoria para a prévia sem persistir nenhuma transação."""
        descricao_base = str(descricao or "").strip()
        texto_base = str(texto_contexto or "").strip()

        if not descricao_base and not texto_base:
            return None

        try:
            tipo = "credito" if str(tipo_movimento or "").lower() == "credito" else "debito"
            transacao_preview = Transacao(
                data=date.today(),
                descricao=descricao_base or texto_base[:120],
                valor=abs(float(valor or 0.0)),
                tipo=tipo,
                fonte="preview_documento",
            )
            categoria = self.classifier.classificar_e_aplicar(transacao_preview)
            if categoria and getattr(categoria, "nome", None):
                return categoria.nome
            if getattr(transacao_preview, "categoria", None) and getattr(transacao_preview.categoria, "nome", None):
                return transacao_preview.categoria.nome

            sugestoes = self.classifier.sugestoes(
                " ".join(parte for parte in (descricao_base, texto_base) if parte),
                n=1,
            )
            if sugestoes:
                return sugestoes[0]
        except Exception as exc:
            logger.debug("Falha ao sugerir categoria da prévia: %s", exc)

        return None

    def _filtrar_transacoes_para_consumo(
        self,
        transacoes_brutas: List[Dict[str, Any]],
        tipo_extrato: str,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        consumo: List[Dict[str, Any]] = []
        referencias_visuais: List[Dict[str, Any]] = []
        ignoradas = 0

        for transacao in transacoes_brutas or []:
            classe = self._classificar_movimento_para_analise(transacao, tipo_extrato)
            item = dict(transacao)
            item["classe_movimento"] = classe
            item["referencia_token"] = self._token_referencia_visual(item)

            if classe == "consumo":
                consumo.append(item)
                continue
            if classe == "estorno":
                item["referencia_visual"] = True
                referencias_visuais.append(item)
                ignoradas += 1
                continue
            ignoradas += 1

        return consumo, self._vincular_estornos_a_consumo(consumo, referencias_visuais), ignoradas

    def _classificar_movimento_para_analise(self, transacao: Dict[str, Any], tipo_extrato: str) -> str:
        descricao = normalizar_descricao(transacao.get("descricao") or "")
        tipo_movimento = str(transacao.get("tipo") or "debito").lower()
        valor = transacao.get("valor")

        if valor is None:
            return "ignorar"

        if any(chave in descricao for chave in KEYWORDS_ESTORNO_REFERENCIA):
            return "estorno"

        if any(chave in descricao for chave in KEYWORDS_MOVIMENTO_NAO_CONSUMO):
            return "ignorar"

        if tipo_movimento == "credito":
            return "estorno" if tipo_extrato == "cartao" else "ignorar"

        return "consumo"

    def _vincular_estornos_a_consumo(
        self,
        consumo: List[Dict[str, Any]],
        referencias_visuais: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        for referencia in referencias_visuais:
            token_ref = referencia.get("referencia_token")
            correspondencia = next(
                (
                    item for item in consumo
                    if item.get("referencia_token") == token_ref
                ),
                None,
            )
            if correspondencia:
                referencia["referencia_token"] = correspondencia.get("referencia_token")
        return referencias_visuais

    def _token_referencia_visual(self, transacao: Dict[str, Any]) -> str:
        descricao = normalizar_descricao(transacao.get("descricao") or "")
        try:
            valor = abs(float(transacao.get("valor") or 0.0))
        except Exception:
            valor = 0.0
        return f"{descricao}|{valor:.2f}"

    def importar_por_tipo_documento(
        self,
        caminho: str,
        tipo_documento: str,
        conta_id:  Optional[int] = None,
        cartao_id: Optional[int] = None,
        descricao_manual: Optional[str] = None,
        senha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Importa o arquivo conforme o tipo de documento confirmado pelo usuário.

        Roteamento:
          - extrato_bancario   → importar_pdf / csv / excel / ofx (tipo bancario)
          - extrato_cartao     → importar_fatura_cartao
          - comprovante_pagamento_bancario → cria Transacao bancária única (PIX/TED/DOC)
          - nota_fiscal        → cria Transacao de débito + EventoFinanceiro opcional
          - boleto             → cria EventoFinanceiro (a pagar)
          - comprovante_compra → cria Transacao de débito vinculada ao cartão

        Args:
            caminho:          Caminho do arquivo
            tipo_documento:   Tipo confirmado pelo usuário
            conta_id:         ID da conta bancária (para extratos bancários)
            cartao_id:        ID do cartão (para extrato_cartao / comprovante_compra)
            descricao_manual: Descrição para lançamentos manuais (nota_fiscal, boleto)

        Returns:
            Resumo da importação
        """
        ext = os.path.splitext(caminho)[1].lower()

        # ── Extratos: roteamento para os importadores existentes ──────────
        if tipo_documento == "extrato_bancario":
            if ext == ".pdf":
                return self.importar_pdf(
                    caminho,
                    tipo_extrato="bancario",
                    conta_id=conta_id,
                    senha=senha,
                )
            elif ext == ".csv":
                return self.importar_csv(caminho, tipo_extrato="bancario", conta_id=conta_id)
            elif ext in (".xlsx", ".xls"):
                return self.importar_excel(caminho, tipo_extrato="bancario", conta_id=conta_id)
            elif ext in (".ofx", ".qfx"):
                return self.importar_ofx(caminho, conta_id=conta_id, tipo_extrato="bancario")
            else:
                # Imagem/DOCX/TXT → extrai texto e passa pelo parser
                texto = self.ocr.extrair_texto(caminho, senha=senha)
                banco = self.ocr.detectar_banco(texto)
                transacoes = self.parser.parsear_texto(texto, banco=banco, tipo_extrato="bancario")
                return self._salvar_transacoes(
                    transacoes,
                    arquivo_nome=os.path.basename(caminho),
                    arquivo_path=caminho,
                    tipo="bancario",
                    banco=banco,
                    conta_id=conta_id,
                )

        if tipo_documento == "extrato_cartao":
            return self.importar_fatura_cartao(caminho, cartao_id=cartao_id, senha=senha)

        if tipo_documento == "comprovante_pagamento_bancario":
            texto = self.ocr.extrair_texto(caminho, senha=senha)
            valor = self._extrair_valor_documento(texto, tipo_documento=tipo_documento) or 0.0
            desc  = (
                descricao_manual
                or self._extrair_descricao_comprovante_bancario(texto)
                or "Comprovante bancário"
            )
            tipo_mov = self._inferir_tipo_comprovante_bancario(texto)
            return self._criar_transacao_unica(
                descricao=desc,
                valor=valor,
                tipo=tipo_mov,
                fonte="comprovante_bancario",
                arquivo_nome=os.path.basename(caminho),
                arquivo_path=caminho,
                conta_id=conta_id,
                cartao_id=None,
            )

        if tipo_documento == "recibo_despesa":
            texto = self.ocr.extrair_texto(caminho, senha=senha)
            valor = self._extrair_valor_documento(texto, tipo_documento=tipo_documento) or 0.0
            desc  = (
                descricao_manual
                or self._extrair_descricao_recibo(texto)
                or self._extrair_descricao_documento(texto)
                or "Recibo"
            )
            return self._criar_transacao_unica(
                descricao=desc,
                valor=valor,
                tipo="debito",
                fonte="recibo",
                arquivo_nome=os.path.basename(caminho),
                arquivo_path=caminho,
                conta_id=conta_id,
                cartao_id=cartao_id,
            )

        # ── Nota Fiscal: extrai valor e cria transação de despesa ─────────
        if tipo_documento == "nota_fiscal":
            texto = self.ocr.extrair_texto(caminho, senha=senha)
            valor = self._extrair_valor_documento(texto, tipo_documento=tipo_documento)
            desc  = descricao_manual or self._extrair_descricao_documento(texto) or "Nota Fiscal"
            return self._criar_transacao_unica(
                descricao=desc,
                valor=valor or 0.0,
                tipo="debito",
                fonte="nota_fiscal",
                arquivo_nome=os.path.basename(caminho),
                arquivo_path=caminho,
                conta_id=conta_id,
                cartao_id=cartao_id,
            )

        # ── Boleto: extrai valor + vencimento e cria EventoFinanceiro ─────
        if tipo_documento == "boleto":
            texto       = self.ocr.extrair_texto(caminho, senha=senha)
            valor       = self._extrair_valor_documento(texto, tipo_documento=tipo_documento) or 0.0
            vencimento  = self._extrair_vencimento_boleto(texto) or date.today()
            cod_barras  = self._extrair_codigo_barras(texto)
            desc        = descricao_manual or self._extrair_beneficiario_boleto(texto) or "Boleto"
            ev = EventoFinanceiro(
                titulo          = desc,
                valor           = valor,
                data_vencimento = vencimento,
                tipo            = "conta",
                status          = "pendente",
                codigo_barras   = cod_barras,
                descricao       = f"Boleto importado de {os.path.basename(caminho)}",
            )
            self.db.add(ev)
            self.db.commit()
            self.db.refresh(ev)
            logger.info(f"Boleto criado: id={ev.id} valor={valor} venc={vencimento}")
            return {
                "importadas": 1,
                "ignoradas":  0,
                "evento_id":  ev.id,
                "arquivo":    os.path.basename(caminho),
                "tipo":       "boleto",
                "valor":      valor,
                "vencimento": str(vencimento),
            }

        # ── Comprovante de Compra: cria transação de débito vinculada ─────
        if tipo_documento == "comprovante_compra":
            texto = self.ocr.extrair_texto(caminho, senha=senha)
            valor = self._extrair_valor_documento(texto, tipo_documento=tipo_documento) or 0.0
            desc  = descricao_manual or self._extrair_estabelecimento_comprovante(texto) or "Compra no cartão"
            return self._criar_transacao_unica(
                descricao=desc,
                valor=valor,
                tipo="debito",
                fonte="comprovante_cartao",
                arquivo_nome=os.path.basename(caminho),
                arquivo_path=caminho,
                conta_id=conta_id,
                cartao_id=cartao_id,
            )

        raise ValueError(f"Tipo de documento desconhecido: '{tipo_documento}'")

    # --------------------------------------------------
    # Helpers internos para documentos avulsos
    # --------------------------------------------------

    def _criar_transacao_unica(
        self,
        descricao: str,
        valor: float,
        tipo: str,
        fonte: str,
        arquivo_nome: str,
        arquivo_path: str,
        conta_id: Optional[int] = None,
        cartao_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cria e persiste uma única Transacao no banco."""
        t = Transacao(
            data           = date.today(),
            descricao      = descricao,
            valor          = abs(valor),
            tipo           = tipo,
            fonte          = fonte,
            arquivo_origem = arquivo_nome,
            conta_id       = conta_id,
            cartao_id      = cartao_id,
        )
        self.classifier.classificar_e_aplicar(t)
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        logger.info(f"Transação única criada: id={t.id} valor={valor} desc={descricao}")
        return {
            "importadas":   1,
            "ignoradas":    0,
            "transacao_id": t.id,
            "arquivo":      arquivo_nome,
            "tipo":         fonte,
            "valor":        abs(valor),
        }

    def _extrair_valor_documento(self, texto: str, tipo_documento: Optional[str] = None) -> Optional[float]:
        """Tenta extrair o valor monetário principal do texto do documento."""
        if not texto:
            return None

        if tipo_documento == "nota_fiscal":
            valor_total_nota = self._extrair_valor_total_nota_fiscal(texto)
            if valor_total_nota is not None:
                return valor_total_nota

        valor_token = r"(\d{1,3}(?:[\.\s]\d{3})*(?:[\.,]\d{2})|\d+[\.,]\d{2})"
        texto_norm = " ".join((texto or "").split())

        def _parse_valor(raw: str) -> Optional[float]:
            if not raw:
                return None
            cleaned = raw.strip()
            cleaned = cleaned.replace(" ", "")

            if "," in cleaned and "." in cleaned:
                # Usa o último separador como decimal; o outro vira milhar.
                if cleaned.rfind(",") > cleaned.rfind("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")

            try:
                return float(cleaned)
            except ValueError:
                return None

        # 1) Padrões de alta prioridade para comprovantes e notas.
        padroes_total = [
            r"valor\s+total\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"total\s+a\s+pagar\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"total\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
        ]
        padroes_pagamento = [
            r"valor\s+do\s+pagamento\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"valor\s+transferido\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"valor\s+recebido\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"valor\s+pago\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
            r"valor\s+a\s+pagar\s*[:\-]?\s*(?:r\$\s*)?" + valor_token,
        ]
        padroes_prioritarios = []
        if tipo_documento == "nota_fiscal":
            padroes_prioritarios.extend(padroes_total)
            padroes_prioritarios.extend(padroes_pagamento)
        else:
            padroes_prioritarios.extend(padroes_pagamento)
            padroes_prioritarios.extend(padroes_total)
        padroes_prioritarios.extend([
            r"import[aâ]ncia\s+de\s*(?:r\$\s*)?" + valor_token,
            r"importancia\s+de\s*(?:r\$\s*)?" + valor_token,
        ])
        for padrao in padroes_prioritarios:
            m = re.search(padrao, texto_norm, re.IGNORECASE)
            if not m:
                continue
            valor = _parse_valor(m.group(1))
            if valor is not None:
                return valor

        # 2) Heurística contextual: avalia todos os valores e escolhe o mais provável.
        contexto_positivo = (
            "valor", "pagamento", "pago", "recebido", "total", "importancia", "importância"
        )
        contexto_negativo = (
            "troco", "taxa", "juros", "multa", "desconto", "iof", "encargos"
        )
        candidatos = []
        for m in re.finditer(r"(?:r\$\s*)?" + valor_token, texto_norm, re.IGNORECASE):
            valor = _parse_valor(m.group(1))
            if valor is None:
                continue
            ini = max(0, m.start() - 28)
            fim = min(len(texto_norm), m.end() + 28)
            janela = texto_norm[ini:fim].lower()
            score = 0
            score += sum(2 for k in contexto_positivo if k in janela)
            score -= sum(3 for k in contexto_negativo if k in janela)
            if "r$" in janela:
                score += 1
            candidatos.append((score, valor))

        if candidatos:
            candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return candidatos[0][1]

        return None

    def _extrair_valor_total_nota_fiscal(self, texto: str) -> Optional[float]:
        """Lê a nota inteira e prioriza o valor total do documento."""
        if not texto:
            return None

        valor_token = r"(\d{1,3}(?:[\.\s]\d{3})*(?:[\.,]\d{2})|\d+[\.,]\d{2})"

        def _parse_valor(raw: str) -> Optional[float]:
            cleaned = str(raw or "").strip().replace(" ", "")
            if not cleaned:
                return None
            if "," in cleaned and "." in cleaned:
                if cleaned.rfind(",") > cleaned.rfind("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None

        linhas = [re.sub(r"\s+", " ", linha).strip() for linha in texto.splitlines() if linha.strip()]
        positivos = (
            "valor total", "total da nota", "total geral", "total a pagar", "valor a pagar", "total"
        )
        negativos = (
            "valor pago", "pago", "troco", "desconto", "subtotal", "icms", "pis", "cofins"
        )
        candidatos: List[tuple[int, float]] = []

        for linha in linhas:
            linha_lower = linha.lower()
            for match in re.finditer(r"(?:r\$\s*)?" + valor_token, linha, re.IGNORECASE):
                valor = _parse_valor(match.group(1))
                if valor is None:
                    continue
                score = 0
                score += sum(6 for termo in positivos if termo in linha_lower)
                score -= sum(8 for termo in negativos if termo in linha_lower)
                if linha_lower.startswith("total") or linha_lower.startswith("valor total"):
                    score += 4
                candidatos.append((score, valor))

        if candidatos:
            candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)
            melhor_score, melhor_valor = candidatos[0]
            if melhor_score >= 0:
                return melhor_valor

        return None

    def _extrair_vencimento_boleto(self, texto: str) -> Optional[date]:
        """Extrai a data de vencimento de um boleto."""
        padroes = [
            r"vencimento\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
            r"vencimento\s*[:\-]?\s*(\d{2}-\d{2}-\d{4})",
            r"data\s+de\s+vencimento\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        ]
        from app.utils.helpers import parsear_data_br
        texto_lower = texto.lower()
        for padrao in padroes:
            m = re.search(padrao, texto_lower)
            if m:
                d = parsear_data_br(m.group(1))
                if d:
                    return d
        return None

    def _extrair_codigo_barras(self, texto: str) -> Optional[str]:
        """Extrai o código de barras / linha digitável de um boleto."""
        # Linha digitável: grupos de dígitos com pontos/espaços separadores
        m = re.search(
            r"\d{5}\.\d{5}\s+\d{5}\.\d{6}\s+\d{5}\.\d{6}\s+\d\s+\d{14}",
            texto
        )
        if m:
            return m.group(0).replace(" ", "")
        # Código de barras numérico contínuo (44 dígitos)
        m = re.search(r"\b(\d{44,48})\b", texto.replace(" ", "").replace("\n", ""))
        if m:
            return m.group(1)
        return None

    def _extrair_beneficiario_boleto(self, texto: str) -> Optional[str]:
        """Extrai o nome do beneficiário/cedente do boleto."""
        m = re.search(r"benefici[aá]rio\s*[:\-]?\s*(.{3,60})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        m = re.search(r"cedente\s*[:\-]?\s*(.{3,60})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        return None

    def _extrair_descricao_documento(self, texto: str) -> Optional[str]:
        """Tenta extrair um nome/emitente de nota fiscal ou documento."""
        m = re.search(r"emitente\s*[:\-]?\s*(.{3,80})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        m = re.search(r"razão\s+social\s*[:\-]?\s*(.{3,80})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        return None

    def _extrair_descricao_nota_fiscal(self, texto: str) -> Optional[str]:
        """Extrai um estabelecimento útil de uma nota fiscal."""
        descricao = self._extrair_descricao_documento(texto)
        if descricao:
            return descricao

        linhas = [re.sub(r"\s+", " ", linha).strip() for linha in (texto or "").splitlines() if linha.strip()]
        descartes = (
            "documento auxiliar", "nota fiscal", "danfe", "nfc-e", "nfce", "cpf", "cnpj",
            "chave de acesso", "protocolo", "serie", "numero", "data de emissao", "valor total",
            "valor pago", "troco", "subtotal", "desconto", "tributos"
        )
        for linha in linhas[:12]:
            linha_lower = linha.lower()
            if any(termo in linha_lower for termo in descartes):
                continue
            if re.search(r"\d{2}[\./-]\d{2}[\./-]\d{2,4}", linha_lower):
                continue
            if re.search(r"(?:r\$\s*)?\d+[\.,]\d{2}", linha_lower):
                continue
            if len(linha) < 4:
                continue
            return linha[:120]

        return None

    def _extrair_descricao_recibo(self, texto: str) -> Optional[str]:
        """Tenta extrair a descrição principal de um recibo simples."""
        padroes = [
            r"referente a\s*[:\-]?\s*(.{3,100})",
            r"referente ao\s*[:\-]?\s*(.{3,100})",
            r"descricao\s*[:\-]?\s*(.{3,100})",
            r"descri[cç][aã]o\s*[:\-]?\s*(.{3,100})",
            r"recebi(?:emos)?\s+de\s+.{3,80}?\s+referente a\s+(.{3,100})",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return m.group(1).strip(" .:-")[:120]
        return None

    def _extrair_estabelecimento_comprovante(self, texto: str) -> Optional[str]:
        """Extrai o nome do estabelecimento de um comprovante de compra."""
        m = re.search(r"estabelecimento\s*[:\-]?\s*(.{3,80})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        m = re.search(r"lojista\s*[:\-]?\s*(.{3,80})", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
        return None

    def _extrair_descricao_comprovante_bancario(self, texto: str) -> Optional[str]:
        """Extrai favorecido/destino/descrição de um comprovante bancário."""
        padroes = [
            r"favorecido\s*[:\-]?\s*(.{3,100})",
            r"destinat[aá]rio\s*[:\-]?\s*(.{3,100})",
            r"recebedor\s*[:\-]?\s*(.{3,100})",
            r"nome do recebedor\s*[:\-]?\s*(.{3,100})",
            r"nome do favorecido\s*[:\-]?\s*(.{3,100})",
            r"origem\s*[:\-]?\s*(.{3,100})",
            r"destino\s*[:\-]?\s*(.{3,100})",
            r"descri[cç][aã]o\s*[:\-]?\s*(.{3,100})",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return m.group(1).strip(" .:-")[:120]
        return None

    def _inferir_tipo_comprovante_bancario(self, texto: str) -> str:
        """Infere se o comprovante representa saída (débito) ou entrada (crédito)."""
        texto_norm = texto.lower()

        chaves_credito = [
            "recebido", "recebida", "valor recebido", "pix recebido",
            "transferência recebida", "transferencia recebida", "creditado",
            "crédito em conta", "credito em conta", "entrada",
        ]
        chaves_debito = [
            "pagamento", "pagamento realizado", "valor pago", "pix enviado",
            "transferência realizada", "transferencia realizada", "enviado",
            "debitado", "débito", "debito", "saída", "saida",
            "comprovante de pagamento",
        ]

        score_credito = sum(1 for chave in chaves_credito if chave in texto_norm)
        score_debito = sum(1 for chave in chaves_debito if chave in texto_norm)
        return "credito" if score_credito > score_debito else "debito"

    def _detectar_banco_csv_cartao(self, cols: List[str], df: "pd.DataFrame") -> str:
        """
        Identifica o banco pelo cabeçalho e/ou conteúdo do CSV.

        Returns:
            "nubank" | "inter" | "c6" | "xp" | "itau" | "bradesco" |
            "santander" | "bb" | "caixa" | "pagbank" | "generico"
        """
        col_str = " ".join(cols)

        # Nubank: colunas "date, title, amount" ou "data, descrição, valor"
        if set(["date", "title", "amount"]).issubset(set(cols)):
            return "nubank"
        if "identificador" in col_str and "categoria" in col_str:
            return "nubank"

        # Inter: "data lançamento" ou "data lancamento"
        if any("lan" in c for c in cols) and any("descri" in c for c in cols):
            return "inter"
        if "tipo lançamento" in col_str or "tipo lancamento" in col_str:
            return "inter"

        # C6 Bank: "data da compra" ou "nome no cartão"
        if "nome no cartão" in col_str or "nome no cartao" in col_str:
            return "c6"
        if "data da compra" in col_str:
            return "c6"

        # XP/BTG: "data de fechamento" ou "portador"
        if "portador" in col_str:
            return "xp"
        if "data de fechamento" in col_str:
            return "xp"

        # Itaú: "lançamento" + "valor (r$)"
        if "valor (r$)" in col_str or "valor r$" in col_str:
            return "itau"

        if "data de lançamento" in col_str and "estabelecimento" in col_str:
            return "bradesco"

        if "lançamento na fatura" in col_str or "lancamento na fatura" in col_str:
            return "santander"

        if "data compra" in col_str and "nome do estabelecimento" in col_str:
            return "bb"

        if "descricao compra" in col_str and "valor compra" in col_str:
            return "caixa"

        if "data da transação" in col_str or "data da transacao" in col_str:
            return "pagbank"

        return "generico"

    def _parse_nubank_csv(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Parser para CSV da fatura Nubank.
        Formato: date,title,amount  OU  Data,Descrição,Valor[,Categoria,Parcelas,Identificador]
        """
        transacoes = []
        cols = [str(c).strip() for c in df.columns]

        # Mapeia pelos nomes reais das colunas
        col_data  = next((c for c in cols if c.lower() in ["date", "data"]), None)
        col_desc  = next((c for c in cols if c.lower() in ["title", "descrição", "descricao"]), None)
        col_valor = next((c for c in cols if c.lower() in ["amount", "valor"]), None)
        col_parc  = next((c for c in cols if "parcela" in c.lower()), None)

        if not all([col_data, col_desc, col_valor]):
            logger.warning("Nubank CSV: colunas esperadas não encontradas")
            mapeamento = self._detectar_mapeamento_csv(cols)
            return self._df_para_transacoes(df, mapeamento)

        for _, row in df.iterrows():
            try:
                data  = parsear_data_br(str(row[col_data]).strip())
                desc  = str(row[col_desc]).strip()
                valor = converter_valor_br(str(row[col_valor]).strip())
                if not data or valor is None or not desc:
                    continue

                # No Nubank, valor positivo = compra (débito na fatura), negativo = estorno
                tipo = "credito" if valor < 0 else "debito"

                # Parcelas
                p_atual, p_total = None, None
                if col_parc:
                    parc_raw = str(row.get(col_parc, "")).strip()
                    m = re.search(r"(\d+)/(\d+)", parc_raw)
                    if m:
                        p_atual, p_total = int(m.group(1)), int(m.group(2))
                else:
                    from app.utils.helpers import detectar_parcela
                    p_atual, p_total = detectar_parcela(desc)

                transacoes.append({
                    "data":          data,
                    "descricao":     desc,
                    "valor":         abs(valor),
                    "tipo":          tipo,
                    "fonte":         "Nubank",
                    "parcela_atual": p_atual,
                    "parcelas_total": p_total,
                })
            except Exception as e:
                logger.debug(f"Nubank CSV linha ignorada: {e}")
        return transacoes

    def _parse_inter_csv(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Parser para CSV de extrato/fatura do Banco Inter.
        Colunas típicas: Data Lançamento, Descrição, Valor, Tipo Lançamento
        """
        transacoes = []
        cols = [str(c).strip() for c in df.columns]
        col_lower = {c: c.lower() for c in cols}

        col_data  = next((c for c, cl in col_lower.items() if "data" in cl), None)
        col_desc  = next((c for c, cl in col_lower.items() if "descri" in cl), None)
        col_valor = next((c for c, cl in col_lower.items() if "valor" in cl), None)
        col_tipo  = next((c for c, cl in col_lower.items() if "tipo" in cl), None)

        if not all([col_data, col_valor]):
            mapeamento = self._detectar_mapeamento_csv(cols)
            return self._df_para_transacoes(df, mapeamento)

        for _, row in df.iterrows():
            try:
                data  = parsear_data_br(str(row[col_data]).strip())
                desc  = str(row[col_desc]).strip() if col_desc else "Inter"
                valor = converter_valor_br(str(row[col_valor]).strip())
                if not data or valor is None:
                    continue

                if col_tipo:
                    tp_raw = str(row[col_tipo]).lower()
                    tipo = "credito" if any(x in tp_raw for x in ["c", "entrada", "estorno"]) else "debito"
                else:
                    from app.utils.helpers import detectar_tipo_transacao
                    tipo = detectar_tipo_transacao(desc, valor)

                from app.utils.helpers import detectar_parcela
                p_atual, p_total = detectar_parcela(desc)

                transacoes.append({
                    "data":          data,
                    "descricao":     desc,
                    "valor":         abs(valor),
                    "tipo":          tipo,
                    "fonte":         "Banco Inter",
                    "parcela_atual": p_atual,
                    "parcelas_total": p_total,
                })
            except Exception as e:
                logger.debug(f"Inter CSV linha ignorada: {e}")
        return transacoes

    def _parse_c6_csv(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Parser para CSV de fatura do C6 Bank.
        Colunas típicas: Data da Compra, Descrição/Nome no Cartão, Valor, Parcelas
        """
        transacoes = []
        cols = [str(c).strip() for c in df.columns]
        col_lower = {c: c.lower() for c in cols}

        col_data  = next((c for c, cl in col_lower.items() if "data" in cl), None)
        col_desc  = next((c for c, cl in col_lower.items()
                          if "descri" in cl or "nome" in cl or "estabelecimento" in cl), None)
        col_valor = next((c for c, cl in col_lower.items() if "valor" in cl), None)
        col_parc  = next((c for c, cl in col_lower.items() if "parcela" in cl), None)

        if not all([col_data, col_valor]):
            mapeamento = self._detectar_mapeamento_csv(cols)
            return self._df_para_transacoes(df, mapeamento)

        for _, row in df.iterrows():
            try:
                data  = parsear_data_br(str(row[col_data]).strip())
                desc  = str(row[col_desc]).strip() if col_desc else "C6 Bank"
                valor = converter_valor_br(str(row[col_valor]).strip())
                if not data or valor is None:
                    continue

                # C6 CSV: valores positivos são compras (débito)
                tipo = "credito" if valor < 0 else "debito"

                p_atual, p_total = None, None
                if col_parc:
                    parc_raw = str(row.get(col_parc, "")).strip()
                    m = re.search(r"(\d+)/(\d+)", parc_raw)
                    if m:
                        p_atual, p_total = int(m.group(1)), int(m.group(2))
                if not p_atual:
                    from app.utils.helpers import detectar_parcela
                    p_atual, p_total = detectar_parcela(desc)

                transacoes.append({
                    "data":          data,
                    "descricao":     desc,
                    "valor":         abs(valor),
                    "tipo":          tipo,
                    "fonte":         "C6 Bank",
                    "parcela_atual": p_atual,
                    "parcelas_total": p_total,
                })
            except Exception as e:
                logger.debug(f"C6 CSV linha ignorada: {e}")
        return transacoes

    def _parse_xp_csv(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Parser para CSV de fatura XP/BTG.
        Colunas típicas: Data, Portador, Descrição, Valor
        """
        transacoes = []
        cols = [str(c).strip() for c in df.columns]
        col_lower = {c: c.lower() for c in cols}

        col_data  = next((c for c, cl in col_lower.items() if "data" in cl), None)
        col_desc  = next((c for c, cl in col_lower.items() if "descri" in cl or "estabele" in cl), None)
        col_valor = next((c for c, cl in col_lower.items() if "valor" in cl), None)

        if not all([col_data, col_valor]):
            mapeamento = self._detectar_mapeamento_csv(cols)
            return self._df_para_transacoes(df, mapeamento)

        for _, row in df.iterrows():
            try:
                data  = parsear_data_br(str(row[col_data]).strip())
                desc  = str(row[col_desc]).strip() if col_desc else "XP"
                valor = converter_valor_br(str(row[col_valor]).strip())
                if not data or valor is None:
                    continue

                tipo = "credito" if valor < 0 else "debito"

                from app.utils.helpers import detectar_parcela
                p_atual, p_total = detectar_parcela(desc)

                transacoes.append({
                    "data":          data,
                    "descricao":     desc,
                    "valor":         abs(valor),
                    "tipo":          tipo,
                    "fonte":         "XP Investimentos",
                    "parcela_atual": p_atual,
                    "parcelas_total": p_total,
                })
            except Exception as e:
                logger.debug(f"XP CSV linha ignorada: {e}")
        return transacoes

    def _parse_itau_csv(self, df: "pd.DataFrame") -> List[Dict]:
        """
        Parser para CSV de fatura Itaú.
        Colunas típicas: Lançamento, Valor (R$)  ou  Data, Estabelecimento, Valor
        """
        transacoes = []
        cols = [str(c).strip() for c in df.columns]
        col_lower = {c: c.lower() for c in cols}

        col_data  = next((c for c, cl in col_lower.items() if "data" in cl or "lança" in cl or "lanca" in cl), None)
        col_desc  = next((c for c, cl in col_lower.items()
                          if "estabele" in cl or "descri" in cl or "histor" in cl), None)
        col_valor = next((c for c, cl in col_lower.items() if "valor" in cl), None)

        if not all([col_data, col_valor]):
            mapeamento = self._detectar_mapeamento_csv(cols)
            return self._df_para_transacoes(df, mapeamento)

        for _, row in df.iterrows():
            try:
                data  = parsear_data_br(str(row[col_data]).strip())
                desc  = str(row[col_desc]).strip() if col_desc else "Itaú"
                valor = converter_valor_br(str(row[col_valor]).strip())
                if not data or valor is None:
                    continue

                tipo = "credito" if valor < 0 else "debito"

                from app.utils.helpers import detectar_parcela
                p_atual, p_total = detectar_parcela(desc)

                transacoes.append({
                    "data":          data,
                    "descricao":     desc,
                    "valor":         abs(valor),
                    "tipo":          tipo,
                    "fonte":         "Itaú",
                    "parcela_atual": p_atual,
                    "parcelas_total": p_total,
                })
            except Exception as e:
                logger.debug(f"Itaú CSV linha ignorada: {e}")
        return transacoes

    def _detectar_mapeamento_csv(self, colunas: List[str]) -> Dict[str, str]:
        """
        Detecta automaticamente o mapeamento de colunas de um CSV/Excel
        com base em nomes comuns em extratos brasileiros.
        """
        col_lower = {c: c.lower().strip() for c in colunas}

        candidatos = {
            "data":      ["data", "date", "dt", "data lançamento", "data lanc"],
            "descricao": ["descricao", "descrição", "historico", "histórico",
                          "memo", "detalhe", "descrição da transação"],
            "valor":     ["valor", "montante", "amount", "valor r$", "vlr", "debit", "credit"],
            "tipo":      ["tipo", "natureza", "type", "debito/credito", "d/c"],
        }

        mapeamento = {}
        for campo, opcoes in candidatos.items():
            for col_orig, col_norm in col_lower.items():
                if any(op in col_norm for op in opcoes):
                    mapeamento[campo] = col_orig
                    break

        return mapeamento

    def _df_para_transacoes(
        self, df: "pd.DataFrame", mapeamento: Dict[str, str]
    ) -> List[Dict]:
        """Converte um DataFrame do pandas em lista de transações brutas."""
        transacoes = []

        col_data  = mapeamento.get("data")
        col_desc  = mapeamento.get("descricao")
        col_valor = mapeamento.get("valor")
        col_tipo  = mapeamento.get("tipo")

        if not col_data or not col_valor:
            logger.warning("Mapeamento de colunas insuficiente para importar CSV/Excel")
            return []

        for _, row in df.iterrows():
            try:
                data_raw  = str(row.get(col_data, "")).strip()
                valor_raw = str(row.get(col_valor, "")).strip()
                desc_raw  = str(row.get(col_desc, "Sem descrição")).strip() if col_desc else "Transação"
                tipo_raw  = str(row.get(col_tipo, "")).strip() if col_tipo else ""

                data  = parsear_data_br(data_raw)
                valor = converter_valor_br(valor_raw)

                if not data or valor is None:
                    continue

                # Detecta tipo pela coluna ou pelo valor/descrição
                if tipo_raw and any(x in tipo_raw.lower() for x in ["c", "cred", "entrada"]):
                    tipo = "credito"
                elif tipo_raw and any(x in tipo_raw.lower() for x in ["d", "deb", "saida"]):
                    tipo = "debito"
                else:
                    tipo = detectar_tipo_transacao(desc_raw, valor)

                transacoes.append({
                    "data":      data,
                    "descricao": desc_raw,
                    "valor":     abs(valor),
                    "tipo":      tipo,
                })
            except Exception as e:
                logger.debug(f"Linha ignorada: {e}")
                continue

        return transacoes
