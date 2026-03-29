"""
Serviço de Agenda Financeira, Compromissos e Planner.
Gerencia CRUD e consultas de EventoFinanceiro, Compromisso e TarefaPlanner.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import re
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models import (
    EventoFinanceiro, StatusEvento, TipoEvento,
    Compromisso,
    TarefaPlanner, StatusTarefa, PrioridadeTarefa, AreaTarefa,
    Transacao, TipoTransacao, FormaPagamento,
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

    if ev.transacao_id is None and ev.tipo in {TipoEvento.CONTA, TipoEvento.PARCELA, TipoEvento.OUTRO}:
        forma_pagamento = _inferir_forma_pagamento_evento(ev)
        transacao = Transacao(
            data=ev.pago_em.date(),
            descricao=ev.titulo,
            valor=abs(float(ev.valor or 0.0)),
            tipo=TipoTransacao.DEBITO,
            observacao=ev.descricao,
            forma_pagamento=forma_pagamento,
            fonte="agenda_financeira",
            categoria_id=ev.categoria_id,
            conta_id=ev.conta_id,
            cartao_id=ev.cartao_id,
        )
        db.add(transacao)
        db.flush()
        ev.transacao_id = transacao.id

    # Cria próxima ocorrência se recorrente
    if ev.recorrente and ev.dia_recorrencia:
        _criar_proxima_recorrencia(db, ev)
    db.commit()
    db.refresh(ev)
    return ev


def quitar_evento(
    db: Session,
    evento_id: int,
    *,
    conta_id: int | None = None,
    cartao_id: int | None = None,
    forma_pagamento: str | None = None,
    data_pagamento: date | None = None,
    descricao_transacao: str | None = None,
) -> Optional[EventoFinanceiro]:
    ev = db.query(EventoFinanceiro).get(evento_id)
    if not ev:
        return None

    if conta_id is not None:
        ev.conta_id = conta_id
    if cartao_id is not None:
        ev.cartao_id = cartao_id

    ev.status = StatusEvento.PAGO if ev.tipo != TipoEvento.RECEITA else StatusEvento.RECEBIDO
    instante_pagamento = datetime.utcnow()
    if data_pagamento is not None:
        instante_pagamento = datetime.combine(data_pagamento, datetime.min.time())
    ev.pago_em = instante_pagamento

    if ev.tipo == TipoEvento.FATURA_CARTAO:
        db.commit()
        db.refresh(ev)
        return ev

    if ev.transacao_id is None and ev.tipo in {TipoEvento.CONTA, TipoEvento.PARCELA, TipoEvento.OUTRO}:
        forma = _coagir_forma_pagamento(forma_pagamento) or _inferir_forma_pagamento_evento(ev)
        transacao = Transacao(
            data=instante_pagamento.date(),
            descricao=descricao_transacao or ev.titulo,
            valor=abs(float(ev.valor or 0.0)),
            tipo=TipoTransacao.DEBITO,
            observacao=ev.descricao,
            forma_pagamento=forma,
            fonte="agenda_financeira",
            categoria_id=ev.categoria_id,
            conta_id=ev.conta_id,
            cartao_id=ev.cartao_id,
        )
        db.add(transacao)
        db.flush()
        ev.transacao_id = transacao.id

    if ev.recorrente and ev.dia_recorrencia:
        _criar_proxima_recorrencia(db, ev)

    db.commit()
    db.refresh(ev)
    return ev


def _coagir_forma_pagamento(valor: str | None) -> FormaPagamento | None:
    if not valor:
        return None
    try:
        return FormaPagamento(valor)
    except ValueError:
        return None


def _inferir_forma_pagamento_evento(ev: EventoFinanceiro) -> FormaPagamento:
    if ev.cartao_id:
        return FormaPagamento.CARTAO_CREDITO
    if ev.codigo_barras:
        return FormaPagamento.BOLETO_CONTA
    if ev.conta_id:
        return FormaPagamento.PIX_TRANSFERENCIA
    return FormaPagamento.DINHEIRO


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
    return q.order_by(TarefaPlanner.data, TarefaPlanner.hora_inicio, TarefaPlanner.prioridade).all()


def criar_tarefa(db: Session, dados: Dict[str, Any]) -> TarefaPlanner:
    dados = _normalizar_campos_horario_tarefa(dados)
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
        payload = _normalizar_campos_horario_tarefa({**base, "data": d})
        t = TarefaPlanner(**payload)
        db.add(t)
        criadas.append(t)
    db.commit()
    return criadas


def atualizar_tarefa(db: Session, tarefa_id: int, dados: Dict[str, Any]) -> Optional[TarefaPlanner]:
    t = db.query(TarefaPlanner).get(tarefa_id)
    if not t:
        return None
    dados = _normalizar_campos_horario_tarefa(dados)
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


def _normalizar_campos_horario_tarefa(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Padroniza hora_inicio/hora_fim/duracao_min para manter consistência no planner."""
    if not dados:
        return dados

    payload = dict(dados)

    hi = payload.get("hora_inicio")
    hf = payload.get("hora_fim")
    dur = payload.get("duracao_min")

    def _parse_hhmm(valor: Any) -> Optional[tuple[int, int]]:
        if valor is None:
            return None
        texto = str(valor).strip()
        if not texto:
            return None
        if not re.match(r"^\d{2}:\d{2}$", texto):
            return None
        h, m = texto.split(":", 1)
        h_i = int(h)
        m_i = int(m)
        if not (0 <= h_i <= 23 and 0 <= m_i <= 59):
            return None
        return h_i, m_i

    hi_t = _parse_hhmm(hi)
    hf_t = _parse_hhmm(hf)

    if dur is not None:
        try:
            dur_i = int(dur)
            payload["duracao_min"] = max(1, dur_i)
        except Exception:
            payload["duracao_min"] = None

    if hi_t and hf_t:
        inicio = hi_t[0] * 60 + hi_t[1]
        fim = hf_t[0] * 60 + hf_t[1]
        if fim <= inicio:
            fim += 24 * 60
        payload["duracao_min"] = fim - inicio
    elif hi_t and payload.get("duracao_min"):
        total = int(payload["duracao_min"])
        inicio = hi_t[0] * 60 + hi_t[1]
        fim = (inicio + total) % (24 * 60)
        payload["hora_fim"] = f"{fim // 60:02d}:{fim % 60:02d}"
    elif hi_t and not hf_t and payload.get("duracao_min") is None:
        payload["duracao_min"] = 60

    return payload
