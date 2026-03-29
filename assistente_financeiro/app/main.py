"""
Aplicação principal FastAPI — Assistente Financeiro Pessoal.

Endpoints disponíveis:
  GET  /                          → Health check
  POST /transacoes/               → Criar transação manual
  GET  /transacoes/               → Listar transações (com filtros)
  GET  /transacoes/{id}           → Detalhe de transação
  PUT  /transacoes/{id}           → Atualizar transação
  DELETE /transacoes/{id}         → Remover transação

  GET  /categorias/               → Listar categorias
  POST /categorias/               → Criar categoria
  PUT  /categorias/{id}           → Atualizar categoria

  GET  /contas/                   → Listar contas bancárias
  POST /contas/                   → Criar conta
  GET  /cartoes/                  → Listar cartões
  POST /cartoes/                  → Criar cartão

  POST /importar/pdf              → Importar PDF
  POST /importar/csv              → Importar CSV
  POST /importar/excel            → Importar Excel
  POST /importar/ofx              → Importar OFX
  GET  /extratos/                 → Listar extratos importados

  GET  /dashboard/{mes}/{ano}     → Dados do dashboard
  GET  /insights/{mes}/{ano}      → Insights do período
  GET  /historico/tendencia       → Análise de tendência
  GET  /historico/comparar        → Comparação entre meses

  GET  /metas/                    → Listar metas
  POST /metas/                    → Criar meta
  PUT  /metas/{id}/progresso      → Atualizar progresso
  GET  /orcamentos/{mes}/{ano}    → Listar orçamentos
  POST /orcamentos/               → Criar orçamento

  POST /exportar/csv              → Exportar CSV
  POST /exportar/excel            → Exportar Excel
  POST /exportar/pdf              → Exportar PDF

  POST /assistente/               → Assistente conversacional
  POST /despesa/rapida            → Registro rápido de despesa
  POST /voz/processar             → Processar áudio de voz
"""

import os
import shutil
import logging
import threading
import time
import asyncio
import concurrent.futures
import re
import unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4

from dotenv import load_dotenv
import requests
load_dotenv()  # carrega .env antes de qualquer os.getenv()

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.database import get_db, criar_tabelas
from app import models, schemas
from app.models import (
    Transacao, Categoria, ContaBancaria, CartaoCredito, Extrato, Meta, Orcamento,
    EventoFinanceiro, Compromisso, TarefaPlanner, StatusEvento, StatusTarefa,
    TelegramChat, Organizacao,
)
from app.schemas import (
    TransacaoCreate, TransacaoUpdate, TransacaoRead,
    CategoriaCreate, CategoriaUpdate, CategoriaRead,
    ContaBancariaCreate, ContaBancariaUpdate, ContaBancariaRead,
    CartaoCreditoCreate, CartaoCreditoUpdate, CartaoCreditoRead,
    MetaCreate, MetaUpdate, MetaRead,
    OrcamentoCreate, OrcamentoUpdate, OrcamentoRead,
    ExtratoRead, ResumoDashboard, InsightFinanceiro,
    PerguntaAssistente, RespostaAssistente, DespesaManual, TelegramTeste,
    DocumentoDetectado, DocumentoConfirmar,
)
from app.services.import_service     import ImportService
from app.services.export_service     import ExportService
from app.services.insights_service   import InsightsService
from app.services.metas_service      import MetasService
from app.services.historico_service  import HistoricoService
from app.services.gemini_service     import GeminiService
from app.services.classifier_service import ClassifierService
from app.services.local_ai_service   import LocalAIService
from app.services.openrouter_service import OpenRouterService
from app.services.notificacoes.telegram_service import TelegramService
from app.services.notificacoes.voice_processor  import VoiceProcessor
from app.routes.planner_routes import router as planner_router

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TELEGRAM_WORKER_STARTED = False
_AGENDA_REMINDER_WORKER_STARTED = False
_TELEGRAM_PENDENCIAS: Dict[str, Dict[str, Any]] = {}
_AGENDA_LEMBRETES_ENVIADOS: set[str] = set()
_AGENDA_LEMBRETES_LOCK = threading.Lock()
_TELEGRAM_TIPOS_DOCUMENTO: List[tuple[str, str]] = [
    ("comprovante_pagamento_bancario", "Comprovante Bancário (PIX/Transferência)"),
    ("recibo_despesa", "Recibo de Despesa"),
    ("nota_fiscal", "Nota Fiscal de Despesa"),
    ("comprovante_compra", "Comprovante de Compra (Cartão)"),
    ("boleto", "Boleto Bancário"),
    ("extrato_bancario", "Extrato Bancário"),
    ("extrato_cartao", "Extrato de Cartão de Crédito"),
]

_CATEGORIA_EMOJI: Dict[str, str] = {
    "Alimentação":      "🛒",
    "Restaurante":      "🍽",
    "Transporte":       "🚗",
    "Saúde":            "💊",
    "Educação":         "📚",
    "Lazer":            "🎬",
    "Vestuário":        "👕",
    "Casa":             "🏠",
    "Telecomunicações": "📱",
    "Investimento":     "📈",
    "Serviços":         "⚙",
    "Pets":             "🐾",
    "Outros":           "📌",
}

_MESES_TEXTO: Dict[str, int] = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "marco": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}

