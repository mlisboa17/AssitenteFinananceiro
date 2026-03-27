"""
Serviço de insights financeiros inteligentes.

Gera alertas, detecta padrões anômalos e identifica oportunidades
de economia comparando o comportamento financeiro ao longo do tempo.
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Optional, Any
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models import Transacao, Categoria, Orcamento
from app.utils.helpers import calcular_percentual, formatar_moeda, periodo_label

logger = logging.getLogger(__name__)


class InsightsService:
    """
    Gera insights financeiros automatizados:
      - Alertas de gastos acima do esperado
      - Detecção de categorias fora do padrão histórico
      - Comparação com mês anterior
      - Oportunidades de economia
      - Verificação de orçamentos próximos do limite
    """

    # Variação considerada anormal (30% acima da média histórica)
    LIMIAR_AUMENTO = 1.30

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------
    # Interface pública - agrupa todos os insights
    # --------------------------------------------------

    def gerar_insights(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Gera todos os insights disponíveis para um período.

        Args:
            mes: Mês de referência (1-12)
            ano: Ano de referência

        Returns:
            Lista de dicionários com os insights gerados
        """
        insights = []

        insights += self.detectar_aumento_gastos(mes, ano)
        insights += self.detectar_categorias_anomalas(mes, ano)
        insights += self.verificar_orcamentos(mes, ano)
        insights += self.oportunidades_economia(mes, ano)

        # Ordena por severidade: alerta > aviso > info
        prioridade = {"alerta": 0, "aviso": 1, "info": 2, "oportunidade": 3}
        insights.sort(key=lambda x: prioridade.get(x.get("tipo", "info"), 99))

        return insights

    # --------------------------------------------------
    # Detecção de aumento de gastos
    # --------------------------------------------------

    def detectar_aumento_gastos(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Compara os gastos totais do mês atual com a média dos 3 meses anteriores.
        Retorna alerta se o aumento for superior ao limiar definido.
        """
        total_atual = self._total_despesas(mes, ano)
        media_anterior = self._media_despesas_anteriores(mes, ano, n_meses=3)

        if media_anterior <= 0 or total_atual <= 0:
            return []

        variacao = total_atual / media_anterior

        if variacao >= self.LIMIAR_AUMENTO:
            perc = (variacao - 1) * 100
            return [{
                "tipo":      "alerta",
                "titulo":    "Gastos acima do normal",
                "descricao": (
                    f"Seus gastos em {periodo_label(mes, ano)} estão "
                    f"{perc:.0f}% acima da média dos últimos 3 meses "
                    f"({formatar_moeda(total_atual)} vs média {formatar_moeda(media_anterior)})."
                ),
                "valor":     total_atual,
            }]

        return []

    # --------------------------------------------------
    # Categorias anômalas
    # --------------------------------------------------

    def detectar_categorias_anomalas(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Identifica categorias cujos gastos estão significativamente
        acima da média histórica daquela mesma categoria.
        """
        gastos_mes = self._gastos_por_categoria(mes, ano)
        insights = []

        for cat_id, valor_atual in gastos_mes.items():
            media = self._media_categoria_anterior(cat_id, mes, ano, n_meses=3)
            if media <= 0:
                continue

            if valor_atual / media >= self.LIMIAR_AUMENTO:
                cat = self.db.query(Categoria).filter(Categoria.id == cat_id).first()
                nome_cat = cat.nome if cat else f"ID {cat_id}"
                perc = ((valor_atual / media) - 1) * 100
                insights.append({
                    "tipo":      "aviso",
                    "titulo":    f"Gasto elevado: {nome_cat}",
                    "descricao": (
                        f"Categoria {nome_cat} com {perc:.0f}% acima da média "
                        f"({formatar_moeda(valor_atual)} vs média {formatar_moeda(media)})."
                    ),
                    "valor":     valor_atual,
                    "categoria": nome_cat,
                })

        return insights

    # --------------------------------------------------
    # Verificação de orçamentos
    # --------------------------------------------------

    def verificar_orcamentos(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Verifica se algum orçamento mensal está próximo ou ultrapassou o limite.
        """
        orcamentos = (
            self.db.query(Orcamento)
            .filter(Orcamento.mes == mes, Orcamento.ano == ano)
            .all()
        )

        gastos = self._gastos_por_categoria(mes, ano)
        insights = []

        for orc in orcamentos:
            gasto = gastos.get(orc.categoria_id, 0.0)
            perc  = calcular_percentual(gasto, orc.valor_limite)
            nome_cat = orc.categoria.nome if orc.categoria else f"ID {orc.categoria_id}"

            if perc >= 100:
                insights.append({
                    "tipo":      "alerta",
                    "titulo":    f"Orçamento estourado: {nome_cat}",
                    "descricao": (
                        f"O limite de {formatar_moeda(orc.valor_limite)} para "
                        f"{nome_cat} foi ultrapassado! "
                        f"Gasto atual: {formatar_moeda(gasto)} ({perc:.0f}%)."
                    ),
                    "valor":     gasto,
                    "categoria": nome_cat,
                })
            elif perc >= orc.alerta_percentual:
                insights.append({
                    "tipo":      "aviso",
                    "titulo":    f"Orçamento próximo do limite: {nome_cat}",
                    "descricao": (
                        f"{perc:.0f}% do orçamento de {nome_cat} utilizado. "
                        f"({formatar_moeda(gasto)} de {formatar_moeda(orc.valor_limite)})."
                    ),
                    "valor":     gasto,
                    "categoria": nome_cat,
                })

        return insights

    # --------------------------------------------------
    # Oportunidades de economia
    # --------------------------------------------------

    def oportunidades_economia(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Identifica as categorias com maior gasto e sugere redução.
        Foca nas 3 maiores categorias de despesa.
        """
        gastos = self._gastos_por_categoria(mes, ano)
        if not gastos:
            return []

        # Busca nomes das categorias
        cat_map = {
            c.id: c.nome
            for c in self.db.query(Categoria).all()
        }

        # Ordena por valor e pega as 3 maiores
        top3 = sorted(gastos.items(), key=lambda x: x[1], reverse=True)[:3]

        insights = []
        for cat_id, valor in top3:
            nome = cat_map.get(cat_id, f"ID {cat_id}")
            insights.append({
                "tipo":      "oportunidade",
                "titulo":    f"Maior gasto: {nome}",
                "descricao": (
                    f"Você gastou {formatar_moeda(valor)} com {nome} "
                    f"em {periodo_label(mes, ano)}. "
                    "Pequenas reduções nessa categoria podem gerar economia significativa."
                ),
                "valor":     valor,
                "categoria": nome,
            })

        return insights

    # --------------------------------------------------
    # Dados de resumo para o dashboard
    # --------------------------------------------------

    def resumo_dashboard(self, mes: int, ano: int) -> Dict[str, Any]:
        """
        Retorna métricas consolidadas para o painel principal.

        Returns:
            Dicionário com totais, evolução mensal e distribuição por categoria
        """
        total_receitas  = self._total_receitas(mes, ano)
        total_despesas  = self._total_despesas(mes, ano)
        saldo           = total_receitas - total_despesas

        gastos_por_cat  = self._gastos_por_categoria_com_nome(mes, ano)
        evolucao        = self._evolucao_ultimos_meses(mes, ano, n=6)

        return {
            "total_receitas":    total_receitas,
            "total_despesas":    total_despesas,
            "saldo_mensal":      saldo,
            "total_transacoes":  self._total_transacoes(mes, ano),
            "mes_referencia":    periodo_label(mes, ano),
            "categorias_gastos": gastos_por_cat,
            "evolucao_mensal":   evolucao,
        }

    # --------------------------------------------------
    # Consultas internas ao banco de dados
    # --------------------------------------------------

    def _total_despesas(self, mes: int, ano: int) -> float:
        r = (
            self.db.query(func.sum(Transacao.valor))
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.tipo == "debito"
            )
            .scalar()
        )
        return float(r or 0)

    def _total_receitas(self, mes: int, ano: int) -> float:
        r = (
            self.db.query(func.sum(Transacao.valor))
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.tipo == "credito"
            )
            .scalar()
        )
        return float(r or 0)

    def _total_transacoes(self, mes: int, ano: int) -> int:
        return (
            self.db.query(func.count(Transacao.id))
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
            )
            .scalar() or 0
        )

    def _media_despesas_anteriores(self, mes: int, ano: int, n_meses: int) -> float:
        """Calcula a média de despesas dos N meses anteriores ao período dado."""
        totais = []
        m, a = mes, ano
        for _ in range(n_meses):
            m -= 1
            if m == 0:
                m, a = 12, a - 1
            totais.append(self._total_despesas(m, a))
        valores = [v for v in totais if v > 0]
        return sum(valores) / len(valores) if valores else 0.0

    def _media_categoria_anterior(
        self, categoria_id: int, mes: int, ano: int, n_meses: int
    ) -> float:
        """Média de gastos de uma categoria nos N meses anteriores."""
        totais = []
        m, a = mes, ano
        for _ in range(n_meses):
            m -= 1
            if m == 0:
                m, a = 12, a - 1
            r = (
                self.db.query(func.sum(Transacao.valor))
                .filter(
                    extract("month", Transacao.data) == m,
                    extract("year",  Transacao.data) == a,
                    Transacao.categoria_id == categoria_id,
                    Transacao.tipo == "debito",
                )
                .scalar()
            )
            if r:
                totais.append(float(r))
        return sum(totais) / len(totais) if totais else 0.0

    def _gastos_por_categoria(self, mes: int, ano: int) -> Dict[int, float]:
        """Retorna dict {categoria_id: total_gasto} para o período."""
        rows = (
            self.db.query(
                Transacao.categoria_id,
                func.sum(Transacao.valor).label("total")
            )
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.tipo == "debito",
                Transacao.categoria_id.isnot(None),
            )
            .group_by(Transacao.categoria_id)
            .all()
        )
        return {r.categoria_id: float(r.total) for r in rows}

    def _gastos_por_categoria_com_nome(self, mes: int, ano: int) -> List[Dict]:
        """Retorna lista de gastos por categoria com nome e percentual."""
        gastos = self._gastos_por_categoria(mes, ano)
        total  = sum(gastos.values())
        cat_map = {c.id: c.nome for c in self.db.query(Categoria).all()}

        resultado = []
        for cat_id, valor in sorted(gastos.items(), key=lambda x: x[1], reverse=True):
            resultado.append({
                "categoria":  cat_map.get(cat_id, f"ID {cat_id}"),
                "valor":      round(valor, 2),
                "percentual": round(calcular_percentual(valor, total), 1),
            })
        return resultado

    def _evolucao_ultimos_meses(self, mes: int, ano: int, n: int) -> List[Dict]:
        """Retorna receitas e despesas dos últimos N meses (incluindo o atual)."""
        resultado = []
        m, a = mes, ano
        for _ in range(n):
            resultado.insert(0, {
                "mes":       periodo_label(m, a),
                "receitas":  round(self._total_receitas(m, a), 2),
                "despesas":  round(self._total_despesas(m, a), 2),
            })
            m -= 1
            if m == 0:
                m, a = 12, a - 1
        return resultado
