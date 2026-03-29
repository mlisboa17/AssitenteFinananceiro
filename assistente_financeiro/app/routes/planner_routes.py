"""
Rotas REST da API para Planner.

Fonte unica dos endpoints /planner para evitar duplicidade com app.main.
"""

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.planner_service import PlannerService


class TarefaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data: Optional[str] = None  # YYYY-MM-DD
    hora_inicio: Optional[str] = None  # HH:MM
    hora_fim: Optional[str] = None
    prioridade: str = "media"
    area: str = "pessoal"
    organizacao_id: int = 1


class TarefaUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    data: Optional[str] = None  # YYYY-MM-DD
    hora_inicio: Optional[str] = None
    hora_fim: Optional[str] = None
    prioridade: Optional[str] = None
    area: Optional[str] = None
    status: Optional[str] = None
    organizacao_id: int = 1


class OrganizarTarefasRequest(BaseModel):
    # Compatibilidade com payload novo e legado
    texto: Optional[str] = None
    tarefas_texto: Optional[str] = None
    data: Optional[str] = None
    data_inicio: Optional[str] = None
    area: str = "pessoal"
    organizacao_id: int = 1


router = APIRouter(prefix="/planner", tags=["Planner"])


def _parse_data_yyyy_mm_dd(data_txt: str) -> date:
    return datetime.strptime(data_txt, "%Y-%m-%d").date()


