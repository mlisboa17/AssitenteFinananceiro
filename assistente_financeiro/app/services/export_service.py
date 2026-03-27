"""
Serviço de exportação de relatórios financeiros.

Suporta os formatos de saída:
  - CSV   : via pandas
  - Excel : via pandas + xlsxwriter (com formatação profissional)
  - PDF   : via reportlab (relatório completo com gráficos e tabelas)
"""

import os
import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models import Transacao, Categoria
from app.utils.helpers import formatar_moeda, periodo_label

logger = logging.getLogger(__name__)


class ExportService:
    """
    Serviço de exportação de dados financeiros.

    Gera arquivos prontos para download ou compartilhamento.
    """

    def __init__(self, db: Session):
        self.db = db

    # ================================================
    # Exportação para CSV
    # ================================================

    def exportar_csv(
        self,
        caminho_saida: str,
        mes: Optional[int] = None,
        ano: Optional[int] = None,
        categoria_id: Optional[int] = None,
    ) -> str:
        """
        Exporta transações para um arquivo CSV.

        Args:
            caminho_saida: Caminho completo do arquivo a gerar
            mes:           Filtro de mês (opcional)
            ano:           Filtro de ano (opcional)
            categoria_id:  Filtro de categoria (opcional)

        Returns:
            Caminho do arquivo gerado
        """
        import pandas as pd

        transacoes = self._consultar_transacoes(mes, ano, categoria_id)
        df = self._transacoes_para_df(transacoes)
        df.to_csv(caminho_saida, index=False, encoding="utf-8-sig", sep=";")

        logger.info(f"CSV exportado: {caminho_saida} ({len(df)} linhas)")
        return caminho_saida

    # ================================================
    # Exportação para Excel
    # ================================================

    def exportar_excel(
        self,
        caminho_saida: str,
        mes: Optional[int] = None,
        ano: Optional[int] = None,
        categoria_id: Optional[int] = None,
    ) -> str:
        """
        Exporta transações para Excel com formatação profissional.
        Inclui aba de transações e aba de resumo por categoria.

        Returns:
            Caminho do arquivo gerado
        """
        import pandas as pd

        transacoes = self._consultar_transacoes(mes, ano, categoria_id)
        df         = self._transacoes_para_df(transacoes)

        with pd.ExcelWriter(caminho_saida, engine="xlsxwriter") as writer:
            workbook = writer.book

            # --- Formatos ---
            fmt_header  = workbook.add_format({"bold": True, "bg_color": "#2E86AB", "font_color": "white", "border": 1})
            fmt_moeda   = workbook.add_format({"num_format": "R$ #,##0.00", "border": 1})
            fmt_debito  = workbook.add_format({"font_color": "#C0392B", "num_format": "R$ #,##0.00", "border": 1})
            fmt_credito = workbook.add_format({"font_color": "#27AE60", "num_format": "R$ #,##0.00", "border": 1})
            fmt_normal  = workbook.add_format({"border": 1})
            fmt_titulo  = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#2E86AB"})

            # --- Aba: Transações ---
            df.to_excel(writer, sheet_name="Transações", index=False, startrow=2)
            ws = writer.sheets["Transações"]

            titulo = f"Extrato Financeiro"
            if mes and ano:
                titulo += f" - {periodo_label(mes, ano)}"
            ws.write(0, 0, titulo, fmt_titulo)

            # Formata cabeçalhos
            for col_num, col_name in enumerate(df.columns):
                ws.write(2, col_num, col_name, fmt_header)
                ws.set_column(col_num, col_num, max(15, len(col_name) + 5))

            # Formata linhas com cores por tipo
            for row_num, row in df.iterrows():
                tipo = row.get("Tipo", "")
                fmt_v = fmt_debito if tipo == "debito" else fmt_credito
                ws.write(row_num + 3, df.columns.get_loc("Valor"), row["Valor"], fmt_v)

            # --- Aba: Resumo ---
            resumo_df = self._gerar_resumo_por_categoria(transacoes)
            resumo_df.to_excel(writer, sheet_name="Resumo", index=False, startrow=2)
            ws_res = writer.sheets["Resumo"]
            ws_res.write(0, 0, "Resumo por Categoria", fmt_titulo)
            for col_num, col_name in enumerate(resumo_df.columns):
                ws_res.write(2, col_num, col_name, fmt_header)
                ws_res.set_column(col_num, col_num, 20)

        logger.info(f"Excel exportado: {caminho_saida} ({len(df)} transações)")
        return caminho_saida

    # ================================================
    # Exportação para PDF
    # ================================================

    def exportar_pdf(
        self,
        caminho_saida: str,
        mes: Optional[int] = None,
        ano: Optional[int] = None,
    ) -> str:
        """
        Gera relatório financeiro completo em PDF.
        Inclui resumo, tabela de transações e total por categoria.

        Returns:
            Caminho do arquivo gerado
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle,
            Paragraph, Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT

        transacoes = self._consultar_transacoes(mes, ano)
        styles     = getSampleStyleSheet()

        # Estilos personalizados
        titulo_style = ParagraphStyle(
            "Titulo", parent=styles["Title"],
            fontSize=16, textColor=colors.HexColor("#2E86AB"),
            spaceAfter=6
        )
        subtitulo_style = ParagraphStyle(
            "SubTitulo", parent=styles["Heading2"],
            fontSize=11, textColor=colors.HexColor("#555555")
        )

        doc      = SimpleDocTemplate(caminho_saida, pagesize=A4, topMargin=2*cm)
        conteudo = []

        # ----- Cabeçalho -----
        periodo = periodo_label(mes, ano) if mes and ano else "Geral"
        conteudo.append(Paragraph("Assistente Financeiro Pessoal", titulo_style))
        conteudo.append(Paragraph(f"Relatório Financeiro — {periodo}", subtitulo_style))
        conteudo.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
        conteudo.append(Spacer(1, 0.5*cm))

        # ----- Resumo -----
        total_deb = sum(t.valor for t in transacoes if t.tipo == "debito")
        total_cred = sum(t.valor for t in transacoes if t.tipo == "credito")
        conteudo.append(Paragraph("Resumo do Período", subtitulo_style))
        resumo_data = [
            ["", "Valor"],
            ["Total de Despesas",  formatar_moeda(total_deb)],
            ["Total de Receitas",  formatar_moeda(total_cred)],
            ["Saldo",              formatar_moeda(total_cred - total_deb)],
        ]
        t_resumo = Table(resumo_data, colWidths=[8*cm, 5*cm])
        t_resumo.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#2E86AB")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EBF5FB")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        conteudo.append(t_resumo)
        conteudo.append(Spacer(1, 0.5*cm))

        # ----- Tabela de transações -----
        conteudo.append(Paragraph("Transações", subtitulo_style))
        dados_tabela = [["Data", "Descrição", "Categoria", "Tipo", "Valor"]]
        for t in transacoes[:200]:   # Limita a 200 para evitar PDF gigante
            cat = t.categoria.nome if t.categoria else "—"
            dados_tabela.append([
                t.data.strftime("%d/%m/%Y"),
                t.descricao[:40],
                cat,
                "Débito" if t.tipo == "debito" else "Crédito",
                formatar_moeda(t.valor),
            ])

        tabela = Table(dados_tabela, colWidths=[2.5*cm, 7*cm, 3*cm, 2*cm, 3*cm])
        tabela.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), colors.HexColor("#2E86AB")),
            ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
            ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#EBF5FB")]),
            ("GRID",           (0,0), (-1,-1), 0.3, colors.grey),
            ("ALIGN",          (4,0), (4,-1), "RIGHT"),
        ]))
        conteudo.append(tabela)

        doc.build(conteudo)
        logger.info(f"PDF exportado: {caminho_saida}")
        return caminho_saida

    # --------------------------------------------------
    # Helpers internos
    # --------------------------------------------------

    def _consultar_transacoes(
        self,
        mes: Optional[int],
        ano: Optional[int],
        categoria_id: Optional[int] = None,
    ) -> List[Transacao]:
        """Consulta transações com filtros opcionais."""
        q = self.db.query(Transacao)
        if mes:
            q = q.filter(extract("month", Transacao.data) == mes)
        if ano:
            q = q.filter(extract("year", Transacao.data) == ano)
        if categoria_id:
            q = q.filter(Transacao.categoria_id == categoria_id)
        return q.order_by(Transacao.data).all()

    def _transacoes_para_df(self, transacoes: List[Transacao]) -> "pd.DataFrame":
        """Converte lista de Transacao em DataFrame do pandas."""
        import pandas as pd

        dados = []
        for t in transacoes:
            dados.append({
                "Data":        t.data.strftime("%d/%m/%Y"),
                "Descrição":   t.descricao,
                "Categoria":   t.categoria.nome if t.categoria else "—",
                "Tipo":        t.tipo,
                "Valor":       t.valor,
                "Parcela":     f"{t.parcela_atual}/{t.parcelas_total}" if t.parcela_atual else "—",
                "Fonte":       t.fonte or "—",
            })
        return pd.DataFrame(dados)

    def _gerar_resumo_por_categoria(self, transacoes: List[Transacao]) -> "pd.DataFrame":
        """Gera DataFrame com resumo de gastos por categoria."""
        import pandas as pd
        from collections import defaultdict

        gastos: Dict[str, float] = defaultdict(float)
        for t in transacoes:
            if t.tipo == "debito":
                cat = t.categoria.nome if t.categoria else "Sem Categoria"
                gastos[cat] += t.valor

        total = sum(gastos.values())
        linhas = []
        for cat, valor in sorted(gastos.items(), key=lambda x: x[1], reverse=True):
            linhas.append({
                "Categoria":  cat,
                "Total (R$)": round(valor, 2),
                "Percentual": f"{(valor/total*100):.1f}%" if total else "0%",
            })

        return pd.DataFrame(linhas)