# Diretório de uploads
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Inicializa recursos globais no startup da aplicação."""
    criar_tabelas()
    _popular_categorias_padrao()
    _iniciar_worker_telegram_polling()
    _iniciar_worker_lembretes_agenda()
    logger.info("✅ Assistente Financeiro iniciado com sucesso!")
    yield

# ================================================
# Inicialização do app FastAPI
# ================================================

app = FastAPI(
    lifespan=lifespan,
    title="Assistente Financeiro Pessoal",
    description="API REST completa para gestão financeira pessoal com OCR, insights e Telegram.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS - permite acesso da interface local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planner_router)


# ================================================
# Eventos de ciclo de vida
# ================================================


def _normalizar_bool_env(valor: Optional[str], padrao: bool = True) -> bool:
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _obter_org_id_chat(chat_id: str) -> Optional[int]:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        chat = (
            db.query(TelegramChat)
            .filter(TelegramChat.chat_id == str(chat_id).strip(), TelegramChat.ativo == True)  # noqa: E712
            .first()
        )
        return int(chat.organizacao_id) if chat and chat.organizacao_id is not None else None
    finally:
        db.close()


def _obter_org_padrao_id(db: Session) -> Optional[int]:
    org = db.query(Organizacao).order_by(Organizacao.id.asc()).first()
    return int(org.id) if org else None


def _registrar_chat_telegram_se_necessario(
    chat_id: str,
    msg: Any,
    permitir_auto_bind: bool,
) -> bool:
    """Garante que o chat atual esteja mapeado para uma organização."""
    from app.database import SessionLocal

    chat_id_norm = str(chat_id).strip()
    if not chat_id_norm:
        return False

    db = SessionLocal()
    try:
        atual = (
            db.query(TelegramChat)
            .filter(TelegramChat.chat_id == chat_id_norm)
            .first()
        )
        if atual:
            if not atual.ativo:
                atual.ativo = True
                db.commit()
            return True

        if not permitir_auto_bind:
            return False

        org_id = _obter_org_padrao_id(db)
        if org_id is None:
            return False

        chat_obj = getattr(msg, "chat", None)
        tipo_chat = str(getattr(chat_obj, "type", "private") or "private")
        titulo = str(getattr(chat_obj, "title", "") or "").strip() or None

        novo = TelegramChat(
            chat_id=chat_id_norm,
            tipo_chat=tipo_chat,
            titulo=titulo,
            organizacao_id=org_id,
            ativo=True,
        )
        db.add(novo)
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception("Falha ao registrar chat Telegram para organização.")
        return False
    finally:
        db.close()


def _chat_telegram_autorizado(svc: TelegramService, chat_id: str, msg: Optional[Any] = None) -> bool:
    """
    Regras:
    1) Chat fixo do .env sempre permitido.
    2) Chats mapeados em telegram_chats permitidos.
    3) Se TELEGRAM_ALLOW_AUTO_BIND=true, novos chats são vinculados automaticamente
       à organização padrão.
    """
    chat_id_norm = str(chat_id).strip()
    if not chat_id_norm:
        return False

    if svc.chat_id and str(svc.chat_id).strip() == chat_id_norm:
        return True

    permitir_auto_bind = _normalizar_bool_env(os.getenv("TELEGRAM_ALLOW_AUTO_BIND"), padrao=True)
    return _registrar_chat_telegram_se_necessario(
        chat_id=chat_id_norm,
        msg=msg,
        permitir_auto_bind=permitir_auto_bind,
    )


def _processar_texto_telegram(
    svc: TelegramService,
    chat_id: str,
    texto: str,
    loop: asyncio.AbstractEventLoop,
    msg: Optional[Any] = None,
) -> None:
    """Processa texto recebido no Telegram e responde com confirmação."""
    texto = (texto or "").strip()
    if not texto:
        return

    # Se chat fixo estiver configurado, ignora mensagens de outros chats.
    if not _chat_telegram_autorizado(svc, chat_id, msg=msg):
        return

    texto_norm_global = _normalizar_texto_telegram(texto)

    # Atalhos por botao do teclado Telegram.
    if texto_norm_global in {"menu", "inicio"}:
        loop.run_until_complete(
            svc.enviar_mensagem(
                "🏠 Menu principal aberto. Escolha uma opção:",
                chat_id=chat_id,
                botoes=svc.teclado_menu_principal(),
            )
        )
        return

    if texto_norm_global in {"limpar contexto", "limpar"}:
        svc.limpar_contexto(chat_id)
        loop.run_until_complete(
            svc.enviar_mensagem(
                "🧹 Contexto limpo com sucesso.",
                chat_id=chat_id,
                botoes=svc.teclado_menu_principal(),
            )
        )
        return

    if texto.lower() in {"/start", "/help", "ajuda"} or texto_norm_global in {"ajuda", "lancar despesa", "importar documento"}:
        loop.run_until_complete(
            svc.enviar_mensagem(
                (
                    svc.mensagem_ajuda_despesa()
                    + "\n\n📎 Você também pode enviar arquivo/foto.\n"
                      "Eu detecto o tipo e pergunto se deseja salvar, alterar ou cancelar.\n\n"
                      "🎙️ Você também pode enviar áudio/voz para lançar despesa.\n"
                      "💬 Também converso com contexto. Para limpar a conversa, envie: limpar contexto"
                ),
                chat_id=chat_id,
                botoes=svc.teclado_menu_principal(),
            )
        )
        return

    pendencia = _TELEGRAM_PENDENCIAS.get(chat_id)
    if pendencia:
        if pendencia.get("kind") == "documento":
            _processar_pendencia_documento_telegram(svc, chat_id, texto, loop, pendencia)
            return

        texto_norm = _normalizar_texto_telegram(texto)

        if texto_norm in {"cancelar", "c", "3", "cancelar lancamento", "cancelar importacao"}:
            _TELEGRAM_PENDENCIAS.pop(chat_id, None)
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "❌ Lançamento cancelado.",
                    chat_id=chat_id,
                    botoes=svc.teclado_menu_principal(),
                )
            )
            return

        if texto_norm in {"editar", "alterar despesa"}:
            pendencia["aguardando_alteracao"] = True
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "✏️ Envie a despesa corrigida (ex: restaurante 50 ou 50 gasolina).",
                    chat_id=chat_id,
                )
            )
            return

        if pendencia.get("aguardando_alteracao"):
            comando_alt = svc.interpretar_comando_despesa(texto)
            if not comando_alt:
                loop.run_until_complete(
                    svc.enviar_mensagem(
                        "Não entendi a alteração. Envie no formato: descrição + valor (ex: gasolina 50) ou valor + descrição (ex: 50 gasolina).",
                        chat_id=chat_id,
                    )
                )
                return

            pendencia["comando"] = comando_alt
            pendencia["texto_original"] = texto
            pendencia["aguardando_alteracao"] = False
            loop.run_until_complete(
                svc.enviar_mensagem(
                    _mensagem_confirmacao_pendente(comando_alt),
                    chat_id=chat_id,
                    botoes=_teclado_confirmacao_despesa_telegram(),
                )
            )
            return

        if texto_norm.startswith("alterar"):
            novo_texto = texto[len("alterar"):].strip(" :")
            if not novo_texto:
                pendencia["aguardando_alteracao"] = True
                loop.run_until_complete(
                    svc.enviar_mensagem(
                        "✏️ Envie a despesa corrigida (ex: restaurante 50 ou 50 gasolina).",
                        chat_id=chat_id,
                    )
                )
                return

            comando_alt = svc.interpretar_comando_despesa(novo_texto)
            if not comando_alt:
                loop.run_until_complete(
                    svc.enviar_mensagem(
                        "Não entendi a alteração. Tente: alterar restaurante 50",
                        chat_id=chat_id,
                    )
                )
                return

            pendencia["comando"] = comando_alt
            pendencia["texto_original"] = novo_texto
            pendencia["aguardando_alteracao"] = False
            loop.run_until_complete(
                svc.enviar_mensagem(
                    _mensagem_confirmacao_pendente(comando_alt),
                    chat_id=chat_id,
                    botoes=_teclado_confirmacao_despesa_telegram(),
                )
            )
            return

        if texto_norm in {"salvar", "s", "1", "confirmar", "ok", "salvar lancamento", "confirmar lancamento"}:
            comando_pendente = pendencia.get("comando") or {}
            _TELEGRAM_PENDENCIAS.pop(chat_id, None)
            _salvar_transacao_telegram(svc, chat_id, comando_pendente, loop)
            return

        loop.run_until_complete(
            svc.enviar_mensagem(
                "Escolha uma ação nos botões abaixo:",
                chat_id=chat_id,
                botoes=_teclado_confirmacao_despesa_telegram(),
            )
        )
        return

    comando = svc.interpretar_comando_despesa(texto)
    if not comando:
        if _eh_consulta_resumo_mensal_telegram(texto):
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "📊 Entendi. Vou montar seu resumo financeiro agora.",
                    chat_id=chat_id,
                )
            )
            resposta = _responder_resumo_mensal_com_progresso(
                chat_id=chat_id,
                texto=texto,
                loop=loop,
                svc=svc,
            )
            loop.run_until_complete(
                svc.enviar_mensagem(
                    resposta,
                    chat_id=chat_id,
                )
            )
            return

        if svc.ollama_enabled:
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "🤖 Entendi. Estou analisando seus dados e ja te respondo. Isso pode levar alguns segundos.",
                    chat_id=chat_id,
                )
            )
            resposta = _responder_conversa_com_progresso(
                svc=svc,
                chat_id=chat_id,
                texto=texto,
                loop=loop,
            )
        else:
            resposta = svc.responder_conversa(chat_id=chat_id, texto=texto)

        loop.run_until_complete(
            svc.enviar_mensagem(
                resposta,
                chat_id=chat_id,
            )
        )
        return

    _TELEGRAM_PENDENCIAS[chat_id] = {
        "kind": "despesa",
        "comando": comando,
        "texto_original": texto,
        "aguardando_alteracao": False,
    }

    loop.run_until_complete(
        svc.enviar_mensagem(
            _mensagem_confirmacao_pendente(comando),
            chat_id=chat_id,
            botoes=_teclado_confirmacao_despesa_telegram(),
        )
    )


def _responder_conversa_com_progresso(
    svc: TelegramService,
    chat_id: str,
    texto: str,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Gera resposta conversacional enviando atualizações quando a IA demora."""
    atualizacoes = [
        "⏳ Ainda processando seu pedido. Obrigado pela paciencia.",
        "📊 Estou finalizando a analise do seu historico financeiro...",
        "✅ Quase pronto, so mais alguns segundos.",
    ]
    progresso_idx = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(svc.responder_conversa, chat_id, texto)

        while True:
            try:
                return future.result(timeout=15)
            except concurrent.futures.TimeoutError:
                if progresso_idx < len(atualizacoes):
                    loop.run_until_complete(
                        svc.enviar_mensagem(atualizacoes[progresso_idx], chat_id=chat_id)
                    )
                    progresso_idx += 1


def _eh_consulta_resumo_mensal_telegram(texto: str) -> bool:
    norm = _normalizar_texto_telegram(texto)
    if not norm:
        return False

    tem_resumo = any(
        chave in norm
        for chave in [
            "resumo",
            "total de gastos",
            "gasto total",
            "resumo financeiro",
            "resumo do mes",
        ]
    )
    tem_saldo_ou_totais = any(chave in norm for chave in ["despesas", "receitas", "saldo"])
    tem_periodo = (
        any(mes in norm.split() for mes in _MESES_TEXTO.keys())
        or "mes passado" in norm
        or "este mes" in norm
        or "mes atual" in norm
        or "esse mes" in norm
    )

    return tem_resumo or (tem_saldo_ou_totais and tem_periodo)


def _extrair_mes_ano_consulta_telegram(texto: str) -> tuple[int, int]:
    hoje = date.today()
    mes = hoje.month
    ano = hoje.year
    norm = _normalizar_texto_telegram(texto)

    for token in norm.split():
        if token in _MESES_TEXTO:
            mes = _MESES_TEXTO[token]
            break

    m_ano = re.search(r"\b(20\d{2})\b", norm)
    if m_ano:
        ano = int(m_ano.group(1))

    if "mes passado" in norm:
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1

    return mes, ano


def _montar_resumo_mensal_telegram(texto: str) -> str:
    from app.database import SessionLocal

    mes, ano = _extrair_mes_ano_consulta_telegram(texto)
    db = SessionLocal()
    try:
        resumo = InsightsService(db).resumo_dashboard(mes, ano)
        categorias = resumo.get("categorias_gastos") or []
        top3 = categorias[:3]

        linhas = [
            f"📊 Resumo financeiro de {resumo.get('mes_referencia', f'{mes:02d}/{ano}')}:",
            f"• Receitas: {_formatar_valor_br(resumo.get('total_receitas', 0))}",
            f"• Despesas: {_formatar_valor_br(resumo.get('total_despesas', 0))}",
            f"• Saldo: {_formatar_valor_br(resumo.get('saldo_mensal', 0))}",
            f"• Transações: {int(resumo.get('total_transacoes', 0) or 0)}",
        ]

        if top3:
            linhas.append("\nTop categorias de gasto:")
            for item in top3:
                nome = item.get("categoria", "Outros")
                valor = _formatar_valor_br(item.get("valor", 0))
                perc = float(item.get("percentual", 0) or 0)
                emoji = _CATEGORIA_EMOJI.get(nome, "📌")
                linhas.append(f"• {emoji} {nome}: {valor} ({perc:.1f}%)")

        return "\n".join(linhas)
    finally:
        db.close()


def _responder_resumo_mensal_com_progresso(
    svc: TelegramService,
    chat_id: str,
    texto: str,
    loop: asyncio.AbstractEventLoop,
) -> str:
    """Monta resumo mensal com atualizações de progresso se houver demora."""
    atualizacoes = [
        "⏳ Ainda consultando suas transações desse período...",
        "📈 Já analisei receitas e despesas. Montando o resumo final...",
    ]
    progresso_idx = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_montar_resumo_mensal_telegram, texto)

        while True:
            try:
                return future.result(timeout=15)
            except concurrent.futures.TimeoutError:
                if progresso_idx < len(atualizacoes):
                    loop.run_until_complete(
                        svc.enviar_mensagem(atualizacoes[progresso_idx], chat_id=chat_id)
                    )
                    progresso_idx += 1
            except Exception as exc:
                logger.exception("Falha ao montar resumo mensal do Telegram")
                return f"❌ Nao consegui montar o resumo financeiro agora: {exc}"


