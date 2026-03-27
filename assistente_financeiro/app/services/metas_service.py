"""
Serviço de metas e orçamentos financeiros.

Permite criar e acompanhar:
  - Metas financeiras (ex: poupar R$ 5.000 para viagem)
  - Orçamentos mensais por categoria (ex: max R$ 800 em Alimentação)
"""

import logging
from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models import Meta, Orcamento, Categoria, Transacao
from app.utils.helpers import calcular_percentual, formatar_moeda, periodo_label

logger = logging.getLogger(__name__)


class MetasService:
    """
    Serviço de gerenciamento de metas e orçamentos.

    Responsabilidades:
      - CRUD completo de Metas
      - CRUD completo de Orçamentos
      - Cálculo de progresso
      - Geração de alertas de limite
    """

    def __init__(self, db: Session):
        self.db = db

    # ================================================
    # METAS
    # ================================================

    def criar_meta(
        self,
        nome: str,
        valor_alvo: float,
        descricao: Optional[str] = None,
        valor_atual: float = 0.0,
        data_fim: Optional[date] = None,
        categoria_id: Optional[int] = None,
    ) -> Meta:
        """
        Cria uma nova meta financeira.

        Args:
            nome:         Nome da meta (ex: "Viagem Europa")
            valor_alvo:   Valor alvo a atingir
            descricao:    Descrição detalhada (opcional)
            valor_atual:  Valor já acumulado (padrão 0)
            data_fim:     Data limite para atingir a meta (opcional)
            categoria_id: ID da categoria associada (opcional)

        Returns:
            Objeto Meta criado e persistido
        """
        meta = Meta(
            nome=nome,
            descricao=descricao,
            valor_alvo=valor_alvo,
            valor_atual=valor_atual,
            data_fim=data_fim,
            categoria_id=categoria_id,
        )
        self.db.add(meta)
        self.db.commit()
        self.db.refresh(meta)
        logger.info(f"Meta criada: '{nome}' (alvo: {formatar_moeda(valor_alvo)})")
        return meta

    def listar_metas(self, apenas_ativas: bool = True) -> List[Meta]:
        """Retorna todas as metas (ativas por padrão)."""
        q = self.db.query(Meta)
        if apenas_ativas:
            q = q.filter(Meta.ativa == True)
        return q.order_by(Meta.criado_em.desc()).all()

    def obter_meta(self, meta_id: int) -> Optional[Meta]:
        """Busca uma meta pelo ID."""
        return self.db.query(Meta).filter(Meta.id == meta_id).first()

    def atualizar_progresso(self, meta_id: int, novo_valor: float) -> Optional[Meta]:
        """
        Atualiza o valor atual de uma meta.
        Marca como concluída automaticamente se atingir o alvo.

        Args:
            meta_id:    ID da meta
            novo_valor: Novo valor acumulado

        Returns:
            Meta atualizada ou None se não encontrada
        """
        meta = self.obter_meta(meta_id)
        if not meta:
            return None

        meta.valor_atual = novo_valor
        if novo_valor >= meta.valor_alvo:
            meta.concluida = True
            logger.info(f"Meta '{meta.nome}' concluída! 🎉")

        self.db.commit()
        self.db.refresh(meta)
        return meta

    def incrementar_progresso(self, meta_id: int, incremento: float) -> Optional[Meta]:
        """
        Adiciona um valor ao progresso atual da meta.

        Args:
            meta_id:    ID da meta
            incremento: Valor a adicionar

        Returns:
            Meta atualizada ou None
        """
        meta = self.obter_meta(meta_id)
        if not meta:
            return None
        return self.atualizar_progresso(meta_id, meta.valor_atual + incremento)

    def excluir_meta(self, meta_id: int) -> bool:
        """
        Remove uma meta (soft delete: marca como inativa).

        Returns:
            True se removida, False se não encontrada
        """
        meta = self.obter_meta(meta_id)
        if not meta:
            return False
        meta.ativa = False
        self.db.commit()
        return True

    def resumo_metas(self) -> List[Dict[str, Any]]:
        """
        Retorna resumo de todas as metas ativas com progresso calculado.
        """
        metas = self.listar_metas()
        return [
            {
                "id":                   m.id,
                "nome":                 m.nome,
                "valor_alvo":           m.valor_alvo,
                "valor_atual":          m.valor_atual,
                "percentual":           round(m.percentual_concluido, 1),
                "falta":                max(m.valor_alvo - m.valor_atual, 0),
                "concluida":            m.concluida,
                "data_fim":             str(m.data_fim) if m.data_fim else None,
            }
            for m in metas
        ]

    # ================================================
    # ORÇAMENTOS
    # ================================================

    def criar_orcamento(
        self,
        categoria_id: int,
        valor_limite: float,
        mes: int,
        ano: int,
        alerta_percentual: float = 80.0,
    ) -> Orcamento:
        """
        Cria um orçamento mensal para uma categoria.

        Args:
            categoria_id:      ID da categoria
            valor_limite:      Limite máximo de gastos
            mes:               Mês (1-12)
            ano:               Ano (ex: 2024)
            alerta_percentual: % de uso que dispara o aviso (padrão 80%)

        Returns:
            Objeto Orcamento criado
        """
        # Remove orçamento anterior para o mesmo período/categoria
        existente = (
            self.db.query(Orcamento)
            .filter(
                Orcamento.categoria_id == categoria_id,
                Orcamento.mes == mes,
                Orcamento.ano == ano,
            )
            .first()
        )
        if existente:
            existente.valor_limite      = valor_limite
            existente.alerta_percentual = alerta_percentual
            self.db.commit()
            self.db.refresh(existente)
            return existente

        orc = Orcamento(
            categoria_id=categoria_id,
            valor_limite=valor_limite,
            mes=mes,
            ano=ano,
            alerta_percentual=alerta_percentual,
        )
        self.db.add(orc)
        self.db.commit()
        self.db.refresh(orc)
        return orc

    def listar_orcamentos(self, mes: int, ano: int) -> List[Orcamento]:
        """Lista todos os orçamentos de um período."""
        return (
            self.db.query(Orcamento)
            .filter(Orcamento.mes == mes, Orcamento.ano == ano)
            .all()
        )

    def excluir_orcamento(self, orcamento_id: int) -> bool:
        """Remove um orçamento pelo ID."""
        orc = self.db.query(Orcamento).filter(Orcamento.id == orcamento_id).first()
        if not orc:
            return False
        self.db.delete(orc)
        self.db.commit()
        return True

    def resumo_orcamentos(self, mes: int, ano: int) -> List[Dict[str, Any]]:
        """
        Retorna o resumo dos orçamentos do período com o gasto realizado.

        Returns:
            Lista com limite, gasto, percentual e status de cada orçamento
        """
        orcamentos = self.listar_orcamentos(mes, ano)
        resultado  = []

        for orc in orcamentos:
            gasto = self._gasto_categoria_periodo(orc.categoria_id, mes, ano)
            perc  = calcular_percentual(gasto, orc.valor_limite)
            nome_cat = orc.categoria.nome if orc.categoria else f"ID {orc.categoria_id}"

            if perc >= 100:
                status = "estourado"
            elif perc >= orc.alerta_percentual:
                status = "alerta"
            else:
                status = "ok"

            resultado.append({
                "id":           orc.id,
                "categoria":    nome_cat,
                "limite":       orc.valor_limite,
                "gasto":        round(gasto, 2),
                "percentual":   round(perc, 1),
                "disponivel":   round(max(orc.valor_limite - gasto, 0), 2),
                "status":       status,
            })

        return resultado

    # --------------------------------------------------
    # Helper interno
    # --------------------------------------------------

    def _gasto_categoria_periodo(
        self, categoria_id: int, mes: int, ano: int
    ) -> float:
        """Soma os gastos (débitos) de uma categoria em um período."""
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
