"""
Serviço de Agenda Financeira, Compromissos e Planner.
Gerencia CRUD e consultas de EventoFinanceiro, Compromisso e TarefaPlanner.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models import (
    EventoFinanceiro, StatusEvento, TipoEvento,
    Compromisso,
    TarefaPlanner, StatusTarefa, PrioridadeTarefa, AreaTarefa,
)


# ================================================
# Agenda Financeira
# ================================================

def listar_eventos(db: Session,
                   mes: int | None = None,
                   ano: int | None = None) -> List[EventoFinanceiro]:
    """Retorna eventos financeiros do mês/ano informado (ou todos)."""
    q = db.query(EventoFinanceiro)
    if mes and ano:
        inicio = date(ano, mes, 1)
        fim    = date(ano, mes, calendar.monthrange(ano, mes)[1])
        q = q.filter(EventoFinanceiro.data_vencimento.between(inicio, fim))
    return q.order_by(EventoFinanceiro.data_vencimento).all()


def listar_proximos_eventos(db: Session, dias: int = 30) -> List[EventoFinanceiro]:
    """Retorna eventos dos próximos N dias pendentes ou atrasados."""
    hoje  = date.today()
    limite = hoje + timedelta(days=dias)
    return (
        db.query(EventoFinanceiro)
        .filter(
            EventoFinanceiro.data_vencimento.between(hoje - timedelta(days=7), limite),
            EventoFinanceiro.status.in_([StatusEvento.PENDENTE, StatusEvento.ATRASADO]),
        )
        .order_by(EventoFinanceiro.data_vencimento)
        .all()
    )


def criar_evento(db: Session, dados: Dict[str, Any]) -> EventoFinanceiro:
    evento = EventoFinanceiro(**dados)
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


def atualizar_evento(db: Session, evento_id: int, dados: Dict[str, Any]) -> Optional[EventoFinanceiro]:
    ev = db.query(EventoFinanceiro).get(evento_id)
    if not ev:
        return None
    for k, v in dados.items():
        setattr(ev, k, v)
    db.commit()
    db.refresh(ev)
    return ev


def marcar_pago(db: Session, evento_id: int) -> Optional[EventoFinanceiro]:
    ev = db.query(EventoFinanceiro).get(evento_id)
    if not ev:
        return None
    ev.status  = StatusEvento.PAGO if ev.tipo != TipoEvento.RECEITA else StatusEvento.RECEBIDO
    ev.pago_em = datetime.utcnow()
    # Cria próxima ocorrência se recorrente
    if ev.recorrente and ev.dia_recorrencia:
        _criar_proxima_recorrencia(db, ev)
    db.commit()
    db.refresh(ev)
    return ev


def _criar_proxima_recorrencia(db: Session, ev: EventoFinanceiro):
    prox_mes = ev.data_vencimento.month + 1
    prox_ano = ev.data_vencimento.year
    if prox_mes > 12:
        prox_mes = 1
        prox_ano += 1
    ult_dia  = calendar.monthrange(prox_ano, prox_mes)[1]
    dia_alvo = min(ev.dia_recorrencia, ult_dia)
    nova_data = date(prox_ano, prox_mes, dia_alvo)
    novo = EventoFinanceiro(
        titulo          = ev.titulo,
        descricao       = ev.descricao,
        valor           = ev.valor,
        data_vencimento = nova_data,
        tipo            = ev.tipo,
        status          = StatusEvento.PENDENTE,
        recorrente      = True,
        dia_recorrencia = ev.dia_recorrencia,
        categoria_id    = ev.categoria_id,
    )
    db.add(novo)


def excluir_evento(db: Session, evento_id: int) -> bool:
    ev = db.query(EventoFinanceiro).get(evento_id)
    if not ev:
        return False
    db.delete(ev)
    db.commit()
    return True


def atualizar_status_atrasados(db: Session):
    """Marca como ATRASADO todos os eventos PENDENTES com vencimento passado."""
    hoje = date.today()
    pendentes = (
        db.query(EventoFinanceiro)
        .filter(
            EventoFinanceiro.status == StatusEvento.PENDENTE,
            EventoFinanceiro.data_vencimento < hoje,
        )
        .all()
    )
    for ev in pendentes:
        ev.status = StatusEvento.ATRASADO
    db.commit()
    return len(pendentes)


# ================================================
# Agenda de Compromissos
# ================================================

def listar_compromissos(db: Session,
                        mes: int | None = None,
                        ano: int | None = None) -> List[Compromisso]:
    q = db.query(Compromisso)
    if mes and ano:
        inicio = date(ano, mes, 1)
        fim    = date(ano, mes, calendar.monthrange(ano, mes)[1])
        q = q.filter(Compromisso.data.between(inicio, fim))
    return q.order_by(Compromisso.data, Compromisso.hora_inicio).all()


def listar_compromissos_dia(db: Session, dia: date) -> List[Compromisso]:
    return (
        db.query(Compromisso)
        .filter(Compromisso.data == dia)
        .order_by(Compromisso.hora_inicio)
        .all()
    )


def criar_compromisso(db: Session, dados: Dict[str, Any]) -> Compromisso:
    comp = Compromisso(**dados)
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


def atualizar_compromisso(db: Session, comp_id: int, dados: Dict[str, Any]) -> Optional[Compromisso]:
    comp = db.query(Compromisso).get(comp_id)
    if not comp:
        return None
    for k, v in dados.items():
        setattr(comp, k, v)
    db.commit()
    db.refresh(comp)
    return comp


def excluir_compromisso(db: Session, comp_id: int) -> bool:
    comp = db.query(Compromisso).get(comp_id)
    if not comp:
        return False
    db.delete(comp)
    db.commit()
    return True


# ================================================
# Planner
# ================================================

def listar_tarefas(db: Session,
                   data: date | None = None,
                   semana_inicio: date | None = None) -> List[TarefaPlanner]:
    q = db.query(TarefaPlanner)
    if data:
        q = q.filter(TarefaPlanner.data == data)
    elif semana_inicio:
        semana_fim = semana_inicio + timedelta(days=6)
        q = q.filter(TarefaPlanner.data.between(semana_inicio, semana_fim))
    return q.order_by(TarefaPlanner.data, TarefaPlanner.prioridade).all()


def criar_tarefa(db: Session, dados: Dict[str, Any]) -> TarefaPlanner:
    tarefa = TarefaPlanner(**dados)
    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)
    return tarefa


def criar_multiplas_tarefas(
    db: Session,
    base: Dict[str, Any],
    datas: List[date],
) -> List["TarefaPlanner"]:
    """
    Cria a mesma tarefa (título, descrição, prioridade, área, status) em
    múltiplas datas de uma só vez.  Nenhum commit individual — faz tudo num
    único commit ao final para eficiência.
    """
    criadas = []
    for d in datas:
        t = TarefaPlanner(**{**base, "data": d})
        db.add(t)
        criadas.append(t)
    db.commit()
    return criadas


def atualizar_tarefa(db: Session, tarefa_id: int, dados: Dict[str, Any]) -> Optional[TarefaPlanner]:
    t = db.query(TarefaPlanner).get(tarefa_id)
    if not t:
        return None
    for k, v in dados.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


def concluir_tarefa(db: Session, tarefa_id: int) -> Optional[TarefaPlanner]:
    t = db.query(TarefaPlanner).get(tarefa_id)
    if not t:
        return None
    t.status       = StatusTarefa.CONCLUIDO
    t.concluido_em = datetime.utcnow()
    db.commit()
    db.refresh(t)
    return t


def excluir_tarefa(db: Session, tarefa_id: int) -> bool:
    t = db.query(TarefaPlanner).get(tarefa_id)
    if not t:
        return False
    db.delete(t)
    db.commit()
    return True


def resumo_semana(db: Session, semana_inicio: date) -> Dict[str, Any]:
    tarefas = listar_tarefas(db, semana_inicio=semana_inicio)
    total   = len(tarefas)
    concluidas = sum(1 for t in tarefas if t.status == StatusTarefa.CONCLUIDO)
    return {
        "total": total,
        "concluidas": concluidas,
        "pendentes": total - concluidas,
        "por_area": {
            area.value: [t for t in tarefas if t.area == area]
            for area in AreaTarefa
        },
        "por_prioridade": {
            p.value: [t for t in tarefas if t.prioridade == p]
            for p in PrioridadeTarefa
        },
    }