def _mensagem_confirmacao_pendente(comando: Dict[str, Any]) -> str:
    valor = abs(float(comando.get("valor", 0) or 0))
    descricao = str(comando.get("descricao", "Despesa Telegram") or "Despesa Telegram")
    data_lanc = comando.get("data") or date.today()

    if isinstance(data_lanc, date):
        data_txt = data_lanc.strftime("%d/%m/%Y")
    else:
        data_txt = str(data_lanc)

    valor_txt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (
        "📩 *Confirmação de lançamento*\n\n"
        f"📝 Descrição: {descricao}\n"
        f"💵 Valor: {valor_txt}\n"
        f"📅 Data: {data_txt}\n\n"
        "Use os botões abaixo para confirmar, alterar ou cancelar."
    )


def _normalizar_texto_telegram(valor: str) -> str:
    txt = unicodedata.normalize("NFD", (valor or ""))
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-zA-Z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip().lower()
    return txt


def _opcoes_tipos_documento_telegram() -> str:
    linhas = ["Tipos disponíveis para alterar:"]
    for idx, (_chave, nome) in enumerate(_TELEGRAM_TIPOS_DOCUMENTO, start=1):
        linhas.append(f"{idx}. {nome}")
    return "\n".join(linhas)


def _resolver_tipo_documento_telegram(texto: str) -> Optional[str]:
    bruto = (texto or "").strip()
    if not bruto:
        return None

    if bruto.isdigit():
        pos = int(bruto)
        if 1 <= pos <= len(_TELEGRAM_TIPOS_DOCUMENTO):
            return _TELEGRAM_TIPOS_DOCUMENTO[pos - 1][0]

    norm = _normalizar_texto_telegram(bruto)
    if not norm:
        return None

    mapa_por_nome = {}
    for chave, nome in _TELEGRAM_TIPOS_DOCUMENTO:
        mapa_por_nome[_normalizar_texto_telegram(nome)] = chave
        mapa_por_nome[_normalizar_texto_telegram(chave)] = chave

    aliases = {
        "comprovante bancario": "comprovante_pagamento_bancario",
        "pix": "comprovante_pagamento_bancario",
        "comprovante pix": "comprovante_pagamento_bancario",
        "recibo": "recibo_despesa",
        "nota": "nota_fiscal",
        "nota fiscal": "nota_fiscal",
        "compra cartao": "comprovante_compra",
        "comprovante compra": "comprovante_compra",
        "extrato": "extrato_bancario",
        "extrato bancario": "extrato_bancario",
        "fatura": "extrato_cartao",
        "extrato cartao": "extrato_cartao",
    }
    mapa_por_nome.update(aliases)

    if norm in mapa_por_nome:
        return mapa_por_nome[norm]

    for chave_nome, chave_tipo in mapa_por_nome.items():
        if norm in chave_nome:
            return chave_tipo

    return None


def _formatar_valor_br(valor: Any) -> str:
    try:
        numero = float(valor)
    except Exception:
        return "não identificado"
    return "R$ " + f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _mensagem_confirmacao_documento_pendente(pendencia: Dict[str, Any]) -> str:
    analise = pendencia.get("analise") or {}
    pre = analise.get("pre_lancamento") or {}
    tipo = analise.get("nome_tipo", "Tipo não identificado")
    confianca = str(analise.get("confianca", "baixa")).upper()
    tipo_escolhido = pendencia.get("tipo_documento") or analise.get("tipo_detectado") or "desconhecido"
    nome_escolhido = next((n for c, n in _TELEGRAM_TIPOS_DOCUMENTO if c == tipo_escolhido), tipo_escolhido)

    linhas = [
        "📄 *Prévia do documento recebido*",
        f"Arquivo: {analise.get('arquivo_nome', 'arquivo')}",
        f"Detectado: {tipo} (confiança {confianca})",
        f"Tipo escolhido: {nome_escolhido}",
    ]

    amostra = pre.get("amostra_transacoes") or []
    qtd = pre.get("qtd_transacoes")

    if amostra:
        # Extrato ou fatura de cartão: exibir amostra de transações categorizada
        qtd_label = f"{qtd}" if qtd is not None else f"{len(amostra)}+"
        linhas.append(f"\n📊 Transações detectadas: {qtd_label}")
        for item in amostra:
            data_raw = str(item.get("data") or "")
            # YYYY-MM-DD → dd/mm
            if len(data_raw) >= 10 and data_raw[4] == "-":
                data_fmt = data_raw[8:10] + "/" + data_raw[5:7]
            else:
                data_fmt = data_raw[:5] or "??"
            desc = (str(item.get("descricao") or "Sem descrição"))[:28]
            valor_fmt = _formatar_valor_br(item.get("valor"))
            tipo_t = str(item.get("tipo") or "debito").lower()
            sinal = "+" if tipo_t == "credito" else "-"
            cat = item.get("categoria_sugerida") or "Outros"
            emoji_cat = _CATEGORIA_EMOJI.get(cat, "📌")
            linhas.append(f"  {data_fmt}  {desc}  {sinal}{valor_fmt}  {emoji_cat} {cat}")
    else:
        # Documento único (comprovante, nota fiscal, boleto, etc.)
        if pre.get("valor") is not None:
            linhas.append(f"\nValor: {_formatar_valor_br(pre.get('valor'))}")
        if pre.get("descricao"):
            linhas.append(f"Descrição: {pre.get('descricao')}")
        if pre.get("vencimento"):
            linhas.append(f"Vencimento: {pre.get('vencimento')}")
        cat = pre.get("categoria_sugerida") or "Outros"
        emoji_cat = _CATEGORIA_EMOJI.get(cat, "📌")
        linhas.append(f"Categoria da despesa: {emoji_cat} {cat}")

    linhas.extend([
        "",
        "Confirmação:",
        "• toque em OK para confirmar",
        "• digite apenas o número da opção para alterar o tipo",
        "• digite cancelar para descartar",
        "",
        _opcoes_tipos_documento_telegram(),
    ])
    return "\n".join(linhas)


def _teclado_confirmacao_documento_telegram() -> List[List[str]]:
    return [["✅ Confirmar"], ["✏️ Alterar tipo", "❌ Cancelar"]]


def _teclado_confirmacao_despesa_telegram() -> List[List[str]]:
    return [["✅ Salvar lançamento"], ["✏️ Alterar despesa", "❌ Cancelar"]]


def _baixar_arquivo_telegram(
    svc: TelegramService,
    loop: asyncio.AbstractEventLoop,
    file_id: str,
    nome_original: str,
    ext: str,
) -> str:
    if not svc._bot:
        raise RuntimeError("Bot Telegram não inicializado.")

    info = loop.run_until_complete(svc._bot.get_file(file_id))
    file_path = getattr(info, "file_path", None)
    if not file_path:
        raise RuntimeError("Não foi possível obter o arquivo no Telegram.")

    dest_dir = UPLOAD_DIR / "telegram"
    dest_dir.mkdir(parents=True, exist_ok=True)

    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(nome_original).stem)[:40] or "arquivo"
    ext_ok = ext if ext.startswith(".") else f".{ext}"
    nome_dest = f"tg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stem}_{uuid4().hex[:8]}{ext_ok}"
    destino = dest_dir / nome_dest

    # python-telegram-bot v20+: file_path já é a URL completa (https://...).
    # Versões anteriores retornam apenas o caminho relativo.
    if str(file_path).startswith("http://") or str(file_path).startswith("https://"):
        url = str(file_path)
    else:
        url = f"https://api.telegram.org/file/bot{svc.token}/{file_path}"
    resp = requests.get(url, timeout=90)
    resp.raise_for_status()
    destino.write_bytes(resp.content)
    return str(destino)


