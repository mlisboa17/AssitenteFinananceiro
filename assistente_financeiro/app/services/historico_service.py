"""
Serviço de análise de histórico financeiro.

Gera comparações temporais, análise de tendências e
respostas para o assistente conversacional.
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, desc

from app.models import Transacao, Categoria
from app.utils.helpers import (
    calcular_percentual, formatar_moeda,
    periodo_label, nome_mes
)

logger = logging.getLogger(__name__)


class HistoricoService:
    """
    Serviço de análise histórica de transações.

    Funcionalidades:
      - Comparação entre meses
      - Análise de tendência de gastos
      - Histórico por categoria
      - Assistente conversacional básico
    """

    def __init__(self, db: Session):
        self.db = db

    # ================================================
    # Comparação de meses
    # ================================================

    def comparar_meses(
        self, mes1: int, ano1: int, mes2: int, ano2: int
    ) -> Dict[str, Any]:
        """
        Compara despesas, receitas e saldo entre dois meses.

        Returns:
            Dicionário com os valores de cada período e a variação percentual
        """
        def totais(mes, ano):
            dep = self._total_por_tipo(mes, ano, "debito")
            rec = self._total_por_tipo(mes, ano, "credito")
            return dep, rec, rec - dep

        dep1, rec1, saldo1 = totais(mes1, ano1)
        dep2, rec2, saldo2 = totais(mes2, ano2)

        def variacao(a, b):
            if b == 0:
                return None
            return round(((a - b) / b) * 100, 1)

        return {
            "periodo_1": {
                "label":     periodo_label(mes1, ano1),
                "despesas":  round(dep1, 2),
                "receitas":  round(rec1, 2),
                "saldo":     round(saldo1, 2),
            },
            "periodo_2": {
                "label":     periodo_label(mes2, ano2),
                "despesas":  round(dep2, 2),
                "receitas":  round(rec2, 2),
                "saldo":     round(saldo2, 2),
            },
            "variacao": {
                "despesas_perc": variacao(dep1, dep2),
                "receitas_perc": variacao(rec1, rec2),
                "saldo_perc":    variacao(saldo1, saldo2),
            },
        }

    # ================================================
    # Análise de tendência
    # ================================================

    def analisar_tendencia(self, n_meses: int = 6) -> Dict[str, Any]:
        """
        Analisa a tendência de gastos nos últimos N meses.

        Calcula se os gastos estão aumentando, diminuindo ou estáveis
        usando regressão linear simples.

        Returns:
            Dicionário com série histórica e tendência calculada
        """
        hoje = date.today()
        serie = []

        m, a = hoje.month, hoje.year
        for i in range(n_meses):
            despesas = self._total_por_tipo(m, a, "debito")
            receitas = self._total_por_tipo(m, a, "credito")
            serie.insert(0, {
                "mes":      periodo_label(m, a),
                "despesas": round(despesas, 2),
                "receitas": round(receitas, 2),
                "saldo":    round(receitas - despesas, 2),
            })
            m -= 1
            if m == 0:
                m, a = 12, a - 1

        # Tendência simples: compara primeira e segunda metade da série
        metade = n_meses // 2
        if metade >= 2:
            media_antiga  = sum(s["despesas"] for s in serie[:metade]) / metade
            media_recente = sum(s["despesas"] for s in serie[metade:]) / (n_meses - metade)

            if media_recente > media_antiga * 1.05:
                tendencia = "crescente"
            elif media_recente < media_antiga * 0.95:
                tendencia = "decrescente"
            else:
                tendencia = "estavel"
        else:
            tendencia = "insuficiente"

        return {
            "serie":     serie,
            "tendencia": tendencia,
            "n_meses":   n_meses,
        }

    # ================================================
    # Histórico por categoria
    # ================================================

    def historico_categoria(
        self, categoria_id: int, n_meses: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Retorna o histórico de gastos de uma categoria nos últimos N meses.

        Args:
            categoria_id: ID da categoria
            n_meses:      Número de meses para analisar

        Returns:
            Lista com o gasto em cada mês
        """
        hoje = date.today()
        resultado = []
        m, a = hoje.month, hoje.year

        for _ in range(n_meses):
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
            resultado.insert(0, {
                "mes":   periodo_label(m, a),
                "valor": round(float(r or 0), 2),
            })
            m -= 1
            if m == 0:
                m, a = 12, a - 1

        return resultado

    # ================================================
    # Assistente conversacional
    # ================================================

    def responder_pergunta(self, pergunta: str) -> Dict[str, Any]:
        """
        Interpreta perguntas em linguagem natural e retorna respostas.

        Perguntas suportadas:
          - "quanto gastei com X" / "gasto com X"
          - "qual foi minha maior despesa"
          - "estou gastando mais que no mês passado"
          - "total de gastos de janeiro"
          - "quais são minhas categorias"

        Args:
            pergunta: Texto da pergunta do usuário

        Returns:
            Dicionário com 'resposta' (texto) e 'dados' (opcionais)
        """
        p   = pergunta.lower().strip()
        hoje = date.today()
        mes, ano = hoje.month, hoje.year

        # ------ Quanto gastei com categoria X ------
        for cat in self.db.query(Categoria).all():
            if cat.nome.lower() in p:
                total = self._gasto_categoria(cat.id, mes, ano)
                return {
                    "resposta": (
                        f"Em {periodo_label(mes, ano)} você gastou "
                        f"{formatar_moeda(total)} com {cat.nome}."
                    ),
                    "dados": {"categoria": cat.nome, "valor": total},
                }

        # ------ Maior despesa ------
        if any(x in p for x in ["maior despesa", "maior gasto", "mais caro"]):
            t = (
                self.db.query(Transacao)
                .filter(
                    extract("month", Transacao.data) == mes,
                    extract("year",  Transacao.data) == ano,
                    Transacao.tipo == "debito",
                )
                .order_by(desc(Transacao.valor))
                .first()
            )
            if t:
                return {
                    "resposta": (
                        f"Sua maior despesa em {periodo_label(mes, ano)} foi "
                        f"'{t.descricao}' no dia {t.data.strftime('%d/%m')} "
                        f"no valor de {formatar_moeda(t.valor)}."
                    ),
                    "dados": {"descricao": t.descricao, "valor": t.valor, "data": str(t.data)},
                }
            return {"resposta": "Não encontrei despesas no período atual.", "dados": None}

        # ------ Comparação com mês anterior ------
        if any(x in p for x in ["mais que no mês passado", "comparado ao mês", "mês anterior"]):
            m_ant = mes - 1 if mes > 1 else 12
            a_ant = ano if mes > 1 else ano - 1
            atual     = self._total_por_tipo(mes, ano, "debito")
            anterior  = self._total_por_tipo(m_ant, a_ant, "debito")
            if anterior > 0:
                diff  = atual - anterior
                perc  = calcular_percentual(abs(diff), anterior)
                verbo = "mais" if diff > 0 else "menos"
                return {
                    "resposta": (
                        f"Em {periodo_label(mes, ano)} você gastou {formatar_moeda(atual)}, "
                        f"{perc:.1f}% {verbo} que em {periodo_label(m_ant, a_ant)} "
                        f"({formatar_moeda(anterior)})."
                    ),
                    "dados": {"atual": atual, "anterior": anterior, "diff": diff},
                }

        # ------ Total de gastos do mês ------
        if any(x in p for x in ["total de gastos", "quanto gastei", "gasto total"]):
            total = self._total_por_tipo(mes, ano, "debito")
            return {
                "resposta": f"Seus gastos totais em {periodo_label(mes, ano)} foram {formatar_moeda(total)}.",
                "dados":    {"total": total},
            }

        # ------ Quais categorias ------
        if any(x in p for x in ["categorias", "onde gasto", "categorizado"]):
            cats = self.db.query(Categoria).filter(Categoria.ativa == True).all()
            nomes = ", ".join(c.nome for c in cats)
            return {
                "resposta": f"Suas categorias são: {nomes}.",
                "dados":    {"categorias": [c.nome for c in cats]},
            }

        # ------ Fallback ------
        return {
            "resposta": (
                "Não entendi sua pergunta. Tente perguntar:\n"
                "• 'Quanto gastei com Alimentação?'\n"
                "• 'Qual foi minha maior despesa?'\n"
                "• 'Estou gastando mais que no mês passado?'\n"
                "• 'Qual o total de gastos do mês?'"
            ),
            "dados": None,
        }

    # --------------------------------------------------
    # Helpers internos
    # --------------------------------------------------

    def _total_por_tipo(self, mes: int, ano: int, tipo: str) -> float:
        r = (
            self.db.query(func.sum(Transacao.valor))
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.tipo == tipo,
            )
            .scalar()
        )
        return float(r or 0)

    def _gasto_categoria(self, categoria_id: int, mes: int, ano: int) -> float:
        r = (
            self.db.query(func.sum(Transacao.valor))
            .filter(
                extract("month", Transacao.data) == mes,
                extract("year",  Transacao.data) == ano,
                Transacao.categoria_id == categoria_id,
                Transacao.tipo == "debito",
            )
            .scalar()
        )
        return float(r or 0)