def _normalizar_horarios(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    timeline_map = payload.get("timeline", {}) if isinstance(payload, dict) else {}
    return [{"hora": hora, "tarefas": tarefas} for hora, tarefas in sorted(timeline_map.items())]


@router.post("/tarefas/")
def criar_tarefa(req: TarefaCreate, db: Session = Depends(get_db)) -> dict:
    """Cria uma nova tarefa no planner."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(req.data) if req.data else None
        service = PlannerService(db)
        tarefa = service.criar_tarefa(
            titulo=req.titulo,
            descricao=req.descricao,
            data=data_obj,
            hora_inicio=req.hora_inicio,
            hora_fim=req.hora_fim,
            prioridade=req.prioridade,
            area=req.area,
            organizacao_id=req.organizacao_id,
        )
        return {
            "ok": True,
            "id": tarefa.get("id"),
            "titulo": tarefa.get("titulo"),
            "data": tarefa.get("data"),
            "prioridade": tarefa.get("prioridade"),
            "area": tarefa.get("area"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao criar tarefa: {str(e)}")


@router.get("/tarefas/{data}")
def listar_tarefas_dia(data: str, db: Session = Depends(get_db)) -> dict:
    """Lista tarefas de uma data especifica (YYYY-MM-DD)."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(data)
        service = PlannerService(db)
        tarefas = service.listar_tarefas_dia(data_obj)
        return {"data": data, "tarefas": tarefas, "total": len(tarefas)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao listar tarefas: {str(e)}")


@router.get("/tarefas/semana/{data}")
def listar_tarefas_semana(data: str, db: Session = Depends(get_db)) -> dict:
    """Lista tarefas da semana do dia informado."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(data)
        service = PlannerService(db)
        tarefas = service.listar_tarefas_semana(data_obj)
        return {
            "semana": f"{data_obj.isocalendar()[1]}/{data_obj.year}",
            "tarefas": tarefas,
            "total": len(tarefas),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao listar tarefas da semana: {str(e)}")


@router.patch("/tarefas/{tarefa_id}/completar")
def completar_tarefa(tarefa_id: int, db: Session = Depends(get_db)) -> dict:
    """Marca tarefa como concluida."""
    try:
        service = PlannerService(db)
        tarefa = service.completar_tarefa(tarefa_id)
        return {
            "ok": True,
            "id": tarefa_id,
            "pontos_ganhos": tarefa.get("pontos_ganhos", 0),
            "xp_ganhos": tarefa.get("xp_ganhos", 0),
            "badge_desbloqueada": tarefa.get("badge_desbloqueada"),
            "novo_nivel": tarefa.get("novo_nivel"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao completar tarefa: {str(e)}")


@router.put("/tarefas/{tarefa_id}")
def atualizar_tarefa(tarefa_id: int, req: TarefaUpdate, db: Session = Depends(get_db)) -> dict:
    """Altera os dados de uma tarefa."""
    try:
        service = PlannerService(db)
        data_obj = _parse_data_yyyy_mm_dd(req.data) if req.data else None
        tarefa = service.atualizar_tarefa(
            tarefa_id,
            titulo=req.titulo,
            descricao=req.descricao,
            data=data_obj,
            hora_inicio=req.hora_inicio,
            hora_fim=req.hora_fim,
            prioridade=req.prioridade,
            area=req.area,
            status=req.status,
            organizacao_id=req.organizacao_id,
        )
        return {"ok": True, "tarefa": tarefa}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao atualizar tarefa: {str(e)}")


@router.delete("/tarefas/{tarefa_id}")
def excluir_tarefa(tarefa_id: int, organizacao_id: int = 1, db: Session = Depends(get_db)) -> dict:
    """Exclui uma tarefa do planner."""
    try:
        service = PlannerService(db)
        resultado = service.excluir_tarefa(tarefa_id=tarefa_id, organizacao_id=organizacao_id)
        return {"ok": True, **resultado}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao excluir tarefa: {str(e)}")


@router.post("/organize/")
def organizar_tarefas_com_ia(req: OrganizarTarefasRequest, db: Session = Depends(get_db)) -> dict:
    """Organiza texto livre em tarefas planejadas."""
    try:
        texto_livre = (req.texto or req.tarefas_texto or "").strip()
        data_ref = req.data or req.data_inicio
        data_obj = _parse_data_yyyy_mm_dd(data_ref) if data_ref else date.today()
        if not texto_livre:
            raise ValueError("Texto vazio para organizacao")

        service = PlannerService(db)
        resultado = service.organizar_tarefas_com_ia(
            tarefas_texto=texto_livre,
            data_inicio=data_obj,
            area=req.area,
            organizacao_id=req.organizacao_id,
        )

        return {
            "ok": True,
            "tarefas_criadas": len(resultado.get("tarefas", [])),
            "tarefas": resultado.get("tarefas", []),
            "horarios_sugeridos": resultado.get("horarios_sugeridos", []),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao organizar tarefas: {str(e)}")


@router.get("/pontuacao/")
def obter_pontuacao(db: Session = Depends(get_db)) -> dict:
    """Retorna status de gamificacao."""
    try:
        service = PlannerService(db)
        pontuacao = service.obter_pontuacao()
        badges_novas = service.verificar_badges()
        return {
            "pontos_totais": pontuacao.get("pontos", 0),
            "xp_total": pontuacao.get("xp", 0),
            "nivel": pontuacao.get("nivel", 1),
            "xp_proximo_nivel": pontuacao.get("xp_para_proximo", 0),
            "porcentagem_para_proximo": pontuacao.get("barra_progresso", 0),
            "badges_desbloqueadas": len(badges_novas),
            "badges": [
                {
                    "id": b.get("nome"),
                    "nome": b.get("nome"),
                    "descricao": b.get("descricao"),
                    "desbloqueada": True,
                    "data_desbloqueio": None,
                }
                for b in badges_novas
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao obter pontuacao: {str(e)}")


@router.get("/timeline/{data}")
def gerar_timeline(data: str, db: Session = Depends(get_db)) -> dict:
    """Retorna timeline do planner por data."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(data)
        service = PlannerService(db)
        timeline = service.gerar_timeline(data_obj)
        horarios = _normalizar_horarios(timeline)
        return {
            "data": data,
            "tipo": "timeline",
            "horarios": horarios,
            "total_tarefas": sum(len(item.get("tarefas", [])) for item in horarios),
            "horarios_vazios": [item.get("hora") for item in horarios if not item.get("tarefas")],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao gerar timeline: {str(e)}")


@router.get("/kanban/{data}")
def gerar_kanban(data: str, db: Session = Depends(get_db)) -> dict:
    """Retorna kanban do planner por data."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(data)
        service = PlannerService(db)
        kanban = service.gerar_kanban(data_obj)
        colunas = kanban.get("colunas") if isinstance(kanban.get("colunas"), dict) else kanban
        a_fazer = colunas.get("a_fazer", [])
        em_progresso = colunas.get("em_progresso", [])
        concluido = colunas.get("concluido", [])
        return {
            "data": data,
            "tipo": "kanban",
            "a_fazer": a_fazer,
            "em_progresso": em_progresso,
            "concluido": concluido,
            "resumo": {
                "total": len(a_fazer) + len(em_progresso) + len(concluido),
                "concluidas": len(concluido),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao gerar kanban: {str(e)}")


@router.get("/smartplanner/{data}")
def smartplanner(data: str, db: Session = Depends(get_db)) -> dict:
    """Retorna SmartPlanner (equivalente a timeline organizada)."""
    try:
        data_obj = _parse_data_yyyy_mm_dd(data)
        service = PlannerService(db)
        resultado = service.gerar_timeline(data_obj)
        horarios = _normalizar_horarios(resultado)
        return {
            "tipo": "smartplanner",
            "data": data,
            "horarios": horarios,
            "total_tarefas": sum(len(item.get("tarefas", [])) for item in horarios),
            "horarios_vazios": [item.get("hora") for item in horarios if not item.get("tarefas")],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao gerar smartplanner: {str(e)}")