def _salvar_documento_telegram(
    svc: TelegramService,
    chat_id: str,
    pendencia: Dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> None:
    from app.database import SessionLocal

    caminho = pendencia.get("caminho")
    tipo_documento = pendencia.get("tipo_documento")
    analise = pendencia.get("analise") or {}

    if not caminho or not tipo_documento:
        loop.run_until_complete(
            svc.enviar_mensagem("❌ Pendência inválida de documento.", chat_id=chat_id)
        )
        return

    db = SessionLocal()
    try:
        import_service = ImportService(db)
        resultado = import_service.importar_por_tipo_documento(
            caminho=caminho,
            tipo_documento=tipo_documento,
            senha=pendencia.get("senha"),
        )

        texto_completo = analise.get("texto_completo")
        tipo_detectado = analise.get("tipo_detectado")
        if texto_completo:
            import_service.registrar_feedback_tipo_documento(
                texto=texto_completo,
                tipo_confirmado=tipo_documento,
                tipo_detectado=tipo_detectado,
            )

        importadas = int(resultado.get("importadas", 0) or 0)
        ignoradas = int(resultado.get("ignoradas", 0) or 0)
        resumo = (
            "✅ Documento salvo com sucesso!\n"
            f"Tipo: {next((n for c, n in _TELEGRAM_TIPOS_DOCUMENTO if c == tipo_documento), tipo_documento)}\n"
            f"Importadas: {importadas}\n"
            f"Ignoradas: {ignoradas}"
        )
        if "valor" in resultado:
            resumo += f"\nValor: {_formatar_valor_br(resultado.get('valor'))}"

        loop.run_until_complete(svc.enviar_mensagem(resumo, chat_id=chat_id))
    except Exception as exc:
        logger.exception("Erro ao salvar documento recebido via Telegram")
        loop.run_until_complete(
            svc.enviar_mensagem(f"❌ Erro ao salvar documento: {exc}", chat_id=chat_id)
        )
    finally:
        db.close()
        try:
            if caminho and os.path.exists(caminho):
                os.remove(caminho)
        except Exception:
            pass


def _processar_pendencia_documento_telegram(
    svc: TelegramService,
    chat_id: str,
    texto: str,
    loop: asyncio.AbstractEventLoop,
    pendencia: Dict[str, Any],
) -> None:
    texto_norm = _normalizar_texto_telegram(texto)

    if texto_norm in {"cancelar", "c", "cancelar importacao"}:
        _TELEGRAM_PENDENCIAS.pop(chat_id, None)
        caminho = pendencia.get("caminho")
        try:
            if caminho and os.path.exists(caminho):
                os.remove(caminho)
        except Exception:
            pass
        loop.run_until_complete(svc.enviar_mensagem("❌ Importação cancelada.", chat_id=chat_id))
        return

    if texto_norm in {"correto", "salvar", "s", "confirmar", "ok", "confirmar", "confirmar documento"}:
        _TELEGRAM_PENDENCIAS.pop(chat_id, None)
        _salvar_documento_telegram(svc, chat_id, pendencia, loop)
        return

    arg = ""
    if texto_norm.isdigit():
        arg = texto_norm
    elif texto_norm.startswith("alterar"):
        arg = (texto or "")[len("alterar"):].strip(" :")

    if texto_norm in {"alterar tipo", "alterar tipo documento"}:
        loop.run_until_complete(
            svc.enviar_mensagem(
                "Informe o novo tipo com o número da lista abaixo:\n\n" + _opcoes_tipos_documento_telegram(),
                chat_id=chat_id,
                botoes=_teclado_confirmacao_documento_telegram(),
            )
        )
        return

    if arg:
        if not arg:
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "Informe o novo tipo após 'alterar'.\n"
                    "Ex.: alterar 2\n"
                    "Ex.: alterar extrato bancário\n\n"
                    + _opcoes_tipos_documento_telegram(),
                    chat_id=chat_id,
                )
            )
            return

        novo_tipo = _resolver_tipo_documento_telegram(arg)
        if not novo_tipo:
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "Tipo não reconhecido para alteração.\n\n"
                    + _opcoes_tipos_documento_telegram(),
                    chat_id=chat_id,
                )
            )
            return

        pendencia["tipo_documento"] = novo_tipo
        loop.run_until_complete(
            svc.enviar_mensagem(
                _mensagem_confirmacao_documento_pendente(pendencia),
                chat_id=chat_id,
                botoes=_teclado_confirmacao_documento_telegram(),
            )
        )
        return

    loop.run_until_complete(
        svc.enviar_mensagem(
            "Toque em OK para confirmar, digite um número para alterar o tipo ou envie cancelar.\n\n"
            + _opcoes_tipos_documento_telegram(),
            chat_id=chat_id,
            botoes=_teclado_confirmacao_documento_telegram(),
        )
    )


def _processar_arquivo_telegram(
    svc: TelegramService,
    chat_id: str,
    msg: Any,
    loop: asyncio.AbstractEventLoop,
) -> None:
    # Valida autorização do chat e faz auto-vínculo quando habilitado.
    if not _chat_telegram_autorizado(svc, chat_id, msg=msg):
        return

    file_id = None
    nome_original = "arquivo_telegram"
    ext = ""

    documento = getattr(msg, "document", None)
    fotos = getattr(msg, "photo", None)
    voz = getattr(msg, "voice", None)
    audio = getattr(msg, "audio", None)

    is_audio = False

    if documento:
        file_id = getattr(documento, "file_id", None)
        nome_original = getattr(documento, "file_name", None) or nome_original
        ext = Path(nome_original).suffix.lower()
    elif fotos:
        foto = fotos[-1]
        file_id = getattr(foto, "file_id", None)
        nome_original = "foto_telegram.jpg"
        ext = ".jpg"
    elif voz:
        file_id = getattr(voz, "file_id", None)
        nome_original = "voice_telegram.ogg"
        ext = ".ogg"
        is_audio = True
    elif audio:
        file_id = getattr(audio, "file_id", None)
        nome_original = getattr(audio, "file_name", None) or "audio_telegram"
        ext = Path(nome_original).suffix.lower()
        if not ext:
            mime = str(getattr(audio, "mime_type", "") or "").lower()
            if "ogg" in mime or "opus" in mime:
                ext = ".ogg"
            elif "mpeg" in mime or "mp3" in mime:
                ext = ".mp3"
            elif "m4a" in mime or "mp4" in mime:
                ext = ".m4a"
            else:
                ext = ".ogg"
            nome_original = f"audio_telegram{ext}"
        is_audio = True

    if not file_id:
        loop.run_until_complete(
            svc.enviar_mensagem("Não consegui ler o arquivo enviado.", chat_id=chat_id)
        )
        return

    if is_audio:
        suportados_audio = set(VoiceProcessor.FORMATOS_SUPORTADOS)
        if ext not in suportados_audio:
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "Formato de áudio não suportado para transcrição.\n"
                    f"Envie um destes: {', '.join(sorted(suportados_audio))}",
                    chat_id=chat_id,
                    botoes=svc.teclado_menu_principal(),
                )
            )
            return
    else:
        suportados = set(ImportService.EXTENSOES_DOCUMENTO)
        if ext not in suportados:
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "Formato ainda não suportado no fluxo automático do Telegram.\n"
                    f"Envie um destes: {', '.join(sorted(suportados))}",
                    chat_id=chat_id,
                    botoes=svc.teclado_menu_principal(),
                )
            )
            return

    # Avisa imediatamente que o arquivo foi recebido e está sendo processado.
    if is_audio:
        loop.run_until_complete(
            svc.enviar_mensagem(
                f"🎙️ Áudio recebido ({nome_original}). Transcrevendo, aguarde...",
                chat_id=chat_id,
                botoes=svc.teclado_menu_principal(),
            )
        )
    else:
        loop.run_until_complete(
            svc.enviar_mensagem(
                f"📥 Arquivo recebido ({nome_original}). Analisando, aguarde...",
                chat_id=chat_id,
                botoes=svc.teclado_menu_principal(),
            )
        )

    try:
        caminho_local = _baixar_arquivo_telegram(svc, loop, file_id, nome_original, ext)
    except Exception as exc:
        logger.exception("Falha ao baixar arquivo do Telegram")
        loop.run_until_complete(
            svc.enviar_mensagem("❌ Não consegui baixar o arquivo. Tente novamente.", chat_id=chat_id)
        )
        return

    if is_audio:
        try:
            voice = VoiceProcessor()
            transcricao = voice.transcrever_audio(caminho_local)

            if str(transcricao).startswith("[Erro"):
                loop.run_until_complete(
                    svc.enviar_mensagem(
                        "❌ Não consegui transcrever o áudio.\n"
                        f"Detalhe: {transcricao}",
                        chat_id=chat_id,
                        botoes=svc.teclado_menu_principal(),
                    )
                )
                return

            comando = svc.interpretar_comando_despesa(transcricao)
            if not comando:
                loop.run_until_complete(
                    svc.enviar_mensagem(
                        "❌ Entendi o áudio, mas não identifiquei um lançamento válido.\n"
                        f"Transcrição: {transcricao}\n\n"
                        "Exemplos que funcionam:\n"
                        "• gasolina 100\n"
                        "• padaria 70\n"
                        "• almoço 40",
                        chat_id=chat_id,
                        botoes=svc.teclado_menu_principal(),
                    )
                )
                return

            _TELEGRAM_PENDENCIAS[chat_id] = {
                "kind": "despesa",
                "comando": comando,
                "texto_original": transcricao,
                "aguardando_alteracao": False,
                "origem": "voz",
            }

            loop.run_until_complete(
                svc.enviar_mensagem(
                    "🎙️ Áudio transcrito:\n"
                    f"{transcricao}\n\n"
                    f"{_mensagem_confirmacao_pendente(comando)}",
                    chat_id=chat_id,
                    botoes=_teclado_confirmacao_despesa_telegram(),
                )
            )
        except Exception:
            logger.exception("Falha ao processar áudio do Telegram")
            loop.run_until_complete(
                svc.enviar_mensagem(
                    "❌ Não consegui processar o áudio agora. Tente novamente em instantes.",
                    chat_id=chat_id,
                    botoes=svc.teclado_menu_principal(),
                )
            )
        finally:
            try:
                if os.path.exists(caminho_local):
                    os.remove(caminho_local)
            except Exception:
                pass
        return

    db = None
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        analise = ImportService(db).analisar_documento(caminho_local)
    except Exception:
        logger.exception("Falha ao analisar arquivo do Telegram")
        loop.run_until_complete(
            svc.enviar_mensagem("❌ Não consegui analisar o documento. Verifique se o arquivo é legível.", chat_id=chat_id)
        )
        try:
            if os.path.exists(caminho_local):
                os.remove(caminho_local)
        except Exception:
            pass
        return
    finally:
        if db is not None:
            db.close()

    _TELEGRAM_PENDENCIAS[chat_id] = {
        "kind": "documento",
        "caminho": caminho_local,
        "senha": None,
        "analise": analise,
        "tipo_documento": analise.get("tipo_detectado") or "extrato_bancario",
    }

    loop.run_until_complete(
        svc.enviar_mensagem(
            _mensagem_confirmacao_documento_pendente(_TELEGRAM_PENDENCIAS[chat_id]),
            chat_id=chat_id,
            botoes=_teclado_confirmacao_documento_telegram(),
        )
    )


