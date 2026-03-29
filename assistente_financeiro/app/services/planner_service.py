"""
Service para Planner inteligente com IA.

Funcionalidades:
  - Organizar tarefas por horário (IA Vorcaro)
  - Gamificação: pontos, badges, levels
  - Suporte a 3 visualizações: Timeline, SmartPlanner, Kanban
  - Planejamento semanal/mensal
"""

import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from app.models import (
    TarefaPlanner, PontuacaoUsuario, Badge, BadgeDesbloqueada,
    MetaFinanceiraGamificada, Meta, EventoFinanceiro,
    StatusTarefa, PrioridadeTarefa, AreaTarefa
)
from app.database import get_db


class PlannerService:
    """Service de Planner inteligente com IA."""

    def __init__(self, db: Session):
        self.db = db

    # ================================================
    # TAREFAS - CRUD
    # ================================================

    def criar_tarefa(
        self,
        titulo: str,
        descricao: Optional[str] = None,
        data: Optional[date] = None,
        hora_inicio: Optional[str] = None,
        hora_fim: Optional[str] = None,
        prioridade: str = "media",
        area: str = "pessoal",
        organizacao_id: int = 1,
    ) -> Dict[str, Any]:
        """Cria nova tarefa no planner."""
        tarefa = TarefaPlanner(
            organizacao_id=organizacao_id,
            titulo=titulo,
            descricao=descricao,
            data=data,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            prioridade=prioridade,
            area=area,
            status=StatusTarefa.A_FAZER,
        )
        self.db.add(tarefa)
        self.db.commit()
        self.db.refresh(tarefa)
        return self._tarefa_dict(tarefa)

    def listar_tarefas_dia(self, data: date, organizacao_id: int = 1) -> List[Dict[str, Any]]:
        """Lista tarefas de um dia específico, ordenadas por horário."""
        tarefas = (
            self.db.query(TarefaPlanner)
            .filter(
                TarefaPlanner.organizacao_id == organizacao_id,
                TarefaPlanner.data == data,
            )
            .order_by(TarefaPlanner.hora_inicio)
            .all()
        )
        return [self._tarefa_dict(t) for t in tarefas]

    def listar_tarefas_semana(self, data_inicio: date, organizacao_id: int = 1) -> List[Dict[str, Any]]:
        """Lista tarefas de uma semana completa."""
        data_fim = data_inicio + timedelta(days=7)
        tarefas = (
            self.db.query(TarefaPlanner)
            .filter(
                TarefaPlanner.organizacao_id == organizacao_id,
                TarefaPlanner.data >= data_inicio,
                TarefaPlanner.data < data_fim,
            )
            .order_by(TarefaPlanner.data, TarefaPlanner.hora_inicio)
            .all()
        )
        return [self._tarefa_dict(t) for t in tarefas]

    def completar_tarefa(self, tarefa_id: int) -> Dict[str, Any]:
        """Marca tarefa como concluída e ganha pontos."""
        tarefa = self.db.query(TarefaPlanner).filter(TarefaPlanner.id == tarefa_id).first()
        if not tarefa:
            raise ValueError(f"Tarefa {tarefa_id} não encontrada")

        tarefa.status = StatusTarefa.CONCLUIDO
        tarefa.concluido_em = datetime.utcnow()
        self.db.commit()
        self.db.refresh(tarefa)

        # Ganhar pontos
        pontos_ganhos = self._calcular_pontos_tarefa(tarefa)
        self._adicionar_pontos(tarefa.organizacao_id, pontos_ganhos)

        return self._tarefa_dict(tarefa)

    def atualizar_tarefa(
        self,
        tarefa_id: int,
        *,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        data: Optional[date] = None,
        hora_inicio: Optional[str] = None,
        hora_fim: Optional[str] = None,
        prioridade: Optional[str] = None,
        area: Optional[str] = None,
        status: Optional[str] = None,
        organizacao_id: int = 1,
    ) -> Dict[str, Any]:
        """Atualiza campos de uma tarefa existente."""
        tarefa = (
            self.db.query(TarefaPlanner)
            .filter(
                TarefaPlanner.id == tarefa_id,
                TarefaPlanner.organizacao_id == organizacao_id,
            )
            .first()
        )
        if not tarefa:
            raise ValueError(f"Tarefa {tarefa_id} não encontrada")

        if titulo is not None:
            titulo = titulo.strip()
            if not titulo:
                raise ValueError("Título da tarefa não pode ser vazio")
            tarefa.titulo = titulo

        if descricao is not None:
            tarefa.descricao = descricao.strip() or None

        if data is not None:
            tarefa.data = data

        if hora_inicio is not None:
            tarefa.hora_inicio = (hora_inicio or "").strip() or None

        if hora_fim is not None:
            tarefa.hora_fim = (hora_fim or "").strip() or None

        if prioridade is not None:
            try:
                tarefa.prioridade = PrioridadeTarefa(prioridade)
            except Exception as exc:
                raise ValueError(f"Prioridade inválida: {prioridade}") from exc

        if area is not None:
            try:
                tarefa.area = AreaTarefa(area)
            except Exception as exc:
                raise ValueError(f"Área inválida: {area}") from exc

        if status is not None:
            try:
                tarefa.status = StatusTarefa(status)
            except Exception as exc:
                raise ValueError(f"Status inválido: {status}") from exc

            if tarefa.status == StatusTarefa.CONCLUIDO:
                tarefa.concluido_em = datetime.utcnow()
            else:
                tarefa.concluido_em = None

        self.db.commit()
        self.db.refresh(tarefa)
        return self._tarefa_dict(tarefa)

    def excluir_tarefa(self, tarefa_id: int, organizacao_id: int = 1) -> Dict[str, Any]:
        """Remove uma tarefa existente do planner."""
        tarefa = (
            self.db.query(TarefaPlanner)
            .filter(
                TarefaPlanner.id == tarefa_id,
                TarefaPlanner.organizacao_id == organizacao_id,
            )
            .first()
        )
        if not tarefa:
            raise ValueError(f"Tarefa {tarefa_id} não encontrada")

        titulo = tarefa.titulo
        self.db.delete(tarefa)
        self.db.commit()
        return {"id": tarefa_id, "titulo": titulo}

    # ================================================
    # IA - ORGANIZAR TAREFAS
    # ================================================

    def organizar_tarefas_com_ia(
        self,
        tarefas_texto: str,
        data_inicio: date,
        area: str = "pessoal",
        organizacao_id: int = 1,
    ) -> Dict[str, Any]:
        """
        Recebe tarefas em texto livre e IA (Vorcaro) organiza por horário.
        
        Exemplo entrada:
        - Academia (1h30)
        - Email trabalho
        - Almoço
        - Reunião com chefe
        - Responder Whatsapp
        
        Retorna agenda organizada por horão.
        """
        # TODO: Integrar com Vorcaro (IA)
        # Por enquanto, retorna um exemplo
        tarefas = self._parsear_tarefas_texto(tarefas_texto)
        agenda_organizada = self._organizar_por_horario(tarefas, data_inicio)

        # Salvar no BD
        tarefas_criadas = []
        for item in agenda_organizada:
            tarefa = self.criar_tarefa(
                titulo=item["titulo"],
                descricao=item.get("descricao"),
                data=item["data"],
                hora_inicio=item.get("hora_inicio"),
                hora_fim=item.get("hora_fim"),
                prioridade=item.get("prioridade", "media"),
                area=area,
                organizacao_id=organizacao_id,
            )
            tarefas_criadas.append(tarefa)

        return {
            "sucesso": True,
            "mensagem": f"✨ Vorcaro organizou suas {len(tarefas_criadas)} tarefas!",
            "tarefas": tarefas_criadas,
        }

    # ================================================
    # GAMIFICAÇÃO
    # ================================================

    def obter_pontuacao(self, organizacao_id: int = 1) -> Dict[str, Any]:
        """Obtém pontuação atual do usuário."""
        pont = (
            self.db.query(PontuacaoUsuario)
            .filter(PontuacaoUsuario.organizacao_id == organizacao_id)
            .first()
        )
        if not pont:
            pont = PontuacaoUsuario(organizacao_id=organizacao_id)
            self.db.add(pont)
            self.db.commit()
            self.db.refresh(pont)

        return {
            "nivel": pont.nivel,
            "pontos": pont.pontos_total,
            "xp": pont.xp_total,
            "xp_para_proximo": pont.xp_proximo_nivel - pont.xp_para_nivel,
            "barra_progresso": (pont.xp_para_nivel / pont.xp_proximo_nivel) * 100,
        }

    def _adicionar_pontos(self, organizacao_id: int, pontos: int, xp: int = None) -> None:
        """Adiciona pontos e XP ao usuário."""
        if xp is None:
            xp = int(pontos * 0.5)  # 1 XP = 2 pontos

        pont = (
            self.db.query(PontuacaoUsuario)
            .filter(PontuacaoUsuario.organizacao_id == organizacao_id)
            .first()
        )
        if not pont:
            pont = PontuacaoUsuario(organizacao_id=organizacao_id)
            self.db.add(pont)

        pont.pontos_total += pontos
        pont.xp_para_nivel += xp

        # Verificar levelup
        while pont.xp_para_nivel >= pont.xp_proximo_nivel:
            pont.xp_para_nivel -= pont.xp_proximo_nivel
            pont.nivel += 1
            pont.xp_proximo_nivel = int(pont.xp_proximo_nivel * 1.1)  # Aumenta 10%

        self.db.commit()

    def _calcular_pontos_tarefa(self, tarefa: TarefaPlanner) -> int:
        """Calcula pontos baseado em prioridade e duração."""
        base_points = {
            PrioridadeTarefa.ALTA: 100,
            PrioridadeTarefa.MEDIA: 50,
            PrioridadeTarefa.BAIXA: 25,
        }
        points = base_points.get(tarefa.prioridade, 50)

        # Bônus por duração
        if tarefa.hora_inicio and tarefa.hora_fim:
            try:
                h_ini = int(tarefa.hora_inicio.split(":")[0])
                h_fim = int(tarefa.hora_fim.split(":")[0])
                duracao = h_fim - h_ini
                if duracao > 2:
                    points += 50  # Tarefas longas = mais pontos
            except:
                pass

        return points

    # ================================================
    # BADGES E CONQUISTAS
    # ================================================

    def verificar_badges(self, organizacao_id: int = 1) -> List[Dict[str, Any]]:
        """Verifica e desbloqueia badges quando critérios são atingidos."""
        badges_novas = []

        # Exemplo: "7 tarefas concluídas"
        tarefas_concluidas = (
            self.db.query(TarefaPlanner)
            .filter(
                TarefaPlanner.organizacao_id == organizacao_id,
                TarefaPlanner.status == StatusTarefa.CONCLUIDO,
            )
            .count()
        )

        if tarefas_concluidas >= 7:
            badge = self._desbloquear_badge("produtivo_7", organizacao_id)
            if badge:
                badges_novas.append(badge)

        if tarefas_concluidas >= 30:
            badge = self._desbloquear_badge("super_produtivo_30", organizacao_id)
            if badge:
                badges_novas.append(badge)

        return badges_novas

    def _desbloquear_badge(self, nome_badge: str, organizacao_id: int) -> Optional[Dict]:
        """Desbloqueia um badge se ainda não tiver."""
        badge = self.db.query(Badge).filter(Badge.nome == nome_badge).first()
        if not badge:
            return None

        # Verificar se já tem
        ja_tem = (
            self.db.query(BadgeDesbloqueada)
            .filter(
                BadgeDesbloqueada.organizacao_id == organizacao_id,
                BadgeDesbloqueada.badge_id == badge.id,
            )
            .first()
        )
        if ja_tem:
            return None

        # Desbloquear
        desbloqueada = BadgeDesbloqueada(
            organizacao_id=organizacao_id,
            badge_id=badge.id,
        )
        self.db.add(desbloqueada)
        self.db.commit()
        self.db.refresh(desbloqueada)

        # Adicionar pontos
        self._adicionar_pontos(organizacao_id, badge.pontos, badge.xp)

        return {
            "nome": badge.nome,
            "descricao": badge.descricao,
            "icone": badge.icone,
            "pontos": badge.pontos,
        }

    # ================================================
    # VISUALIZAÇÕES (Timeline, SmartPlanner, Kanban)
    # ================================================

    def gerar_timeline(self, data: date, organizacao_id: int = 1) -> Dict[str, Any]:
        """Gera visualização de timeline por horário."""
        tarefas = self.listar_tarefas_dia(data, organizacao_id)

        timeline = {}
        for hora in range(6, 23):  # 6h até 22h
            hora_str = f"{hora:02d}:00"
            timeline[hora_str] = []

        for tarefa in tarefas:
            if tarefa["hora_inicio"]:
                hora_str = f"{tarefa['hora_inicio'][:2]}:00"
                if hora_str in timeline:
                    timeline[hora_str].append(tarefa)

        return {
            "tipo": "timeline",
            "data": str(data),
            "timeline": timeline,
        }

    def gerar_kanban(self, data_inicio: date, organizacao_id: int = 1) -> Dict[str, Any]:
        """Gera visualização kanban (A fazer, Em progresso, Concluído)."""
        tarefas = self.listar_tarefas_semana(data_inicio, organizacao_id)

        kanban = {
            "a_fazer": [],
            "em_progresso": [],
            "concluido": [],
        }

        for tarefa in tarefas:
            status = tarefa["status"]
            if status == "a_fazer":
                kanban["a_fazer"].append(tarefa)
            elif status == "em_progresso":
                kanban["em_progresso"].append(tarefa)
            else:
                kanban["concluido"].append(tarefa)

        return {
            "tipo": "kanban",
            "semana_inicio": str(data_inicio),
            "colunas": kanban,
        }

    # ================================================
    # HELPERS
    # ================================================

    def _tarefa_dict(self, tarefa: TarefaPlanner) -> Dict[str, Any]:
        """Converte tarefa para dict."""
        return {
            "id": tarefa.id,
            "titulo": tarefa.titulo,
            "descricao": tarefa.descricao,
            "data": str(tarefa.data) if tarefa.data else None,
            "hora_inicio": tarefa.hora_inicio,
            "hora_fim": tarefa.hora_fim,
            "prioridade": tarefa.prioridade,
            "status": tarefa.status,
            "area": tarefa.area,
            "concluido_em": str(tarefa.concluido_em) if tarefa.concluido_em else None,
        }

    def _parsear_tarefas_texto(self, texto: str) -> List[Dict[str, str]]:
        """Parse tarefas em texto livre (linhas separadas por \n ou -)."""
        linhas = [l.strip().lstrip("- •") for l in texto.split("\n") if l.strip()]
        return [{"titulo": l} for l in linhas]

    def _organizar_por_horario(
        self, tarefas: List[Dict[str, str]], data_inicio: date
    ) -> List[Dict[str, Any]]:
        """
        IA simples para organizar tarefas por horário.
        TODO: Integrar com Vorcaro para IA real.
        """
        agenda = []
        hora_atual = 8  # Começa 8h

        for tarefa in tarefas:
            titulo = tarefa.get("titulo", "")

            # Estimar duração baseado em palavras-chave
            duracao = 1
            if any(word in titulo.lower() for word in ["academia", "exercício", "treino"]):
                duracao = 1.5
            elif any(word in titulo.lower() for word in ["almoço", "café", "refeição"]):
                duracao = 1
            elif any(word in titulo.lower() for word in ["reunião", "meeting"]):
                duracao = 1
            else:
                duracao = 0.5

            hora_fim = hora_atual + duracao
            hora_inicio_str = f"{int(hora_atual):02d}:{int((hora_atual % 1) * 60):02d}"
            hora_fim_str = f"{int(hora_fim):02d}:{int((hora_fim % 1) * 60):02d}"

            agenda.append({
                "titulo": titulo,
                "data": data_inicio,
                "hora_inicio": hora_inicio_str,
                "hora_fim": hora_fim_str,
                "prioridade": "media",
            })

            hora_atual = hora_fim + 0.25  # 15 min de intervalo

        return agenda