def _salvar_transacao_telegram(
    svc: TelegramService,
    chat_id: str,
    comando: Dict[str, Any],
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Persiste uma despesa Telegram já confirmada pelo usuário."""

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        transacao = Transacao(
            data=comando.get("data", date.today()),
            descricao=comando.get("descricao", "Despesa Telegram"),
            valor=abs(float(comando.get("valor", 0))),
            tipo="debito",
            fonte="telegram",
            organizacao_id=_obter_org_id_chat(chat_id) or 1,
        )
        ClassifierService(db).classificar_e_aplicar(transacao)

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        categoria_nome = transacao.categoria.nome if transacao.categoria else "Outros"
        resposta = svc.formatar_confirmacao(
            valor=transacao.valor,
            descricao=transacao.descricao,
            categoria=categoria_nome,
            data=transacao.data,
        )
        resposta += f"\n\n🆔 ID: {transacao.id}\n📡 Fonte: telegram"
        loop.run_until_complete(svc.enviar_mensagem(resposta, chat_id=chat_id))
    except Exception as exc:
        db.rollback()
        logger.exception("Erro ao processar mensagem do Telegram")
        loop.run_until_complete(
            svc.enviar_mensagem(
                f"❌ Erro ao registrar despesa: {exc}",
                chat_id=chat_id,
            )
        )
    finally:
        db.close()


def _iniciar_worker_lembretes_agenda() -> None:
    """Inicia worker que envia lembretes de agenda financeira, compromissos e planner."""
    global _AGENDA_REMINDER_WORKER_STARTED

    if _AGENDA_REMINDER_WORKER_STARTED:
        return

    if not _normalizar_bool_env(os.getenv("TELEGRAM_AGENDA_REMINDERS_ENABLED"), padrao=True):
        logger.info("Lembretes Telegram desativados por TELEGRAM_AGENDA_REMINDERS_ENABLED.")
        return

    svc = TelegramService()
    st = svc.status()
    if not st.get("ativo"):
        logger.info("Telegram sem token ativo; worker de lembretes não iniciado.")
        return

    intervalo_seg = max(20, int(os.getenv("TELEGRAM_AGENDA_POLL_SECONDS", "60")))
    janela_min = max(5, int(os.getenv("TELEGRAM_AGENDA_JANELA_MIN", "15")))
    compromisso_padrao_min = max(1, int(os.getenv("TELEGRAM_COMPROMISSO_LEMBRETE_PADRAO_MIN", "60")))
    evento_antecedencia_h = max(1, int(os.getenv("TELEGRAM_EVENTO_ANTECEDENCIA_HORAS", "24")))
    planner_hora = min(23, max(0, int(os.getenv("TELEGRAM_PLANNER_LEMBRETE_HORA", "8"))))

    def _chave(kind: str, item_id: int, when: datetime) -> str:
        return f"{kind}:{item_id}:{when.strftime('%Y%m%d%H%M')}"

    def _janela_inclui(agora: datetime, alvo: datetime) -> bool:
        inicio = agora - timedelta(minutes=janela_min)
        fim = agora + timedelta(minutes=janela_min)
        return inicio <= alvo <= fim

    def _enviar_se_novo(
        loop: asyncio.AbstractEventLoop,
        chat_destino: str,
        chave: str,
        texto: str,
    ) -> None:
        chave_global = f"{chat_destino}:{chave}"
        with _AGENDA_LEMBRETES_LOCK:
            if chave_global in _AGENDA_LEMBRETES_ENVIADOS:
                return
            _AGENDA_LEMBRETES_ENVIADOS.add(chave_global)

        enviado = loop.run_until_complete(svc.enviar_mensagem(texto, chat_id=chat_destino))
        if not enviado:
            with _AGENDA_LEMBRETES_LOCK:
                _AGENDA_LEMBRETES_ENVIADOS.discard(chave_global)

    def _destinos_por_org(db: Session) -> List[tuple[str, Optional[int]]]:
        chats = (
            db.query(TelegramChat)
            .filter(TelegramChat.ativo == True)  # noqa: E712
            .all()
        )
        if chats:
            return [(str(c.chat_id), int(c.organizacao_id) if c.organizacao_id is not None else None) for c in chats]

        if svc.chat_id and str(svc.chat_id).strip():
            org_padrao = _obter_org_padrao_id(db)
            return [(str(svc.chat_id).strip(), org_padrao)]

        return []

    def _hora_compromisso(hora_txt: Optional[str]) -> tuple[int, int]:
        if not hora_txt:
            return 9, 0
        try:
            hora, minuto = hora_txt.strip().split(":")
            h = min(23, max(0, int(hora)))
            m = min(59, max(0, int(minuto)))
            return h, m
        except Exception:
            return 9, 0

    def _loop_lembretes() -> None:
        from app.database import SessionLocal

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("🔔 Worker de lembretes da agenda iniciado.")

        while True:
            db = SessionLocal()
            try:
                agora = datetime.now()

                for chat_destino, org_id in _destinos_por_org(db):
                    # Agenda financeira: lembrete antecipado e no vencimento.
                    q_eventos = (
                        db.query(EventoFinanceiro)
                        .filter(
                            EventoFinanceiro.status.in_([StatusEvento.PENDENTE, StatusEvento.ATRASADO]),
                            EventoFinanceiro.data_vencimento >= (agora.date() - timedelta(days=1)),
                            EventoFinanceiro.data_vencimento <= (agora.date() + timedelta(days=2)),
                        )
                    )
                    if org_id is not None:
                        q_eventos = q_eventos.filter(EventoFinanceiro.organizacao_id == org_id)

                    for ev in q_eventos.all():
                        vencimento = datetime.combine(ev.data_vencimento, datetime.min.time().replace(hour=9, minute=0))
                        lembrete_antes = vencimento - timedelta(hours=evento_antecedencia_h)

                        if _janela_inclui(agora, lembrete_antes):
                            chave = _chave("evento_pre", ev.id, lembrete_antes)
                            texto = (
                                f"🔔 Lembrete financeiro: '{ev.titulo}' vence em breve.\n"
                                f"📅 Vencimento: {ev.data_vencimento.strftime('%d/%m/%Y')}\n"
                                f"💵 Valor: {_formatar_valor_br(ev.valor)}"
                            )
                            _enviar_se_novo(loop, chat_destino, chave, texto)

                        if _janela_inclui(agora, vencimento):
                            chave = _chave("evento_due", ev.id, vencimento)
                            texto = (
                                f"⚠️ Evento financeiro para hoje: '{ev.titulo}'.\n"
                                f"📅 Data: {ev.data_vencimento.strftime('%d/%m/%Y')}\n"
                                f"💵 Valor: {_formatar_valor_br(ev.valor)}"
                            )
                            _enviar_se_novo(loop, chat_destino, chave, texto)

                    # Compromissos: usa lembrete_min do item ou fallback padrão.
                    q_comp = (
                        db.query(Compromisso)
                        .filter(
                            Compromisso.concluido == False,  # noqa: E712
                            Compromisso.data >= (agora.date() - timedelta(days=1)),
                            Compromisso.data <= (agora.date() + timedelta(days=1)),
                        )
                    )
                    if org_id is not None:
                        q_comp = q_comp.filter(Compromisso.organizacao_id == org_id)

                    for comp in q_comp.all():
                        h, m = _hora_compromisso(comp.hora_inicio)
                        inicio = datetime.combine(comp.data, datetime.min.time().replace(hour=h, minute=m))
                        lembrete_min = comp.lembrete_min if comp.lembrete_min is not None else compromisso_padrao_min
                        lembrete = inicio - timedelta(minutes=max(1, int(lembrete_min)))

                        if _janela_inclui(agora, lembrete):
                            chave = _chave("compromisso", comp.id, lembrete)
                            horario = comp.hora_inicio or "09:00"
                            local_txt = f"\n📍 Local: {comp.local}" if comp.local else ""
                            texto = (
                                f"🗓️ Lembrete de compromisso: '{comp.titulo}'.\n"
                                f"📅 Data: {comp.data.strftime('%d/%m/%Y')} às {horario}"
                                f"{local_txt}"
                            )
                            _enviar_se_novo(loop, chat_destino, chave, texto)

                    # Planner: lembra no dia da tarefa, usando hora_inicio quando houver.
                    q_tarefas = (
                        db.query(TarefaPlanner)
                        .filter(
                            TarefaPlanner.status != StatusTarefa.CONCLUIDO,
                            TarefaPlanner.data != None,  # noqa: E711
                            TarefaPlanner.data >= agora.date(),
                            TarefaPlanner.data <= (agora.date() + timedelta(days=1)),
                        )
                    )
                    if org_id is not None:
                        q_tarefas = q_tarefas.filter(TarefaPlanner.organizacao_id == org_id)

                    for tarefa in q_tarefas.all():
                        hora_inicio_tarefa = str(tarefa.hora_inicio or "").strip()
                        try:
                            if hora_inicio_tarefa and ":" in hora_inicio_tarefa:
                                hh, mm = hora_inicio_tarefa.split(":", 1)
                                hora_ref = min(23, max(0, int(hh)))
                                min_ref = min(59, max(0, int(mm)))
                            else:
                                hora_ref = planner_hora
                                min_ref = 0
                        except Exception:
                            hora_ref = planner_hora
                            min_ref = 0

                        lembrete = datetime.combine(
                            tarefa.data,
                            datetime.min.time().replace(hour=hora_ref, minute=min_ref),
                        )
                        if _janela_inclui(agora, lembrete):
                            chave = _chave("planner", tarefa.id, lembrete)
                            if tarefa.hora_inicio and tarefa.hora_fim:
                                horario_txt = f"{tarefa.hora_inicio}-{tarefa.hora_fim}"
                            elif tarefa.duracao_min:
                                horario_txt = f"duração estimada: {int(tarefa.duracao_min)} min"
                            else:
                                horario_txt = f"início: {hora_ref:02d}:{min_ref:02d}"

                            texto = (
                                f"✅ Planner do dia: '{tarefa.titulo}'.\n"
                                f"📅 Data: {tarefa.data.strftime('%d/%m/%Y')}\n"
                                f"⏱️ Horário: {horario_txt}\n"
                                f"🏷️ Área: {tarefa.area.value} | Prioridade: {tarefa.prioridade.value}"
                            )
                            _enviar_se_novo(loop, chat_destino, chave, texto)

            except Exception:
                logger.exception("Falha no worker de lembretes da agenda.")
            finally:
                db.close()

            time.sleep(intervalo_seg)

    t = threading.Thread(target=_loop_lembretes, daemon=True, name="agenda-reminders")
    t.start()
    _AGENDA_REMINDER_WORKER_STARTED = True


def _iniciar_worker_telegram_polling() -> None:
    """Inicia worker de polling para processar mensagens recebidas no Telegram."""
    global _TELEGRAM_WORKER_STARTED

    if _TELEGRAM_WORKER_STARTED:
        return

    if not _normalizar_bool_env(os.getenv("TELEGRAM_POLLING_ENABLED"), padrao=True):
        logger.info("Telegram polling desativado por TELEGRAM_POLLING_ENABLED.")
        return

    svc = TelegramService()
    if not svc.status().get("ativo"):
        logger.info("Telegram não ativo; worker de polling não iniciado.")
        return

    # Garante modo polling e remove webhook legado que pode causar conflito.
    try:
        if svc.token:
            requests.post(
                f"https://api.telegram.org/bot{svc.token}/deleteWebhook",
                data={"drop_pending_updates": "false"},
                timeout=30,
            )
    except Exception:
        logger.exception("Falha ao preparar bot para modo polling.")

    def _loop_polling():
        offset = None
        conflitos_seguidos = 0
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("📱 Worker de polling do Telegram iniciado.")
        # Aguarda um ciclo inicial para garantir que polls anteriores expiraram
        time.sleep(5)
        while True:
            try:
                if not svc._bot:
                    time.sleep(3)
                    continue

                # python-telegram-bot v20+: get_updates é async.
                # timeout=10 (menor que 25) reduz janela de conflito em reestarts
                novos = loop.run_until_complete(
                    svc._bot.get_updates(offset=offset, timeout=10, allowed_updates=["message"])
                )
                conflitos_seguidos = 0

                for up in novos:
                    offset = up.update_id + 1
                    msg = getattr(up, "message", None)
                    if not msg:
                        continue
                    if getattr(msg, "text", None):
                        _processar_texto_telegram(svc, str(msg.chat_id), str(msg.text), loop, msg=msg)
                    elif (
                        getattr(msg, "document", None)
                        or getattr(msg, "photo", None)
                        or getattr(msg, "voice", None)
                        or getattr(msg, "audio", None)
                    ):
                        _processar_arquivo_telegram(svc, str(msg.chat_id), msg, loop)

            except Exception as _poll_exc:
                _exc_name = type(_poll_exc).__name__
                if "Conflict" in _exc_name or "Conflict" in str(_poll_exc):
                    conflitos_seguidos += 1
                    # Conflito: poll anterior ainda ativo no servidor do Telegram.
                    # Aguarda 15s para o poll de 10s anterior expirar com segurança.
                    if conflitos_seguidos <= 1:
                        logger.info("ℹ️ Conflito Telegram transitório; aguardando 15s para o poll anterior expirar...")
                    time.sleep(15)
                else:
                    logger.exception("Falha no polling do Telegram; tentando novamente...")
                    time.sleep(5)

    t = threading.Thread(target=_loop_polling, daemon=True, name="telegram-polling")
    t.start()
    _TELEGRAM_WORKER_STARTED = True


def _popular_categorias_padrao():
    """Insere as categorias padrão se o banco estiver vazio."""
    from app.database import SessionLocal

    categorias_padrao = [
        ("Alimentação",      "#E74C3C", "🛒"),
        ("Restaurante",      "#E67E22", "🍽️"),
        ("Transporte",       "#3498DB", "🚗"),
        ("Saúde",            "#2ECC71", "💊"),
        ("Educação",         "#9B59B6", "📚"),
        ("Lazer",            "#F1C40F", "🎮"),
        ("Vestuário",        "#1ABC9C", "👕"),
        ("Casa",             "#95A5A6", "🏠"),
        ("Telecomunicações", "#34495E", "📱"),
        ("Investimento",     "#27AE60", "📈"),
        ("Serviços",         "#8E44AD", "🔧"),
        ("Pets",             "#D35400", "🐾"),
        ("Outros",           "#BDC3C7", "💰"),
        ("Receitas",         "#2ECC71", "💵"),
    ]

    db = SessionLocal()
    try:
        if db.query(Categoria).count() == 0:
            for nome, cor, icone in categorias_padrao:
                db.add(Categoria(nome=nome, cor=cor, icone=icone))
            db.commit()
            logger.info(f"✅ {len(categorias_padrao)} categorias padrão criadas.")
    finally:
        db.close()


# ================================================
# Health Check
# ================================================

@app.get("/", tags=["Sistema"])
def health_check():
    return {
        "status":  "online",
        "sistema": "Assistente Financeiro Pessoal",
        "versao":  "1.0.0",
        "docs":    "/docs",
    }


# ================================================
# TRANSAÇÕES
# ================================================

@app.post("/transacoes/", response_model=TransacaoRead, tags=["Transações"])
def criar_transacao(dados: TransacaoCreate, db: Session = Depends(get_db)):
    """Cria uma nova transação manualmente."""
    t = Transacao(**dados.model_dump())
    # Auto-classifica se categoria não informada
    if not t.categoria_id:
        ClassifierService(db).classificar_e_aplicar(t)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@app.get("/transacoes/", response_model=List[TransacaoRead], tags=["Transações"])
def listar_transacoes(
    mes:          Optional[int]  = Query(None, ge=1, le=12),
    ano:          Optional[int]  = Query(None),
    categoria_id: Optional[int]  = Query(None),
    tipo:         Optional[str]  = Query(None, pattern="^(debito|credito)$"),
    busca:        Optional[str]  = Query(None),
    limite:       int            = Query(100, le=1000),
    offset:       int            = Query(0),
    db:           Session        = Depends(get_db),
):
    """Lista transações com filtros opcionais."""
    q = db.query(Transacao)
    if mes:
        q = q.filter(extract("month", Transacao.data) == mes)
    if ano:
        q = q.filter(extract("year", Transacao.data) == ano)
    if categoria_id:
        q = q.filter(Transacao.categoria_id == categoria_id)
    if tipo:
        q = q.filter(Transacao.tipo == tipo)
    if busca:
        q = q.filter(Transacao.descricao.ilike(f"%{busca}%"))
    return q.order_by(Transacao.data.desc()).offset(offset).limit(limite).all()


@app.get("/transacoes/{tid}", response_model=TransacaoRead, tags=["Transações"])
def obter_transacao(tid: int, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == tid).first()
    if not t:
        raise HTTPException(404, "Transação não encontrada")
    return t


@app.put("/transacoes/{tid}", response_model=TransacaoRead, tags=["Transações"])
def atualizar_transacao(tid: int, dados: TransacaoUpdate, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == tid).first()
    if not t:
        raise HTTPException(404, "Transação não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(t, campo, valor)
    db.commit()
    db.refresh(t)
    return t


@app.delete("/transacoes/{tid}", tags=["Transações"])
def excluir_transacao(tid: int, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == tid).first()
    if not t:
        raise HTTPException(404, "Transação não encontrada")
    db.delete(t)
    db.commit()
    return {"ok": True, "id": tid}


# ================================================
# CATEGORIAS
# ================================================

@app.get("/categorias/", response_model=List[CategoriaRead], tags=["Categorias"])
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(Categoria).filter(Categoria.ativa == True).all()


@app.post("/categorias/", response_model=CategoriaRead, tags=["Categorias"])
def criar_categoria(dados: CategoriaCreate, db: Session = Depends(get_db)):
    existente = db.query(Categoria).filter(Categoria.nome == dados.nome).first()
    if existente:
        raise HTTPException(400, f"Categoria '{dados.nome}' já existe")
    c = Categoria(**dados.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@app.put("/categorias/{cid}", response_model=CategoriaRead, tags=["Categorias"])
def atualizar_categoria(cid: int, dados: CategoriaUpdate, db: Session = Depends(get_db)):
    c = db.query(Categoria).filter(Categoria.id == cid).first()
    if not c:
        raise HTTPException(404, "Categoria não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(c, campo, valor)
    db.commit()
    db.refresh(c)
    return c


# ================================================
# CONTAS BANCÁRIAS
# ================================================

@app.get("/contas/", response_model=List[ContaBancariaRead], tags=["Contas"])
def listar_contas(db: Session = Depends(get_db)):
    return db.query(ContaBancaria).filter(ContaBancaria.ativa == True).all()


@app.post("/contas/", response_model=ContaBancariaRead, tags=["Contas"])
def criar_conta(dados: ContaBancariaCreate, db: Session = Depends(get_db)):
    c = ContaBancaria(**dados.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@app.put("/contas/{cid}", response_model=ContaBancariaRead, tags=["Contas"])
def atualizar_conta(cid: int, dados: ContaBancariaUpdate, db: Session = Depends(get_db)):
    c = db.query(ContaBancaria).filter(ContaBancaria.id == cid).first()
    if not c:
        raise HTTPException(404, "Conta não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(c, campo, valor)
    db.commit()
    db.refresh(c)
    return c


# ================================================
# CARTÕES DE CRÉDITO
# ================================================

@app.get("/cartoes/", response_model=List[CartaoCreditoRead], tags=["Cartões"])
def listar_cartoes(db: Session = Depends(get_db)):
    return db.query(CartaoCredito).filter(CartaoCredito.ativo == True).all()


@app.post("/cartoes/", response_model=CartaoCreditoRead, tags=["Cartões"])
def criar_cartao(dados: CartaoCreditoCreate, db: Session = Depends(get_db)):
    c = CartaoCredito(**dados.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ================================================
# AGENDA (Financeira + Compromissos)
# ================================================

@app.get("/agenda/financeira/{data_ref}", tags=["Agenda"])
def agenda_financeira_dia(data_ref: str, db: Session = Depends(get_db)):
    """Lista eventos financeiros para a data informada (AAAA-MM-DD)."""
    try:
        data_obj = datetime.strptime(data_ref, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, "Data inválida. Use o formato AAAA-MM-DD")

    eventos = (
        db.query(EventoFinanceiro)
        .filter(EventoFinanceiro.data_vencimento == data_obj)
        .order_by(EventoFinanceiro.data_vencimento.asc(), EventoFinanceiro.id.asc())
        .all()
    )

    itens = [
        {
            "id": int(ev.id),
            "titulo": str(ev.titulo or "Evento"),
            "descricao": str(ev.descricao or ""),
            "valor": float(ev.valor or 0.0),
            "tipo": str(getattr(ev.tipo, "value", ev.tipo) or "outro"),
            "status": str(getattr(ev.status, "value", ev.status) or "pendente"),
            "data_vencimento": ev.data_vencimento.isoformat() if ev.data_vencimento else data_ref,
        }
        for ev in eventos
    ]

    return {
        "data": data_ref,
        "total": len(itens),
        "itens": itens,
    }


@app.get("/agenda/compromissos/{data_ref}", tags=["Agenda"])
def agenda_compromissos_dia(data_ref: str, db: Session = Depends(get_db)):
    """Lista compromissos para a data informada (AAAA-MM-DD)."""
    try:
        data_obj = datetime.strptime(data_ref, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, "Data inválida. Use o formato AAAA-MM-DD")

    compromissos = (
        db.query(Compromisso)
        .filter(Compromisso.data == data_obj)
        .order_by(Compromisso.hora_inicio.asc(), Compromisso.id.asc())
        .all()
    )

    itens = [
        {
            "id": int(comp.id),
            "titulo": str(comp.titulo or "Compromisso"),
            "descricao": str(comp.descricao or ""),
            "local": str(comp.local or ""),
            "data": comp.data.isoformat() if comp.data else data_ref,
            "hora_inicio": str(comp.hora_inicio or ""),
            "hora_fim": str(comp.hora_fim or ""),
            "concluido": bool(comp.concluido),
        }
        for comp in compromissos
    ]

    return {
        "data": data_ref,
        "total": len(itens),
        "itens": itens,
    }


# ================================================
# IMPORTAÇÃO DE EXTRATOS
# ================================================

@app.post("/importar/pdf", tags=["Importação"])
async def importar_pdf(
    arquivo:      UploadFile        = File(...),
    banco:        Optional[str]     = Form(None),
    tipo_extrato: str               = Form("bancario"),
    conta_id:     Optional[int]     = Form(None),
    cartao_id:    Optional[int]     = Form(None),
    db:           Session           = Depends(get_db),
):
    """Importa transações de um arquivo PDF (extrato bancário ou fatura)."""
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    try:
        resultado = ImportService(db).importar_pdf(
            str(caminho), banco=banco, tipo_extrato=tipo_extrato,
            conta_id=conta_id, cartao_id=cartao_id
        )
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar PDF: {str(e)}")

    return resultado


@app.post("/importar/csv", tags=["Importação"])
async def importar_csv(
    arquivo:   UploadFile    = File(...),
    separador: str           = Form(","),
    encoding:  str           = Form("utf-8"),
    conta_id:  Optional[int] = Form(None),
    db:        Session       = Depends(get_db),
):
    """Importa transações de um arquivo CSV."""
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    resultado = ImportService(db).importar_csv(
        str(caminho), separador=separador, encoding=encoding, conta_id=conta_id
    )
    return resultado


@app.post("/importar/excel", tags=["Importação"])
async def importar_excel(
    arquivo:  UploadFile    = File(...),
    conta_id: Optional[int] = Form(None),
    db:       Session       = Depends(get_db),
):
    """Importa transações de um arquivo Excel (.xlsx)."""
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    resultado = ImportService(db).importar_excel(str(caminho), conta_id=conta_id)
    return resultado


@app.post("/importar/ofx", tags=["Importação"])
async def importar_ofx(
    arquivo:  UploadFile    = File(...),
    conta_id: Optional[int] = Form(None),
    db:       Session       = Depends(get_db),
):
    """Importa transações de um arquivo OFX (Open Financial Exchange)."""
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    resultado = ImportService(db).importar_ofx(str(caminho), conta_id=conta_id)
    return resultado


@app.post("/importar/fatura_cartao", tags=["Importação"])
async def importar_fatura_cartao(
    arquivo:   UploadFile    = File(...),
    cartao_id: Optional[int] = Form(None),
    db:        Session       = Depends(get_db),
):
    """
    Importa fatura de cartão com auto-detecção de formato.
    Suporta CSV (Nubank, Inter, C6, XP, Itaú), PDF, Excel e OFX.
    """
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    try:
        return ImportService(db).importar_fatura_cartao(str(caminho), cartao_id=cartao_id)
    except Exception as e:
        raise HTTPException(500, f"Erro ao processar fatura: {str(e)}")


@app.get("/extratos/", response_model=List[ExtratoRead], tags=["Importação"])
def listar_extratos(db: Session = Depends(get_db)):
    """Lista todos os extratos importados."""
    return db.query(Extrato).order_by(Extrato.importado_em.desc()).all()


@app.post("/importar/analisar", response_model=DocumentoDetectado, tags=["Importação"])
async def analisar_documento(
    arquivo: UploadFile = File(...),
):
    """
    Recebe um arquivo (PDF, imagem, DOCX, TXT), extrai o texto via OCR
    e retorna o tipo de documento identificado automaticamente.

    O arquivo é salvo temporariamente em uploads/ para uso posterior
    pelo endpoint /importar/confirmar_documento.
    """
    extensao = Path(arquivo.filename).suffix.lower()
    extensoes_aceitas = {
        ".pdf", ".jpg", ".jpeg", ".png", ".bmp",
        ".tiff", ".tif", ".webp", ".docx", ".doc", ".txt",
    }
    if extensao not in extensoes_aceitas:
        raise HTTPException(
            400,
            f"Formato '{extensao}' não suportado. "
            f"Aceitos: {', '.join(sorted(extensoes_aceitas))}"
        )

    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    try:
        from app.services.import_service import ImportService
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            resultado = ImportService(db).analisar_documento(str(caminho))
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(500, f"Erro ao analisar documento: {str(e)}")

    return DocumentoDetectado(**resultado)


@app.post("/importar/confirmar_documento", tags=["Importação"])
async def confirmar_documento(
    dados: DocumentoConfirmar,
    db: Session = Depends(get_db),
):
    """
    Recebe o tipo de documento confirmado pelo usuário e executa
    a importação/persistência no banco de dados correspondente.

    Tipos aceitos:
      - extrato_bancario   → importa como extrato bancário
      - extrato_cartao     → importa como fatura de cartão
      - nota_fiscal        → cria transação de débito
      - boleto             → cria EventoFinanceiro (a pagar)
      - comprovante_compra → cria transação de débito vinculada ao cartão
    """
    if not os.path.exists(dados.arquivo_path):
        raise HTTPException(404, f"Arquivo não encontrado: {dados.arquivo_path}")

    try:
        from app.services.import_service import ImportService
        resultado = ImportService(db).importar_por_tipo_documento(
            caminho          = dados.arquivo_path,
            tipo_documento   = dados.tipo_documento,
            conta_id         = dados.conta_id,
            cartao_id        = dados.cartao_id,
            descricao_manual = dados.descricao_manual,
        )
    except Exception as e:
        raise HTTPException(500, f"Erro ao importar documento: {str(e)}")

    return resultado


# ================================================
# DASHBOARD E INSIGHTS
# ================================================

@app.get("/dashboard/{mes}/{ano}", tags=["Dashboard"])
def dashboard(mes: int, ano: int, db: Session = Depends(get_db)):
    """Retorna dados consolidados para o painel principal."""
    return InsightsService(db).resumo_dashboard(mes, ano)


@app.get("/insights/{mes}/{ano}", tags=["Dashboard"])
def insights(mes: int, ano: int, db: Session = Depends(get_db)):
    """Gera insights financeiros automáticos para o período."""
    return InsightsService(db).gerar_insights(mes, ano)


# ================================================
# HISTÓRICO E COMPARAÇÕES
# ================================================

@app.get("/historico/tendencia", tags=["Histórico"])
def tendencia(n_meses: int = Query(6, ge=2, le=24), db: Session = Depends(get_db)):
    """Analisa a tendência de gastos nos últimos N meses."""
    return HistoricoService(db).analisar_tendencia(n_meses)


@app.get("/historico/comparar", tags=["Histórico"])
def comparar_meses(
    mes1: int = Query(...), ano1: int = Query(...),
    mes2: int = Query(...), ano2: int = Query(...),
    db: Session = Depends(get_db),
):
    """Compara despesas e receitas entre dois períodos."""
    return HistoricoService(db).comparar_meses(mes1, ano1, mes2, ano2)


@app.get("/historico/categoria/{categoria_id}", tags=["Histórico"])
def historico_categoria(
    categoria_id: int,
    n_meses: int = Query(6),
    db: Session = Depends(get_db),
):
    """Retorna o histórico de gastos de uma categoria."""
    return HistoricoService(db).historico_categoria(categoria_id, n_meses)


# ================================================
# METAS
# ================================================

@app.get("/metas/", response_model=List[MetaRead], tags=["Metas"])
def listar_metas(db: Session = Depends(get_db)):
    return MetasService(db).listar_metas()


@app.post("/metas/", response_model=MetaRead, tags=["Metas"])
def criar_meta(dados: MetaCreate, db: Session = Depends(get_db)):
    return MetasService(db).criar_meta(
        nome=dados.nome,
        valor_alvo=dados.valor_alvo,
        descricao=dados.descricao,
        valor_atual=dados.valor_atual,
        data_fim=dados.data_fim,
        categoria_id=dados.categoria_id,
    )


@app.put("/metas/{mid}/progresso", response_model=MetaRead, tags=["Metas"])
def atualizar_progresso_meta(mid: int, novo_valor: float, db: Session = Depends(get_db)):
    meta = MetasService(db).atualizar_progresso(mid, novo_valor)
    if not meta:
        raise HTTPException(404, "Meta não encontrada")
    return meta


@app.delete("/metas/{mid}", tags=["Metas"])
def excluir_meta(mid: int, db: Session = Depends(get_db)):
    ok = MetasService(db).excluir_meta(mid)
    if not ok:
        raise HTTPException(404, "Meta não encontrada")
    return {"ok": True}


# ================================================
# ORÇAMENTOS
# ================================================

@app.get("/orcamentos/{mes}/{ano}", tags=["Orçamentos"])
def listar_orcamentos(mes: int, ano: int, db: Session = Depends(get_db)):
    return MetasService(db).resumo_orcamentos(mes, ano)


@app.post("/orcamentos/", response_model=OrcamentoRead, tags=["Orçamentos"])
def criar_orcamento(dados: OrcamentoCreate, db: Session = Depends(get_db)):
    return MetasService(db).criar_orcamento(
        categoria_id=dados.categoria_id,
        valor_limite=dados.valor_limite,
        mes=dados.mes,
        ano=dados.ano,
        alerta_percentual=dados.alerta_percentual,
    )


@app.delete("/orcamentos/{oid}", tags=["Orçamentos"])
def excluir_orcamento(oid: int, db: Session = Depends(get_db)):
    ok = MetasService(db).excluir_orcamento(oid)
    if not ok:
        raise HTTPException(404, "Orçamento não encontrado")
    return {"ok": True}


# ================================================
# EXPORTAÇÃO
# ================================================

@app.post("/exportar/csv", tags=["Exportação"])
def exportar_csv(
    mes:          Optional[int] = None,
    ano:          Optional[int] = None,
    categoria_id: Optional[int] = None,
    db:           Session       = Depends(get_db),
):
    """Gera e retorna arquivo CSV com as transações."""
    nome = f"extrato_{mes or 'geral'}_{ano or ''}.csv"
    caminho = str(EXPORT_DIR / nome)
    ExportService(db).exportar_csv(caminho, mes, ano, categoria_id)
    return FileResponse(caminho, media_type="text/csv", filename=nome)


@app.post("/exportar/excel", tags=["Exportação"])
def exportar_excel(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db:  Session       = Depends(get_db),
):
    """Gera e retorna arquivo Excel com as transações."""
    nome = f"extrato_{mes or 'geral'}_{ano or ''}.xlsx"
    caminho = str(EXPORT_DIR / nome)
    ExportService(db).exportar_excel(caminho, mes, ano)
    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=nome
    )


@app.post("/exportar/pdf", tags=["Exportação"])
def exportar_pdf(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db:  Session       = Depends(get_db),
):
    """Gera e retorna relatório em PDF."""
    nome = f"relatorio_{mes or 'geral'}_{ano or ''}.pdf"
    caminho = str(EXPORT_DIR / nome)
    ExportService(db).exportar_pdf(caminho, mes, ano)
    return FileResponse(caminho, media_type="application/pdf", filename=nome)


# ================================================
# ASSISTENTE CONVERSACIONAL
# ================================================

@app.post("/assistente/", tags=["Assistente"])
def assistente(dados: PerguntaAssistente, db: Session = Depends(get_db)):
    """
    Endpoint do assistente conversacional.
    Usa Google Gemini (Vorcaro) se GEMINI_API_KEY estiver configurada;
    caso contrário, usa o fallback baseado em palavras-chave.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            resposta = GeminiService(api_key=api_key, db=db).enviar(dados.pergunta)
            return {
                "pergunta": dados.pergunta,
                "resposta": resposta,
                "dados": None,
                "provedor": "gemini",
            }
        except Exception as exc:
            logger.warning("GeminiService falhou, usando fallback: %s", exc)
    else:
        logger.info("GEMINI_API_KEY ausente no .env. Usando fallback de histórico.")

    resultado = HistoricoService(db).responder_pergunta(dados.pergunta)
    retorno = {"pergunta": dados.pergunta, **resultado, "provedor": "fallback_historico"}
    if not api_key:
        retorno["configuracao"] = "GEMINI_API_KEY ausente no .env. Configure a chave para habilitar respostas pelo Gemini."
    return retorno


@app.post("/despesa/rapida", tags=["Assistente"])
def despesa_rapida(dados: DespesaManual, db: Session = Depends(get_db)):
    """Registro rápido de despesa (via Telegram ou interface)."""
    fonte_norm = (dados.fonte or "manual").strip().lower()
    if fonte_norm not in {"manual", "telegram", "voz", "api"}:
        fonte_norm = "manual"

    t = Transacao(
        data      = dados.data or date.today(),
        descricao = dados.descricao,
        valor     = dados.valor,
        tipo      = "debito",
        fonte     = fonte_norm,
    )

    if dados.categoria:
        cat = db.query(Categoria).filter(Categoria.nome.ilike(f"%{dados.categoria}%")).first()
        if cat:
            t.categoria_id = cat.id
        else:
            ClassifierService(db).classificar_e_aplicar(t)
    else:
        ClassifierService(db).classificar_e_aplicar(t)

    db.add(t)
    db.commit()
    db.refresh(t)

    from app.utils.helpers import formatar_moeda
    return {
        "ok":       True,
        "id":       t.id,
        "mensagem": f"✅ {t.descricao} - {formatar_moeda(t.valor)} registrado com sucesso!",
        "categoria": t.categoria.nome if t.categoria else "Outros",
        "fonte": t.fonte,
    }


# ================================================
# PROCESSAMENTO DE VOZ
# ================================================

@app.post("/voz/processar", tags=["Voz"])
async def processar_voz(
    arquivo: UploadFile = File(...),
    db:      Session    = Depends(get_db),
):
    """
    Recebe arquivo de áudio, transcreve e registra a despesa.
    Suporta: OGG, MP3, WAV, M4A (do Telegram ou outros).
    """
    caminho = UPLOAD_DIR / arquivo.filename
    with open(caminho, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)

    resultado = VoiceProcessor().processar_audio(str(caminho), db)
    return resultado


@app.get("/diagnostico/ambiente", tags=["Diagnóstico"])
def diagnostico_ambiente() -> Dict[str, Any]:
    """Consolida o diagnóstico de variáveis de ambiente e serviços externos."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini = {
        "ok": bool(gemini_key),
        "mensagem": (
            "Gemini configurado."
            if gemini_key else
            "GEMINI_API_KEY ausente no .env."
        ),
    }

    try:
        openrouter_diag = OpenRouterService().diagnostico()
        openrouter = {
            "ok": bool(openrouter_diag.get("enabled") and openrouter_diag.get("api_key_ok")),
            "enabled": bool(openrouter_diag.get("enabled")),
            "mensagem": str(openrouter_diag.get("mensagem") or "OpenRouter sem diagnóstico."),
            "model": str(openrouter_diag.get("model") or ""),
        }
    except Exception as exc:
        openrouter = {
            "ok": False,
            "enabled": False,
            "mensagem": f"Falha ao inicializar OpenRouter: {exc}",
            "model": "",
        }

    try:
        local_diag = LocalAIService().diagnostico()
        local_ai = {
            "ok": bool(local_diag.get("enabled") and local_diag.get("ollama_ok")),
            "enabled": bool(local_diag.get("enabled")),
            "mensagem": str(local_diag.get("mensagem") or "IA local sem diagnóstico."),
            "model": str(local_diag.get("model") or ""),
        }
    except Exception as exc:
        local_ai = {
            "ok": False,
            "enabled": False,
            "mensagem": f"Falha ao inicializar IA local: {exc}",
            "model": "",
        }

    tg_status = TelegramService().status()
    telegram = {
        "ok": bool(tg_status.get("ativo") and tg_status.get("token_ok") and tg_status.get("chat_ok")),
        "enabled": bool(tg_status.get("token_ok")),
        "mensagem": str(tg_status.get("mensagem") or "Telegram sem diagnóstico."),
    }

    try:
        voz_diag = VoiceProcessor().diagnostico()
        voz = {
            "ok": bool(voz_diag.get("ok")),
            "mensagem": str(voz_diag.get("mensagem") or "Voz sem diagnóstico."),
            "engine": str(voz_diag.get("engine") or ""),
            "model": str(voz_diag.get("model") or ""),
        }
    except Exception as exc:
        voz = {
            "ok": False,
            "mensagem": f"Falha ao inicializar serviço de voz: {exc}",
            "engine": "",
            "model": "",
        }

    servicos = {
        "gemini": gemini,
        "openrouter": openrouter,
        "local_ai": local_ai,
        "telegram": telegram,
        "voz": voz,
    }

    pendencias = [nome for nome, item in servicos.items() if not item.get("ok")]
    return {
        "ok": len(pendencias) == 0,
        "pendencias": pendencias,
        "servicos": servicos,
    }


@app.get("/telegram/status", tags=["Telegram"])
def telegram_status():
    """Verifica o status da integração com Telegram."""
    return TelegramService().status()


@app.post("/telegram/teste", tags=["Telegram"])
async def telegram_teste(dados: TelegramTeste):
    """Envia uma mensagem de teste para validar token e chat id configurados."""
    svc = TelegramService()
    enviado = await svc.enviar_mensagem(dados.mensagem, chat_id=dados.chat_id)
    status = svc.status()
    detalhe = status.get("mensagem")
    return {
        "ok": enviado,
        "mensagem": (
            "Mensagem de teste enviada com sucesso."
            if enviado else
            f"Falha ao enviar mensagem de teste. {detalhe or 'Verifique token e chat id.'}"
        ),
        "status": status,
    }
